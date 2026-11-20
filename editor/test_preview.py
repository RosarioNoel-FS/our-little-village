import hashlib, importlib.util, json, os, subprocess, tempfile, unittest
from pathlib import Path
from html.parser import HTMLParser
from serve import ROOT, PREVIEW, prepare, allowed, get

class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boot=prepare()
    def test_all_supported_visible_strings_have_stable_bindings(self):
        def walk(v,path=''):
            if isinstance(v,str): yield path,v
            elif isinstance(v,list):
                for i,x in enumerate(v):yield from walk(x,path+'/'+str(i))
            elif isinstance(v,dict):
                for k,x in v.items():yield from walk(x,path+'/'+k)
        for page,p in self.boot['pages'].items():
            paths={f['path'] for f in p['fields']}
            for path,value in walk(p['content']):
                if value and allowed(page,path):self.assertIn(path,paths,(page,path))
            for path in paths:self.assertTrue(allowed(page,path))
    def test_protected_fields_never_allowed(self):
        for page in self.boot['pages']:
            for path in ['/title','/description','/buttons/0/to','/sections/0/cards/0/wide','/sections/0/cards/0/button/to','/__proto__/image','/photo/image/../../CNAME','/navigation','/video/poster','/contact']:
                self.assertFalse(allowed(page,path),(page,path))
        self.assertFalse(allowed('contact','/heading'))
    def test_images_reference_existing_approved_media_and_exact_alts(self):
        for page,p in self.boot['pages'].items():
            for f in p['fields']:
                if f['kind']=='image':
                    self.assertIn('/'+get(p['content'],f['path']).lstrip('/'),self.boot['media'])
                    self.assertEqual(f['altPath'],f['path'].rsplit('/',1)[0]+'/alt')
                    self.assertTrue((ROOT/get(p['content'],f['path']).lstrip('/')).is_file())
    def test_video_registry_defaults_and_legacy_draft_hash(self):
        raw={}
        for page,p in self.boot['pages'].items():
            raw[page]=json.loads((ROOT/p['source']).read_text())
            fields=[f for f in p['fields'] if f['kind']=='video']
            self.assertEqual(len(fields),6 if page=='home' else 1)
            for f in fields:
                self.assertIn(get(p['content'],f['path']),self.boot['videos'])
                self.assertTrue(allowed(page,f['path']))
        self.assertEqual(self.boot['baseHash'],hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest())
        self.assertFalse(allowed('home','/video'))
        self.assertFalse(allowed('contact','/video'))
    def test_generator_accepts_only_scoped_video_paths_and_renders_replacements(self):
        with tempfile.TemporaryDirectory() as out:
            code = """import runpy,json
D=runpy.run_path(%r)
d=json.load(open(%r));d['video']='/assets/work/art.mp4'
p=D['to_page'](d,'private-events.html','private')
assert 'data-src="assets/work/art.mp4"' in D['page'](p,p)
h=json.load(open(%r));h['panels']['private']['video']='/assets/work/special.mp4'
s=D['what_we_do'](h)
assert 'data-video-src="assets/work/special.mp4"' in s
assert 'assets/video-sources.js' in s
for source in ['https://evil.example/x.mp4','assets/work/../../x.mp4','assets/work/x.mov','javascript:alert(1)']:
 try: D['video'](source)
 except ValueError: pass
 else: raise AssertionError(source)
""" % (str(ROOT/'cms/build.py'),str(ROOT/'content/pages/private-events.json'),str(ROOT/'content/home.json'))
            env=dict(os.environ,OLV_EDITOR_OUTPUT=out);env.pop('OLV_EDITOR_PREVIEW',None)
            result=subprocess.run(['python3','-c',code],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_public_generator_is_byte_identical_to_checked_in_site(self):
        with tempfile.TemporaryDirectory() as output:
            env=dict(os.environ, OLV_EDITOR_OUTPUT=output);env.pop('OLV_EDITOR_PREVIEW',None)
            subprocess.run(['python3',str(ROOT/'cms/build.py')],env=env,check=True,stdout=subprocess.DEVNULL)
            for file in ['index.html','contact.html','privacy.html']+[k+'.html' for k in self.boot['pages'] if k!='home']:
                expected=subprocess.check_output(['git','show','origin/main:'+file],cwd=ROOT)
                self.assertEqual((Path(output)/file).read_bytes(),expected,file)
    def test_preview_does_not_bind_protected_home_or_contact(self):
        s=(PREVIEW/'index.html').read_text();start=s.index('<!-- cms:what-we-do');end=s.index('<!-- /cms:what-we-do')
        self.assertNotIn('data-cms=',s[:start]);self.assertNotIn('data-cms=',s[end:])
        self.assertNotIn('data-cms=',(PREVIEW/'contact.html').read_text())
    def test_existing_image_path_guard_and_html_escaping(self):
        with tempfile.TemporaryDirectory() as out:
            env=dict(os.environ,OLV_EDITOR_OUTPUT=out)
            result=subprocess.run(['python3','-c',f"import runpy; d=runpy.run_path({str(ROOT/'cms/build.py')!r}); assert d['em']('<script>alert(1)</script> *hi*') == '&lt;script&gt;alert(1)&lt;/script&gt; <em>hi</em>'; d['img']('https://evil.example/x.jpg')"],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('unexpected image path',result.stderr)

class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import serve, threading
        from functools import partial
        from http.server import ThreadingHTTPServer
        serve.BOOT=prepare()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(serve.Handler,directory=str(ROOT)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def test_readonly_routes_and_hidden_paths(self):
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError
        for path in ['/','/api/bootstrap','/site/parties.html','/editor/app.js']:
            with urlopen(self.url+path) as r:self.assertEqual(r.status,200)
        for path in ['/.git/config','/site/assets/../../.git/config','/cms/build.py','/content/home.json','/api/publish']:
            with self.assertRaises(HTTPError) as e:urlopen(self.url+path)
            self.assertEqual(e.exception.code,404)
        with self.assertRaises(HTTPError) as e:urlopen(Request(self.url+'/api/publish',data=b'{}',method='POST'))
        self.assertEqual(e.exception.code,501)

if __name__=='__main__':unittest.main()
