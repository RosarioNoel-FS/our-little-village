"""Protected single-site WSGI app. Use gunicorn behind HTTPS for hosted staging."""
import argparse, html, json, mimetypes, os, re, secrets, sqlite3, sys, threading, time
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import unquote, urlsplit
from .auth import Auth, Denied, Limited
from .policy import Invalid, Conflict, MAX_BODY, strict_json, validate_draft
from .publishing import Publisher, PUBLIC_FILES
from .github_app import GitHubApp, REPOSITORY, BRANCH
from ..serve import ROOT

class App:
    def __init__(self,source=ROOT,state=None,origin='http://127.0.0.1:4180',mode='local-staging',github=None):
        self.source=Path(source);self.state=Path(state or self.source/'editor/.state/backend');self.origin=origin.rstrip('/')
        parsed=urlsplit(self.origin)
        if parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or parsed.password:raise Invalid('Use a single editor origin without a path.')
        self.secure=parsed.scheme=='https'
        if not self.secure and not(parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost')):raise Invalid('Hosted editors require HTTPS. HTTP is permitted only on loopback.')
        self.cookie='__Host-olv_session' if self.secure else 'olv_session'
        self.auth=Auth(self.state);self.publisher=Publisher(self.source,self.state,self.auth,mode,github)
        self.mode=mode
    def response(self,start,status,body=b'',mime='application/json',extra=()):
        if isinstance(body,dict):body=json.dumps(body).encode()
        elif isinstance(body,str):body=body.encode()
        headers=[('Content-Type',mime),('Content-Length',str(len(body))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('X-Frame-Options','SAMEORIGIN'),('Permissions-Policy','camera=(), microphone=(), geolocation=()'),('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; media-src 'self' data: blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'")]
        if self.secure:headers.append(('Strict-Transport-Security','max-age=31536000'))
        headers.extend(extra);start(str(status)+' '+HTTPStatus(status).phrase,headers);return [body]
    def token(self,env):
        try:c=SimpleCookie();c.load(env.get('HTTP_COOKIE',''));return c[self.cookie].value if self.cookie in c else ''
        except Exception:return ''
    def session_cookie(self,token):return self.cookie+'='+token+'; Path=/; HttpOnly; SameSite=Strict; '+('Secure; ' if self.secure else '')+'Max-Age='+('28800' if token else '0')
    def body(self,env,limit=MAX_BODY):
        try:length=int(env.get('CONTENT_LENGTH','0'))
        except ValueError:raise Invalid('Invalid request length.')
        if not 0<length<=limit:raise Invalid('Request is empty or too large.')
        if env.get('CONTENT_TYPE','').split(';')[0]!='application/json':raise Invalid('Use a JSON request.')
        raw=env['wsgi.input'].read(length)
        if len(raw)!=length:raise Invalid('Incomplete request.')
        data=strict_json(raw)
        if not isinstance(data,dict):raise Invalid('Expected a JSON object.')
        return data
    def only(self,data,keys):
        if set(data)!=set(keys):raise Invalid('Unexpected or missing request fields.')
    def static(self,start,file):
        if not file.is_file() or file.is_symlink() or not any(file.resolve().is_relative_to(root.resolve()) for root in (self.source,self.state)):return self.response(start,404,{'error':'Page not found.'})
        return self.response(start,200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
    def __call__(self,env,start):
        try:
            host=urlsplit(self.origin).netloc
            if env.get('HTTP_HOST')!=host:return self.response(start,400,{'error':'Invalid editor host.'})
            path=unquote(env.get('PATH_INFO','/'));method=env.get('REQUEST_METHOD','GET')
            if '..' in path.split('/') or '\\' in path or any(p.startswith('.') for p in path.split('/') if p):return self.response(start,404,{'error':'Page not found.'})
            if method not in ('GET','POST','PUT'):return self.response(start,405,{'error':'Method is not supported.'})
            token=self.token(env);user=self.auth.session(token)
            if method in ('POST','PUT'):
                if env.get('HTTP_ORIGIN')!=self.origin:raise Denied('This request must come from the editor.')
                if env.get('HTTP_SEC_FETCH_SITE','same-origin') not in ('same-origin','none'):raise Denied('Cross-site requests are not accepted.')
            public=path in ('/signin','/auth.js','/auth.css','/api/auth/login','/api/auth/enroll','/api/auth/session','/healthz')
            if path=='/healthz':return self.response(start,200,{'status':'ok','mode':self.mode,'productionPublishing':False})
            if path=='/signin' and method=='GET':return self.static(start,self.source/'editor/backend/signin.html')
            if path in ('/auth.js','/auth.css') and method=='GET':return self.static(start,self.source/'editor/backend'/path[1:])
            if path=='/api/auth/session' and method=='GET':return self.response(start,200,{'user':user,'csrf':self.auth.csrf(token) if user else None,'mode':self.mode})
            if path in ('/api/auth/login','/api/auth/enroll') and method=='POST':
                data=self.body(env,8192);ip=env.get('REMOTE_ADDR','unknown')
                if path.endswith('/login'):
                    self.only(data,['email','password']);new=self.auth.login(data['email'],data['password'],ip)
                else:self.only(data,['token','password']);new=self.auth.enroll(data['token'],data['password'],ip)
                if token:self.auth.logout(token)
                return self.response(start,200,{'ok':True},extra=[('Set-Cookie',self.session_cookie(new))])
            if not user:
                if path.startswith('/api/'):return self.response(start,401,{'error':'Please sign in to the Our Little Village editor.'})
                return self.response(start,303,b'',extra=[('Location','/signin')])
            if method in ('POST','PUT'):self.auth.check_csrf(token,env.get('HTTP_X_CSRF_TOKEN',''))
            if path=='/api/auth/logout' and method=='POST':
                self.auth.logout(token);return self.response(start,200,{'ok':True},extra=[('Set-Cookie',self.session_cookie(''))])
            if path=='/api/bootstrap' and method=='GET':
                with self.publisher.exclusive():
                    b=dict(self.publisher.boot);b.update(mode=self.mode,revision=self.publisher.revision,auth={'user':user,'csrf':self.auth.csrf(token)},publishing={'enabled':True,'target':'Our Little Village staging','productionEnabled':False,'local':self.mode=='local-staging'})
                return self.response(start,200,b)
            if path=='/api/draft' and method=='GET':
                with self.auth.db() as db:row=db.execute('SELECT data,updated FROM drafts WHERE user_id=?',(user['id'],)).fetchone()
                return self.response(start,200,{'draft':json.loads(row['data']) if row else None,'updated':row['updated'] if row else None})
            if path=='/api/draft' and method=='PUT':
                data=self.body(env)
                with self.publisher.exclusive():validate_draft(self.publisher.boot,data)
                with self.auth.db() as db:db.execute('INSERT OR REPLACE INTO drafts VALUES(?,?,?)',(user['id'],json.dumps(data),time.time()))
                self.auth.audit(user['id'],'save-staff-draft');return self.response(start,200,{'saved':True})
            if path=='/api/publish' and method=='POST':
                self.auth.rate('publish:'+user['id'],20)
                return self.response(start,202,self.publisher.submit(user,self.body(env)))
            if path=='/api/restore' and method=='POST':
                data=self.body(env);self.only(data,['revision','expectedRevision','requestId'])
                self.auth.rate('restore:'+user['id'],20)
                return self.response(start,202,self.publisher.restore(user,data['revision'],data['expectedRevision'],data['requestId']))
            if path=='/api/releases' and method=='GET':return self.response(start,200,{'releases':self.publisher.history(),'revision':self.publisher.revision})
            if re.fullmatch(r'/api/jobs/[a-f0-9]{32}',path) and method=='GET':return self.response(start,200,self.publisher.poll(path.split('/')[-1]))
            if path=='/api/jobs' and method=='GET':
                with self.auth.db() as db:rows=db.execute('SELECT data FROM jobs ORDER BY rowid DESC LIMIT 10').fetchall()
                return self.response(start,200,{'jobs':[json.loads(r['data']) for r in rows]})
            if method!='GET':return self.response(start,404,{'error':'Route not found.'})
            if path in ('/','/editor/','/editor/index.html'):return self.static(start,self.source/'editor/index.html')
            if path in ['/editor/'+n for n in ('app.js','model.js','bridge.js','style.css')]:return self.static(start,self.source/path[1:])
            if path.startswith('/site/assets/'):return self.static(start,self.publisher.repo/'assets'/path[len('/site/assets/'):])
            if path in ('/site/favicon.png','/site/apple-touch-icon.png'):return self.static(start,self.publisher.repo/path.split('/')[-1])
            if path.startswith('/site/') and path[6:] in PUBLIC_FILES:return self.static(start,self.state/'preview'/path[6:])
            if path.startswith('/staging'):
                relative=path[len('/staging'):].lstrip('/') or 'index.html'
                if relative not in PUBLIC_FILES and not re.fullmatch(r'assets/[\w./-]+',relative):return self.response(start,404,{'error':'Page not found.'})
                active=self.publisher.active()
                if not active:return self.response(start,503,{'error':'No verified staging build is available yet.'})
                file=self.publisher.releases/active/relative
                if file.suffix=='.html' and file.is_file():
                    text=file.read_text().replace('<head>','<head><base href="/staging/">',1)
                    text=text.replace('<body','<body',1).replace('</body>','<div style="position:fixed;top:0;left:0;right:0;z-index:2147483647;background:#482477;color:white;text-align:center;padding:9px;font:14px system-ui">Our Little Village staging · not the live website</div></body>')
                    return self.response(start,200,text,'text/html')
                return self.static(start,file)
            return self.response(start,404,{'error':'Page not found.'})
        except Limited as e:return self.response(start,429,{'error':str(e)})
        except Denied as e:return self.response(start,403,{'error':str(e)})
        except Conflict as e:return self.response(start,409,{'error':str(e)})
        except Invalid as e:return self.response(start,400,{'error':str(e)})
        except Exception:return self.response(start,500,{'error':'The staging service could not complete this request. Your local draft is still available.'})

def configured_app():
    mode=os.environ.get('OLV_PUBLISH_MODE','local-staging');origin=os.environ.get('OLV_EDITOR_ORIGIN','http://127.0.0.1:4180')
    github=None
    if mode=='github-staging':github=GitHubApp(os.environ.get('OLV_GITHUB_APP_ID',''),os.environ.get('OLV_GITHUB_INSTALLATION_ID',''),os.environ.get('OLV_GITHUB_PRIVATE_KEY_FILE',''))
    return App(state=os.environ.get('OLV_STATE_DIR'),origin=origin,mode=mode,github=github)

if __name__=='__main__':
    from wsgiref.simple_server import make_server, WSGIRequestHandler
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIServer
    class Server(ThreadingMixIn,WSGIServer):daemon_threads=True
    class Quiet(WSGIRequestHandler):
        def log_message(self,*args):pass
    app=configured_app();port=urlsplit(app.origin).port or 4180
    print('Protected staff staging: '+app.origin+' · production publishing disabled',flush=True)
    with make_server('127.0.0.1',port,app,server_class=Server,handler_class=Quiet) as server:server.serve_forever()
