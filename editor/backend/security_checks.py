import base64, copy, hashlib, io, json, os, subprocess, tempfile, time, unittest, uuid
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from editor.backend.auth import Auth, Denied, Limited, digest
from editor.backend.policy import Invalid, Conflict, validate_draft, strict_json
from editor.backend.server import App
from editor.backend.github_app import GitHubApp, REPOSITORY, REPOSITORY_ID, BRANCH
from editor.serve import ROOT, prepare

PASSWORD='An isolated staging test passphrase!'
def request(app,path='/',method='GET',body=None,token='',csrf=None,origin=None,host=None):
    raw=json.dumps(body).encode() if body is not None else b''
    env={'PATH_INFO':path,'REQUEST_METHOD':method,'HTTP_HOST':host or app.origin.split('//')[1], 'REMOTE_ADDR':'127.0.0.1','wsgi.input':io.BytesIO(raw),'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json','HTTP_COOKIE':app.cookie+'='+token,'HTTP_ORIGIN':origin if origin is not None else app.origin}
    if csrf is not None:env['HTTP_X_CSRF_TOKEN']=csrf
    result={}
    def start(status,headers):result.update(status=int(status.split()[0]),headers=dict(headers))
    raw=b''.join(app(env,start));result['raw']=raw
    if raw and result['headers']['Content-Type'].startswith('application/json'):result['data']=json.loads(raw)
    return result

def account(auth,email):
    token=auth.enroll(auth.invite(email,'Test staff'),PASSWORD,'test-enroll-'+email)
    return token,auth.session(token)

def draft(app,changes,media=None):return {'version':1,'baseHash':app.publisher.boot['baseHash'],'changes':changes,'media':media or {},'revision':app.publisher.revision,'requestId':str(uuid.uuid4())}
def wait_job(app,id):
    for _ in range(250):
        job=app.publisher.job(id)
        if job['state'] in ('published-staging','failed','conflict'):return job
        time.sleep(.05)
    raise AssertionError('Staging job did not finish')

class AuthTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.auth=Auth(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_invitation_is_one_use_and_no_public_registration(self):
        invite=self.auth.invite('staff@example.invalid','Village staff')
        token=self.auth.enroll(invite,PASSWORD,'one')
        self.assertIsNotNone(self.auth.session(token))
        with self.assertRaises(Denied):self.auth.enroll(invite,PASSWORD,'one')
        with self.assertRaises(Denied):self.auth.enroll('uninvited',PASSWORD,'two')
        with self.auth.db() as db:
            row=db.execute('SELECT password FROM users').fetchone();self.assertNotIn(PASSWORD,row['password'])
            stored=db.execute('SELECT hash FROM sessions').fetchone()['hash'];self.assertNotEqual(stored,token)
    def test_expired_invites_sessions_and_revoked_accounts(self):
        invite=self.auth.invite('staff@example.invalid','Village staff')
        with self.auth.db() as db:db.execute('UPDATE invites SET expires=0')
        with self.assertRaises(Denied):self.auth.enroll(invite,PASSWORD,'one')
        token,user=account(self.auth,'staff@example.invalid')
        self.auth.revoke('staff@example.invalid');self.assertIsNone(self.auth.session(token))
        with self.assertRaises(Denied):self.auth.login('staff@example.invalid',PASSWORD,'test')
    def test_credentials_rate_limits_and_csrf(self):
        token,user=account(self.auth,'staff@example.invalid')
        self.auth.check_csrf(token,self.auth.csrf(token))
        with self.assertRaises(Denied):self.auth.check_csrf(token,'wrong')
        for _ in range(6):
            with self.assertRaises(Denied):self.auth.login('staff@example.invalid','Wrong but long passphrase','test')
        with self.assertRaises(Limited):self.auth.login('staff@example.invalid',PASSWORD,'test')
        self.auth.logout(token);self.assertIsNone(self.auth.session(token))

    def test_absolute_and_idle_session_expiry(self):
        token,user=account(self.auth,'expiry@example.invalid')
        with self.auth.db() as db:db.execute('UPDATE sessions SET touched=0')
        self.assertIsNone(self.auth.session(token))
        token=self.auth.login('expiry@example.invalid',PASSWORD,'expiry')
        with self.auth.db() as db:db.execute('UPDATE sessions SET expires=0')
        self.assertIsNone(self.auth.session(token))

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.app=App(state=cls.tmp.name)
        cls.token,cls.user=account(cls.app.auth,'first@example.invalid');cls.csrf=cls.app.auth.csrf(cls.token)
        cls.other,cls.other_user=account(cls.app.auth,'second@example.invalid')
    @classmethod
    def tearDownClass(cls):
        for thread in cls.app.publisher.threads:thread.join(10)
        cls.tmp.cleanup()
    def publish(self,payload):
        result=request(self.app,'/api/publish','POST',payload,self.token,self.csrf)
        self.assertEqual(result['status'],202,result);return wait_job(self.app,result['data']['id'])
    def test_unauthenticated_and_cross_site_protected(self):
        self.assertEqual(request(self.app,'/api/bootstrap')['status'],401)
        self.assertEqual(request(self.app,'/staging/')['status'],303)
        self.assertEqual(request(self.app,'/site/assets/pages.css')['status'],303)
        self.assertEqual(request(self.app,'/api/publish','POST',{},self.token)['status'],403)
        self.assertEqual(request(self.app,'/api/publish','POST',{},self.token,self.csrf,origin='https://evil.example')['status'],403)
        self.assertEqual(request(self.app,'/api/bootstrap',token=self.token,host='evil.example')['status'],400)
        for path in ['/editor/backend/auth.py','/editor/.state/backend/staff.sqlite3','/.git/config','/site/assets/../../editor/backend/auth.py']:
            self.assertEqual(request(self.app,path,token=self.token)['status'],404,path)
        with self.assertRaises(Invalid):App(state=self.tmp.name,origin='http://public.example')
        with self.assertRaises(Invalid):App(state=self.tmp.name,mode='production')
    def test_secure_cookie_and_logout(self):
        result=request(self.app,'/api/auth/login','POST',{'email':'first@example.invalid','password':PASSWORD})
        cookie=result['headers']['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
        token=cookie.split(';')[0].split('=',1)[1]
        self.assertTrue(request(self.app,'/api/auth/session',token=token)['data']['user'])
        self.assertEqual(request(self.app,'/api/auth/logout','POST',{},token,self.app.auth.csrf(token))['status'],200)
        self.assertEqual(request(self.app,'/api/bootstrap',token=token)['status'],401)
        # The hosted HTTPS variant uses the browser-enforced __Host cookie prefix and Secure.
        https=App(state=self.tmp.name,origin='https://editor.example.invalid')
        result=request(https,'/api/auth/login','POST',{'email':'first@example.invalid','password':PASSWORD})
        self.assertTrue(result['headers']['Set-Cookie'].startswith('__Host-olv_session='));self.assertIn('Secure;',result['headers']['Set-Cookie']);self.assertIn('Strict-Transport-Security',result['headers'])
    def test_staff_draft_isolation(self):
        payload=draft(self.app,{'parties|/heading':'Staff *draft*'})
        self.assertEqual(request(self.app,'/api/draft','PUT',payload,self.token,self.csrf)['status'],200)
        self.assertEqual(request(self.app,'/api/draft',token=self.token)['data']['draft']['changes'],payload['changes'])
        self.assertIsNone(request(self.app,'/api/draft',token=self.other)['data']['draft'])
    def test_protected_fields_types_paths_and_duplicate_json(self):
        for field in ['parties|/buttons/0/to','parties|/sections/0/cards/0/wide','contact|/heading','other-repository|/heading','parties|/__proto__','parties|/gallery/99/image']:
            with self.assertRaises(Invalid):validate_draft(self.app.publisher.boot,draft(self.app,{field:'attempt'}))
        for value in ['<script>alert(1)</script>','',{'html':'text'},'x'*4001]:
            with self.assertRaises(Invalid):validate_draft(self.app.publisher.boot,draft(self.app,{'parties|/heading':value}))
        with self.assertRaises(Invalid):strict_json('{"changes":{},"changes":{"evil":true}}')
        payload=draft(self.app,{'parties|/heading':'Safe'});payload['repository']='other/repo'
        with self.assertRaises(Invalid):validate_draft(self.app.publisher.boot,payload)
    def test_media_decoding_and_generated_filename(self):
        im=Image.new('RGB',(40,40),'red');buffer=io.BytesIO();im.save(buffer,format='JPEG');raw=buffer.getvalue()
        entry={'data':'data:image/jpeg;base64,'+base64.b64encode(raw).decode(),'name':'../../secret.jpg','width':99999,'bytes':1}
        payload=draft(self.app,{'parties|/photo/image':'draft:upload'},{'draft:upload':entry});files=validate_draft(self.app.publisher.boot,payload)
        paths=[p for p in files if p.startswith('assets/')];self.assertEqual(len(paths),1);self.assertRegex(paths[0],r'^assets/work/olv-[a-f0-9]{64}\.jpg$')
        for value in ['https://evil.example/file.jpg','/assets/work/../../secret.jpg']:
            with self.assertRaises(Invalid):validate_draft(self.app.publisher.boot,draft(self.app,{'parties|/photo/image':value}))
        forged={'data':'data:image/jpeg;base64,'+base64.b64encode(b'<svg onload=alert(1) />').decode()}
        with self.assertRaises(Invalid):validate_draft(self.app.publisher.boot,draft(self.app,{'parties|/photo/image':'draft:fake'},{'draft:fake':forged}))
        video=(ROOT/'assets/work/art.mp4').read_bytes();v={'data':'data:video/mp4;base64,'+base64.b64encode(video).decode(),'duration':0,'width':0}
        result=validate_draft(self.app.publisher.boot,draft(self.app,{'private-events|/video':'draft:video'},{'draft:video':v}));self.assertTrue(any(k.endswith('.mp4') for k in result))
        with self.assertRaises(Invalid):validate_draft(self.app.publisher.boot,draft(self.app,{'private-events|/video':'draft:photo'},{'draft:photo':entry}))
    def test_publish_photo_video_then_restore_original_sources(self):
        previous=self.app.publisher.revision
        image=io.BytesIO();Image.new('RGB',(80,60),'blue').save(image,format='PNG')
        video=(ROOT/'assets/work/art.mp4').read_bytes()
        uploads={'draft:photo':{'data':'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()},'draft:video':{'data':'data:video/mp4;base64,'+base64.b64encode(video).decode()}}
        payload=draft(self.app,{'private-events|/photo/image':'draft:photo','private-events|/photo/alt':'Blue test image','private-events|/video':'draft:video'},uploads)
        job=self.publish(payload);self.assertEqual(job['state'],'published-staging',job)
        doc=json.loads((self.app.publisher.repo/'content/pages/private-events.json').read_text())
        self.assertRegex(doc['photo']['image'],r'^/assets/work/olv-[a-f0-9]{64}\.png$');self.assertRegex(doc['video'],r'^/assets/work/olv-[a-f0-9]{64}\.mp4$')
        stage=request(self.app,'/staging/private-events.html',token=self.token)['raw']
        self.assertIn(doc['video'].lstrip('/').encode(),stage);self.assertIn(b'Blue test image',stage)
        result=self.app.publisher.restore(self.user,previous,self.app.publisher.revision,str(uuid.uuid4()));restored=wait_job(self.app,result['id']);self.assertEqual(restored['state'],'published-staging',restored)
        doc=json.loads((self.app.publisher.repo/'content/pages/private-events.json').read_text());self.assertEqual(doc.get('video','/assets/work/private.mp4'),'/assets/work/private.mp4')
    def test_publish_build_restore_conflicts_idempotency_and_failure(self):
        before=self.app.publisher.revision;original=(self.app.publisher.repo/'content/pages/parties.json').read_bytes()
        protected=(self.app.publisher.repo/'contact.html').read_bytes()
        payload=draft(self.app,{'parties|/heading':'Published *staging test*'})
        job=self.publish(payload);self.assertEqual(job['state'],'published-staging',job)
        current=self.app.publisher.revision;self.assertNotEqual(before,current)
        stage=request(self.app,'/staging/parties.html',token=self.token);self.assertIn(b'Published <em>staging test</em>',stage['raw']);self.assertIn(b'not the live website',stage['raw'])
        self.assertEqual((self.app.publisher.repo/'contact.html').read_bytes(),protected)
        repeat=request(self.app,'/api/publish','POST',payload,self.token,self.csrf);self.assertEqual(repeat['data']['id'],job['id'])
        self.assertEqual(request(self.app,'/api/publish','POST',draft(self.app,{'parties|/heading':'Another'},),self.token,'bad')['status'],403)
        stale={**payload,'requestId':str(uuid.uuid4())};self.assertEqual(request(self.app,'/api/publish','POST',stale,self.token,self.csrf)['status'],409)
        failing=draft(self.app,{'parties|/heading':'Do not *activate*'})
        with patch.object(self.app.publisher,'build',side_effect=RuntimeError('simulated build failure')):
            failed=self.publish(failing)
        self.assertEqual(failed['state'],'failed');self.assertEqual(self.app.publisher.revision,current);self.assertEqual(self.app.publisher.active(),current)
        restored=request(self.app,'/api/restore','POST',{'revision':before,'expectedRevision':current,'requestId':str(uuid.uuid4())},self.token,self.csrf)
        self.assertEqual(restored['status'],202,restored);done=wait_job(self.app,restored['data']['id']);self.assertEqual(done['state'],'published-staging',done)
        self.assertEqual(json.loads((self.app.publisher.repo/'content/pages/parties.json').read_bytes()),json.loads(original))
        # Local staging never has a remote, production branch or repository owner token.
        self.assertEqual(subprocess.check_output(['git','-C',str(self.app.publisher.repo),'remote']).strip(),b'')
        self.assertEqual(subprocess.check_output(['git','-C',str(self.app.publisher.repo),'branch','--show-current']).decode().strip(),BRANCH)

class GitHubAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.key=Path(self.tmp.name)/'app.pem';self.key.write_text('test key');self.key.chmod(0o600);self.calls=[];self.broad=False
        self.head='a'*40
        def transport(method,path,token,body=None,raw=False):
            self.calls.append((method,path,body,token))
            if path=='/app/installations/2':return {'repository_selection':'selected','account':{'login':'RosarioNoel-FS'}}
            if path.endswith('/access_tokens'):return {'token':'fixture-inspect' if body['permissions']=={'metadata':'read'} else 'fixture-scoped'}
            if path.startswith('/installation/repositories'):return {'total_count':2 if self.broad else 1,'repositories':[{'id':REPOSITORY_ID,'full_name':REPOSITORY}]}
            if '/git/ref/' in path:return {'object':{'sha':self.head}}
            if '/git/blobs' in path:return {'sha':'b'*40}
            if '/git/commits/' in path:return {'tree':{'sha':'c'*40}}
            if path.endswith('/git/trees'):return {'sha':'d'*40}
            if path.endswith('/git/commits'):return {'sha':'e'*40}
            if '/git/refs/' in path:self.head=body['sha'];return {}
            raise AssertionError((method,path))
        self.app=GitHubApp('1','2',self.key,transport=transport);self.app.jwt=lambda:'test-jwt'
    def tearDown(self):self.tmp.cleanup()
    def test_single_repo_install_and_write_token_scope(self):
        self.app.installation_token();writes=[c for c in self.calls if c[2] and c[2].get('repository_ids')]
        self.assertEqual(writes[0][2],{'repository_ids':[REPOSITORY_ID],'permissions':{'contents':'write','actions':'read'}})
        self.broad=True;self.calls=[]
        with self.assertRaises(Invalid):self.app.installation_token(force=True)
        self.assertFalse(any(c[2] and c[2].get('repository_ids') for c in self.calls))
    def test_atomic_fixed_staging_branch_and_path_restrictions(self):
        self.app.commit('a'*40,{'content/home.json':b'{}'});patches=[c for c in self.calls if c[0]=='PATCH']
        self.assertEqual(len(patches),1);self.assertTrue(patches[0][1].endswith('/git/refs/heads/'+BRANCH));self.assertFalse(patches[0][2]['force'])
        self.assertTrue(all('/repos/' not in c[1] or c[1].startswith('/repos/'+REPOSITORY+'/') for c in self.calls))
        with self.assertRaises(Conflict):self.app.commit('a'*40,{'content/home.json':b'{}'})
        with self.assertRaises(Invalid):self.app.commit(self.head,{'.github/workflows/evil.yml':b'evil'})
    def test_remote_snapshot_revision_does_not_follow_a_newer_head(self):
        import re
        from editor.backend.publishing import CONTENT
        class Remote:
            def __init__(self):self.calls=0
            def head(self):self.calls+=1;return 'a'*40 if self.calls==1 else 'b'*40
            def read_files(self,revision,paths):
                assert revision=='a'*40
                return {p:(ROOT/p).read_bytes() for p in paths}
            def tree(self,revision):
                result=[]
                for p in (ROOT/'assets/work').iterdir():
                    if re.fullmatch(r'[\w.-]+\.(jpe?g|png|webp|mp4|webm)',p.name,re.I):
                        data=p.read_bytes();result.append({'path':'assets/work/'+p.name,'mode':'100644','type':'blob','size':len(data),'sha':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()})
                return result
            def commit(self,*args):raise AssertionError('A newer remote head must not be overwritten.')
        remote=Remote();app=App(state=Path(self.tmp.name)/'remote-state',mode='github-staging',github=remote)
        self.assertEqual(app.publisher.revision,'a'*40)
        token,user=account(app.auth,'remote@example.invalid')
        job=app.publisher.submit(user,draft(app,{'parties|/heading':'Safe *change*'}));result=wait_job(app,job['id'])
        self.assertEqual(result['state'],'conflict')
    def test_real_rsa_jwt_signature_and_private_key_permissions(self):
        key=Path(self.tmp.name)/'rsa.pem';public=Path(self.tmp.name)/'rsa.pub'
        subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(key)],check=True,capture_output=True)
        key.chmod(0o600);adapter=GitHubApp('1','2',key);token=adapter.jwt();head,payload,signature=token.split('.')
        claims=json.loads(base64.urlsafe_b64decode(payload+'='*((4-len(payload)%4)%4)));self.assertEqual(claims['iss'],'1');self.assertLessEqual(claims['exp']-claims['iat'],600)
        subprocess.run(['openssl','pkey','-in',str(key),'-pubout','-out',str(public)],check=True,capture_output=True)
        sig=Path(self.tmp.name)/'signature';sig.write_bytes(base64.urlsafe_b64decode(signature+'='*((4-len(signature)%4)%4)))
        result=subprocess.run(['openssl','dgst','-sha256','-verify',str(public),'-signature',str(sig)],input=(head+'.'+payload).encode(),capture_output=True)
        self.assertEqual(result.returncode,0)
        key.chmod(0o644)
        with self.assertRaises(Invalid):GitHubApp('1','2',key)
    def test_workflow_state_uses_exact_commit_branch_and_checksum(self):
        revision='a'*40
        run={'id':10,'head_sha':revision,'head_branch':BRANCH,'path':'.github/workflows/visual-cms-staging.yml','status':'completed','conclusion':'failure'}
        self.app.api=lambda method,path,body=None,raw=False: {'workflow_runs':[run]}
        self.assertEqual(self.app.build(revision)['state'],'failed')
        run['head_sha']='f'*40
        self.assertEqual(self.app.build(revision)['state'],'awaiting-build')
        run['head_sha']=revision;run['conclusion']='success'
        def api(method,path,body=None,raw=False):
            if '/runs?' in path:return {'workflow_runs':[run]}
            if '/artifacts' in path and not path.endswith('/zip'):return {'artifacts':[{'id':1,'name':'olv-staging-'+revision,'expired':False,'digest':'sha256:wrong'}]}
            return b'build archive bytes'
        self.app.api=api
        with self.assertRaises(Invalid):self.app.build(revision)
    def test_artifact_zip_slip_and_site_revision_binding(self):
        from editor.backend.publishing import safe_artifact
        data=io.BytesIO()
        import zipfile
        with zipfile.ZipFile(data,'w') as z:z.writestr('../../stolen','bad')
        with self.assertRaises(Invalid):safe_artifact(data.getvalue(),Path(self.tmp.name)/'extract','a'*40)

if __name__=='__main__':unittest.main()
