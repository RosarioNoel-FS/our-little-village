"""Server-only, single-repository GitHub App adapter. No PAT or OAuth fallback."""
import base64, certifi, hashlib, json, os, re, ssl, subprocess, time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
from .policy import Invalid, Conflict

REPOSITORY='RosarioNoel-FS/our-little-village'
REPOSITORY_ID=1454198001
BRANCH='staging/visual-cms'
WORKFLOW='visual-cms-staging.yml'
SHA=re.compile(r'[0-9a-f]{40}')
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def http(method,path,token,body=None,raw=False):
    if not path.startswith('/') or path.startswith('//'):raise Invalid('Invalid GitHub API path.')
    data=json.dumps(body).encode() if body is not None else None
    req=Request('https://api.github.com'+path,data=data,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2026-03-10','User-Agent':'OLV-Staff-Editor'})
    try:
        with build_opener(NoRedirect,HTTPSHandler(context=ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or certifi.where()))).open(req,timeout=30) as response:
            result=response.read(200*1024*1024+1 if raw else 15*1024*1024+1)
            if len(result)>(200 if raw else 15)*1024*1024:raise Invalid('GitHub response exceeds the allowed size.')
            return result if raw else json.loads(result)
    except HTTPError as e:
        if raw and e.code in (301,302,303,307):
            location=e.headers.get('Location','');u=urlsplit(location)
            # Signed artifact redirect: no GitHub authorization header ever leaves api.github.com.
            if u.scheme!='https' or not any(u.hostname and u.hostname.endswith(suffix) for suffix in ('.blob.core.windows.net','.actions.githubusercontent.com','.githubusercontent.com')):raise Invalid('Unexpected artifact download destination.')
            with build_opener(NoRedirect,HTTPSHandler(context=ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or certifi.where()))).open(Request(location,headers={'User-Agent':'OLV-Staff-Editor'}),timeout=60) as r:
                data=r.read(200*1024*1024+1)
                if len(data)>200*1024*1024:raise Invalid('Build artifact is too large.')
                return data
        if e.code in (409,422):raise Conflict('The staging branch changed. Refresh and review your draft.') from e
        raise Invalid('GitHub could not complete this staging operation. Check the App installation and build configuration.') from e

