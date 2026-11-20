"""Build/release coordination. Only staging; atomic snapshots and append-only media."""
import contextlib, copy, fcntl, hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, threading, time, uuid, zipfile
from pathlib import Path
from .policy import Invalid, Conflict, validate_draft, strict_json
from .github_app import BRANCH, REPOSITORY, GitHubApp
from ..serve import prepare, PAGES

PUBLIC_FILES=['index.html','parties.html','private-events.html','toddler-classes.html','art-classes.html','special-events.html','balloons-backdrops.html','contact.html','privacy.html','favicon.png','apple-touch-icon.png','robots.txt','sitemap.xml']
CONTENT=['content/home.json']+['content/pages/'+p+'.json' for p in PAGES if p!='home']
def git(root,*args,input=None):
    return subprocess.run(['git','-C',str(root),*args],input=input,capture_output=True,check=True,timeout=90).stdout.decode().strip()
def copy_source(source,target):
    target.mkdir(parents=True,exist_ok=True)
    for folder in ['assets','content','cms']:
        shutil.copytree(source/folder,target/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    for name in PUBLIC_FILES:
        if (source/name).is_file():shutil.copy2(source/name,target/name)

def safe_artifact(raw,target,expected_revision):
    total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len(archive.infolist())>2000:raise Invalid('Build artifact has too many entries.')
        seen=set()
        for entry in archive.infolist():
            name=entry.filename
            if entry.is_dir():continue
            if name in seen or name.startswith('/') or '\\' in name or '..' in Path(name).parts or any(p.startswith('.') for p in Path(name).parts):raise Invalid('Unsafe build artifact path.')
            if (entry.external_attr>>16)&0o170000==0o120000:raise Invalid('Build artifact contains a symlink.')
            if name not in PUBLIC_FILES and not re.fullmatch(r'assets/[\w./-]+',name) and name not in CONTENT and name!='olv-build.json':raise Invalid('Build artifact contains a protected path.')
            seen.add(name);total+=entry.file_size
            if total>200*1024*1024 or entry.file_size>40*1024*1024:raise Invalid('Build artifact exceeds limits.')
            dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(archive.read(entry))
    marker=json.loads((target/'olv-build.json').read_text())
    if marker.get('revision')!=expected_revision or marker.get('repository')!=REPOSITORY or marker.get('branch')!=BRANCH:raise Invalid('Staging artifact does not belong to this exact site revision.')
    for file in CONTENT+['index.html']:
        if not(target/file).is_file():raise Invalid('Staging artifact is incomplete.')

class Publisher:
    def __init__(self,source,state,auth,mode='local-staging',github=None):
        if mode not in ('local-staging','github-staging'):raise Invalid('Only staging publishing is supported. Production publishing is disabled in this release.')
        self.source=Path(source);self.state=Path(state);self.auth=auth;self.mode=mode;self.github=github
        self.repo=self.state/'staging-repo';self.releases=self.state/'releases';self.releases.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.boot=None;self.revision=None;self.threads=[]
        with self.exclusive():
            if mode=='local-staging':self.init_local()
            elif not github:raise Invalid('A single-repository GitHub App is required for GitHub staging.')
            else:self.sync_github()
            self.refresh()
            with auth.db() as db:
                for row in db.execute('SELECT id,data FROM jobs').fetchall():
                    job=json.loads(row['data'])
                    if job['state'] in ('queued','validating','committing') or (mode=='local-staging' and job['state']=='building'):
                        job.update(state='failed',message='The server restarted during this operation. Review the current staging site before trying again.')
                        db.execute('UPDATE jobs SET data=? WHERE id=?',(json.dumps(job),row['id']))
    @contextlib.contextmanager
    def exclusive(self):
        self.state.mkdir(parents=True,exist_ok=True,mode=0o700)
        with self.lock, (self.state/'publish.lock').open('a') as f:
            fcntl.flock(f.fileno(),fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(f.fileno(),fcntl.LOCK_UN)
    def init_local(self):
        if not(self.repo/'.git').exists():
            copy_source(self.source,self.repo);git(self.repo,'init','-b',BRANCH)
            git(self.repo,'config','user.name','Our Little Village Staging');git(self.repo,'config','user.email','staging@localhost')
            self.build(self.repo);git(self.repo,'add','assets','content','cms',*[p for p in PUBLIC_FILES if (self.repo/p).exists()])
            git(self.repo,'commit','-m','Initialize isolated local staging site')
            revision=git(self.repo,'rev-parse','HEAD');self.release(self.repo,revision)
    def build(self,root):
        for script,args in [('optimize.py',['assets/work']),('build.py',[])]:
            env=dict(os.environ);env.pop('OLV_EDITOR_PREVIEW',None);env.pop('OLV_EDITOR_OUTPUT',None)
            subprocess.run([sys.executable,str(root/'cms'/script),*args],cwd=root,env=env,capture_output=True,timeout=120,check=True)
    def release(self,root,revision):
        dest=self.releases/revision
        if not dest.exists():
            temp=self.releases/('tmp-'+uuid.uuid4().hex);temp.mkdir()
            for folder in ['assets','content']:shutil.copytree(root/folder,temp/folder)
            for name in PUBLIC_FILES:
                if(root/name).is_file():shutil.copy2(root/name,temp/name)
            os.replace(temp,dest)
        pointer=self.state/'active.json';tmp=pointer.with_suffix('.tmp');tmp.write_text(json.dumps({'revision':revision}));os.replace(tmp,pointer)
    def active(self):
        p=self.state/'active.json'
        return json.loads(p.read_text())['revision'] if p.exists() else None
    def refresh(self):
        self.revision=git(self.repo,'rev-parse','HEAD') if self.mode=='local-staging' else self.remote_revision
        self.boot=prepare(self.repo,self.state/'preview')
    def sync_github(self):
        # Seed trusted renderer/assets from the reviewed source bundle. Only remote JSON is read as content.
        if not self.repo.exists():copy_source(self.source,self.repo)
        revision=self.github.head();files=self.github.read_files(revision,CONTENT)
        for name,data in files.items():(self.repo/name).write_bytes(data)
        # Download only flat approved media blobs with bounded sizes, never remote executable templates.
        seen_media=set()
        for entry in self.github.tree(revision):
            path=entry.get('path','')
            if re.fullmatch(r'assets/work/[\w.-]+\.(jpe?g|png|webp|mp4|webm)',path,re.I):
                seen_media.add(path)
                if entry.get('mode')!='100644' or entry.get('type')!='blob' or entry.get('size',0)>20*1024*1024:raise Invalid('Invalid staging media tree entry.')
                dest=self.repo/path
                if dest.exists() and hashlib.sha1(b'blob '+str(dest.stat().st_size).encode()+b'\0'+dest.read_bytes()).hexdigest()==entry['sha']:continue
                blob=self.github.api('GET','/git/blobs/'+entry['sha']);data=__import__('base64').b64decode(blob['content'])
                if len(data)>20*1024*1024:raise Invalid('Remote media exceeds limits.')
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        for cached in (self.repo/'assets/work').iterdir():
            if re.fullmatch(r'[\w.-]+\.(jpe?g|png|webp|mp4|webm)',cached.name,re.I) and 'assets/work/'+cached.name not in seen_media:cached.unlink()
        self.remote_revision=revision
    def job(self,id):
        with self.auth.db() as db:row=db.execute('SELECT data FROM jobs WHERE id=?',(id,)).fetchone()
        if not row:raise Invalid('Staging operation not found.')
        return json.loads(row['data'])
    def update(self,id,**values):
        job=self.job(id);job.update(values,updated=time.time())
        with self.auth.db() as db:db.execute('UPDATE jobs SET data=? WHERE id=?',(json.dumps(job),id))
        return job
    def submit(self,user,payload):
        request_id=payload.get('requestId')
        if not isinstance(request_id,str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,80}',request_id):raise Invalid('A unique request identifier is required.')
        request_hash=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        with self.exclusive():
            with self.auth.db() as db:existing=db.execute('SELECT id,request_hash FROM jobs WHERE user_id=? AND request_id=?',(user['id'],request_id)).fetchone()
            if existing:
                if existing['request_hash']!=request_hash:raise Conflict('This request identifier was already used for another draft.')
                return self.job(existing['id'])
            # Fail before scheduling if the draft is invalid, stale or attempts a protected write.
            files=validate_draft(self.boot,payload,self.revision)
            if not files:raise Invalid('There are no applied changes to publish.')
            id=uuid.uuid4().hex;job={'id':id,'state':'queued','message':'Staging update queued.','created':time.time(),'updated':time.time(),'actor':user['id'],'expected':self.revision,'target':'staging','mode':self.mode}
            with self.auth.db() as db:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(id,user['id'],request_id,request_hash,json.dumps(job)))
            self.auth.audit(user['id'],'publish-staging',id)
        worker=threading.Thread(target=self.execute,args=(id,files),daemon=True);self.threads.append(worker);worker.start();return job
    def execute(self,id,files):
        try:
            with self.exclusive():
                job=self.job(id);expected=job['expected'];self.update(id,state='validating',message='Checking the current staging revision.')
                current=git(self.repo,'rev-parse','HEAD') if self.mode=='local-staging' else self.github.head()
                if current!=expected:raise Conflict('Another update changed staging. Refresh your draft; nothing was overwritten.')
                if self.mode=='github-staging':
                    self.update(id,state='committing',message='Saving validated content to the staging branch.')
                    revision=self.github.commit(expected,files)
                    self.update(id,state='awaiting-build',revision=revision,message='Staging commit saved. Waiting for the verified GitHub build.');return
                with tempfile.TemporaryDirectory(dir=self.state,prefix='build-') as td:
                    candidate=Path(td);copy_source(self.repo,candidate)
                    for name,raw in files.items():dest=candidate/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
                    self.update(id,state='building',message='Optimizing photos and building the staging website.')
                    self.build(candidate)
                    # Build must succeed before the isolated staging branch or active site changes.
                    copy_source(candidate,self.repo)
                    git(self.repo,'add','assets','content',*[p for p in PUBLIC_FILES if (self.repo/p).exists()])
                    if git(self.repo,'diff','--cached','--name-only'):
                        git(self.repo,'commit','-m','Apply validated staff staging update')
                    revision=git(self.repo,'rev-parse','HEAD');self.refresh();self.release(self.repo,revision)
                    self.update(id,state='published-staging',revision=revision,message='Published to the isolated local staging site. The live website is unchanged.',url='/staging/')
        except Conflict as e:
            self.auth.audit(self.job(id)['actor'],'staging-conflict',id);self.update(id,state='conflict',message=str(e))
        except Exception:
            self.auth.audit(self.job(id)['actor'],'staging-failed',id)
            self.update(id,state='failed',message='Staging could not be activated. The previous staging site is still available. Review the current staging revision before trying again.')
    def poll(self,id):
        job=self.job(id)
        if self.mode!='github-staging' or job['state'] not in ('awaiting-build','building'):return job
        with self.exclusive():
            try:
                if time.time()-job['created']>1800:return self.update(id,state='failed',message='No verified staging build arrived within 30 minutes. Check the staging workflow.')
                result=self.github.build(job['revision'])
                if result['state']=='built':
                    with tempfile.TemporaryDirectory(dir=self.state,prefix='artifact-') as td:
                        root=Path(td);safe_artifact(result['artifact'],root,job['revision'])
                        # A completed older build never replaces a more recent branch revision.
                        if self.github.head()!=job['revision']:raise Conflict('A newer staging revision exists. This older build was not activated.')
                        self.release(root,job['revision']);self.sync_github();self.refresh()
                    return self.update(id,state='published-staging',message='Verified GitHub build is available on the protected staging site.',url='/staging/')
                return self.update(id,state=result['state'],message=result['message'])
            except Conflict as e:return self.update(id,state='conflict',message=str(e))
            except Exception:return self.update(id,state='failed',message='The staging artifact could not be verified. The previous staging site is still available.')
    def history(self):
        return [{'revision':p.name,'active':p.name==self.active()} for p in sorted(self.releases.iterdir(),key=lambda p:p.stat().st_mtime,reverse=True) if re.fullmatch('[a-f0-9]{40}',p.name)]
    def restore(self,user,revision,expected,request_id):
        if not isinstance(revision,str) or not re.fullmatch('[a-f0-9]{40}',revision) or not(self.releases/revision).is_dir():raise Invalid('Choose a verified staging release from history.')
        if expected!=self.revision:raise Conflict('Staging changed. Refresh before restoring.')
        old=self.releases/revision;changes={}
        for page,p in self.boot['pages'].items():
            doc=json.loads((old/p['source']).read_text())
            # Legacy loop defaults are part of the effective editable model.
            if page=='home':
                for clip,panel in doc['panels'].items():panel.setdefault('video','/assets/work/'+clip+'.mp4')
            else:
                clip={'private-events':'private','toddler-classes':'toddler','art-classes':'art','special-events':'special','balloons-backdrops':'balloons'}.get(page,page)
                doc.setdefault('video','/assets/work/'+clip+'.mp4')
            for f in p['fields']:
                value=doc
                for part in f['path'][1:].split('/'):value=value[int(part)] if isinstance(value,list) else value[part]
                now=p['content']
                for part in f['path'][1:].split('/'):now=now[int(part)] if isinstance(now,list) else now[part]
                if now!=value:changes[page+'|'+f['path']]=value
        return self.submit(user,{'version':1,'baseHash':self.boot['baseHash'],'changes':changes,'media':{},'revision':expected,'requestId':request_id})