def b64(raw):return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
class GitHubApp:
    def __init__(self,app_id,installation_id,key_file,transport=http):
        if not str(app_id).isdigit() or not str(installation_id).isdigit():raise Invalid('GitHub App identifiers are not configured.')
        self.app_id=str(app_id);self.installation_id=str(installation_id);self.key_file=Path(key_file);self.transport=transport
        if not self.key_file.is_file():raise Invalid('The GitHub App private key file is missing.')
        if os.name!='nt' and self.key_file.stat().st_mode&0o077:raise Invalid('The GitHub App key file must be readable only by its server owner (mode 600 or 400).')
        self.token=None;self.until=0
    def jwt(self):
        now=int(time.time());message=b64(b'{"alg":"RS256","typ":"JWT"}')+'.'+b64(json.dumps({'iat':now-60,'exp':now+480,'iss':self.app_id}).encode())
        try:signature=subprocess.run(['openssl','dgst','-sha256','-sign',str(self.key_file)],input=message.encode(),capture_output=True,timeout=10,check=True).stdout
        except Exception as e:raise Invalid('The GitHub App key could not sign a request.') from e
        return message+'.'+b64(signature)
    def installation_token(self,force=False):
        if self.token and time.time()<self.until and not force:return self.token
        jwt=self.jwt();prefix='/app/installations/'+self.installation_id
        installation=self.transport('GET',prefix,jwt)
        if installation.get('repository_selection')!='selected' or installation.get('account',{}).get('login')!='RosarioNoel-FS':raise Invalid('Install this App only on the Our Little Village repository using selected repositories.')
        inspect_token=self.transport('POST',prefix+'/access_tokens',jwt,{'permissions':{'metadata':'read'}})['token']
        scope=self.transport('GET','/installation/repositories?per_page=100',inspect_token)
        repos=scope.get('repositories',[])
        if scope.get('total_count')!=1 or len(repos)!=1 or repos[0].get('id')!=REPOSITORY_ID or repos[0].get('full_name')!=REPOSITORY:raise Invalid('The GitHub App installation must include exactly Our Little Village and no other repositories.')
        result=self.transport('POST',prefix+'/access_tokens',jwt,{'repository_ids':[REPOSITORY_ID],'permissions':{'contents':'write','actions':'read'}})
        self.token=result['token'];self.until=time.time()+45*60;return self.token
    def api(self,method,suffix,body=None,raw=False):
        # No client-provided owner, repository, branch or API URL is accepted.
        return self.transport(method,'/repos/'+REPOSITORY+suffix,self.installation_token(),body,raw=raw)
    def head(self):
        sha=self.api('GET','/git/ref/heads/'+BRANCH)['object']['sha']
        if not SHA.fullmatch(sha):raise Invalid('Unexpected repository revision.')
        return sha
    def tree(self,revision):
        result=self.api('GET','/git/trees/'+revision+'?recursive=1')
        if result.get('truncated'):raise Invalid('Repository tree is too large to validate safely.')
        return result['tree']
    def read_files(self,revision,paths):
        files={}
        for path in paths:
            blob=self.api('GET','/contents/'+path+'?'+urlencode({'ref':revision}))
            if blob.get('type')!='file' or blob.get('encoding')!='base64':raise Invalid('Unexpected content file type.')
            files[path]=base64.b64decode(blob['content'])
        return files
    def commit(self,expected,files):
        if not SHA.fullmatch(expected):raise Invalid('Invalid repository revision.')
        for path in files:
            if not(re.fullmatch(r'content/(?:home|pages/(?:parties|private-events|toddler-classes|art-classes|special-events|balloons-backdrops))\.json',path) or re.fullmatch(r'assets/work/olv-[a-f0-9]{64}\.(jpg|png|webp|mp4|webm)',path)):raise Invalid('Repository write path is protected.')
        self.installation_token(force=True)
        if self.head()!=expected:raise Conflict('The staging branch changed before saving. Refresh and review.')
        entries=[]
        for path,raw in files.items():
            if not(re.fullmatch(r'content/(?:home|pages/(?:parties|private-events|toddler-classes|art-classes|special-events|balloons-backdrops))\.json',path) or re.fullmatch(r'assets/work/olv-[a-f0-9]{64}\.(jpg|png|webp|mp4|webm)',path)):raise Invalid('Repository write path is protected.')
            result=self.api('POST','/git/blobs',{'content':base64.b64encode(raw).decode(),'encoding':'base64'})
            entries.append({'path':path,'mode':'100644','type':'blob','sha':result['sha']})
        base=self.api('GET','/git/commits/'+expected)
        tree=self.api('POST','/git/trees',{'base_tree':base['tree']['sha'],'tree':entries})
        commit=self.api('POST','/git/commits',{'message':'Update Our Little Village staging content','tree':tree['sha'],'parents':[expected]})
        if self.head()!=expected:raise Conflict('Another staging update arrived. No branch was overwritten.')
        self.api('PATCH','/git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False})
        return commit['sha']
    def build(self,revision):
        runs=self.api('GET','/actions/workflows/'+WORKFLOW+'/runs?'+urlencode({'branch':BRANCH,'head_sha':revision,'event':'push','per_page':30}))['workflow_runs']
        runs=[r for r in runs if r.get('head_sha')==revision and r.get('head_branch')==BRANCH and r.get('path')=='.github/workflows/'+WORKFLOW]
        if not runs:return {'state':'awaiting-build','message':'Staging commit saved. Waiting for the staging build.'}
        run=max(runs,key=lambda r:r.get('run_attempt',1));run_id=int(run['id'])
        if run['status']!='completed':return {'state':'building','message':'GitHub is building the staging site.'}
        if run.get('conclusion')!='success':return {'state':'failed','message':'The staging build failed. The previous staging site is still available.'}
        artifacts=self.api('GET',f'/actions/runs/{run_id}/artifacts')['artifacts']
        matches=[a for a in artifacts if a.get('name')=='olv-staging-'+revision and not a.get('expired')]
        if len(matches)!=1:return {'state':'failed','message':'The verified staging build artifact is missing or expired.'}
        artifact=matches[0];raw=self.api('GET',f'/actions/artifacts/{int(artifact["id"])}/zip',raw=True)
        expected=artifact.get('digest')
        if not expected or expected!='sha256:'+hashlib.sha256(raw).hexdigest():raise Invalid('The staging build artifact checksum did not match.')
        return {'state':'built','artifact':raw,'message':'Verified staging build completed.'}
