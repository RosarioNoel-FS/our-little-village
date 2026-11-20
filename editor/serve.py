"""Read-only localhost preview. No publish, upload, credential or repository-write API."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from html.parser import HTMLParser
import copy, hashlib, json, os, re, subprocess, sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / 'editor' / '.preview'
PAGES = {'home': 'Home · What we do', 'parties': 'Birthday Parties', 'private-events': 'Private Events',
         'toddler-classes': 'Weekly Classes', 'art-classes': 'Creative Arts',
         'special-events': 'Special Events', 'balloons-backdrops': 'GO OLV'}
# Array shape, destinations, SEO, opening film, branding and layout are deliberately locked.
HOME = r'/(heading|intro|panels/(parties|private|toddler|art|special|balloons)/(heading|text|button|video|photo_[12]/(image|alt)))'
CATEGORY = r'/(video|heading|intro|statement|buttons/\d+/label|photo/(image|alt)|gallery/\d+/(image|alt)|sections/\d+/(heading|intro|note|ribbon/\d+|cards/\d+/(tag|title|subtitle|text|facts/\d+/(label|value)|bullets/\d+/(bold|text)|chips/(label|list/\d+)|note/(label|text)|button/label)))'

def allowed(page, path):
    return page in PAGES and bool(re.fullmatch(HOME if page == 'home' else CATEGORY, path))

def get(doc, path):
    for key in path.strip('/').split('/'):
        doc = doc[int(key)] if isinstance(doc, list) else doc[key]
    return doc

class Bindings(HTMLParser):
    def __init__(self):
        super().__init__(); self.paths = set(); self.images = {}; self.videos = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'data-cms-video' in a:
            self.paths.add(a['data-cms-video']); self.videos.add(a['data-cms-video'])
        if 'data-cms' in a:
            self.paths.add(a['data-cms'])
            if tag == 'video': self.videos.add(a['data-cms'])
            if tag == 'img':
                self.paths.add(a['data-cms-alt']); self.images[a['data-cms']] = a['data-cms-alt']

def label(doc, path):
    bits = path.strip('/').split('/')
    names = {'heading':'Heading', 'intro':'Introduction', 'statement':'Big statement', 'tag':'Small label',
             'title':'Title', 'subtitle':'Subtitle', 'text':'Text', 'label':'Label', 'value':'Value',
             'bold':'Bold opening', 'alt':'Photo description', 'image':'Photo', 'button':'Button words',
             'note':'Note', 'photo':'Featured photo', 'photo_1':'First photo', 'photo_2':'Second photo',
             'video':'Looping video', 'list':'Pill', 'ribbon':'Scrolling ribbon', 'chips':'Pill list'}
    context = []
    if 'panels' in bits: context.append(PAGES.get({'private':'private-events','toddler':'toddler-classes','art':'art-classes','special':'special-events','balloons':'balloons-backdrops'}.get(bits[1],bits[1]), bits[1]))
    if 'sections' in bits:
        si = int(bits[1]); section = doc['sections'][si]
        context.append(section.get('heading','').replace('*','') or f'Section {si+1}')
        if 'cards' in bits:
            ci = int(bits[3]); context.append(section['cards'][ci]['title'])
    if bits[0] == 'gallery': context.append(f'Gallery photo {int(bits[1])+1}')
    if bits[0] == 'buttons': context.append(f'Top button {int(bits[1])+1}')
    for key in ['facts','bullets','ribbon','list']:
        if key in bits and bits.index(key)+1 < len(bits) and bits[bits.index(key)+1].isdigit():
            context.append(key.rstrip('s').title()+' '+str(int(bits[bits.index(key)+1])+1))
    leaf = names.get(bits[-1],bits[-1].replace('_',' ').title())
    if bits[-1].isdigit(): leaf = names.get(bits[-2],bits[-2].title())
    if 'note' in bits and len(bits)>2: leaf = 'Note '+leaf.lower()
    if 'chips' in bits and bits[-1]=='label': leaf = 'Pill list heading'
    if 'photo' in bits: leaf = 'Featured '+leaf.lower()
    if 'photo_1' in bits or 'photo_2' in bits: context.append(names[bits[-2]])
    return ' · '.join(context+[leaf])

def prepare(root=None,preview=None):
    ROOT=Path(root or globals()['ROOT'])
    PREVIEW=Path(preview or ROOT/'editor'/'.preview')
    PREVIEW.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ, OLV_EDITOR_PREVIEW='1', OLV_EDITOR_OUTPUT=str(PREVIEW))
    subprocess.run([sys.executable, str(ROOT/'cms/build.py')], env=env, check=True, stdout=subprocess.DEVNULL)
    pages = {}; all_content = {}
    for page, name in PAGES.items():
        file = 'index.html' if page == 'home' else page+'.html'
        source = 'content/home.json' if page == 'home' else 'content/pages/'+page+'.json'
        doc = json.loads((ROOT/source).read_text()); all_content[page] = copy.deepcopy(doc)
        # Optional source fields have legacy defaults; old image/text drafts keep their content hash.
        if page == 'home':
            for clip,panel in doc['panels'].items(): panel.setdefault('video','/assets/work/'+clip+'.mp4')
        else:
            clip={'private-events':'private','toddler-classes':'toddler','art-classes':'art','special-events':'special','balloons-backdrops':'balloons'}.get(page,page)
            doc.setdefault('video','/assets/work/'+clip+'.mp4')
        html = (PREVIEW/file).read_text()
        parser = Bindings(); parser.feed(html)
        fields = []
        for path in sorted(parser.paths):
            if not allowed(page,path): raise ValueError('Unexpected binding: '+page+path)
            value = get(doc,path)
            if not isinstance(value,str): raise ValueError('Non-text binding')
            kind = 'video' if path in parser.videos else 'image' if path in parser.images else 'alt' if path.endswith('/alt') else 'text'
            accent = path.endswith('/heading') or path == '/statement'
            fields.append(dict(path=path, label=label(doc,path), kind=kind, accent=accent,
                               maxLength=500 if kind=='alt' else 4000, required=True,
                               altPath=parser.images.get(path)))
            if kind=='video': fields[-1].update(acceptedTypes=['video/mp4','video/webm'],maxBytes=20*1024*1024,maxDurationSeconds=120,maxPixels=3840*2160)
        pages[page] = dict(name=name, file=file, source=source, content=doc, rawContent=all_content[page], fields=fields)
        # Bridge runs before the original scripts. No source-site code is changed.
        html = html.replace('<head>','<head><base href="/site/"><script src="/editor/bridge.js"></script>',1)
        (PREVIEW/file).write_text(html)
    media = sorted('/assets/work/'+p.name for p in (ROOT/'assets/work').iterdir() if re.fullmatch(r'[\w.-]+\.(jpe?g|png|webp)',p.name,re.I))
    videos = sorted('/assets/work/'+p.name for p in (ROOT/'assets/work').iterdir() if re.fullmatch(r'[\w.-]+\.(mp4|webm)',p.name,re.I))
    digest = hashlib.sha256(json.dumps(all_content, sort_keys=True).encode()).hexdigest()
    return dict(pages=pages, media=media, videos=videos, baseHash=digest, mode='local-draft-only', version=1)

BOOT = None
class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/favicon.ico':
            self.send_response(204);self.end_headers();return
        if path == '/api/bootstrap':
            body = json.dumps(BOOT).encode(); self.send_response(200)
            self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body); return
        # Only explicit preview/static roots. Never expose .git, config, documents or credentials.
        if '..' in path.split('/') or '\\' in path or any(p.startswith('.') for p in path.split('/') if p):
            self.send_error(404); return
        if path in ('/','/editor/','/editor/index.html'):
            target = ROOT/'editor/index.html'
        elif path.startswith('/editor/') and path.split('/')[-1] in ('app.js','style.css','bridge.js','model.js'):
            target = ROOT/'editor'/path.split('/')[-1]
        elif path in ('/site/favicon.png','/site/apple-touch-icon.png'):
            target = ROOT/path.split('/')[-1]
        elif path.startswith('/site/assets/'):
            target = ROOT/'assets'/path[len('/site/assets/'):]
        elif path.startswith('/site/') and path[len('/site/'):] in ['index.html']+[p+'.html' for p in PAGES if p!='home']:
            target = PREVIEW/path[len('/site/'):]
        else:
            self.send_error(404); return
        self.path = '/'+str(target.relative_to(ROOT))
        try: super().do_GET()
        except (BrokenPipeError, ConnectionResetError): pass
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def log_message(self, fmt, *args):
        if len(args)>1 and str(args[1]) != '200': super().log_message(fmt,*args)

if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--port',type=int,default=4173); ap.add_argument('--open',action='store_true'); args=ap.parse_args()
    BOOT=prepare(); os.chdir(ROOT)
    server=ThreadingHTTPServer(('127.0.0.1',args.port), Handler)
    print(f'Our Little Village editor: http://127.0.0.1:{args.port}/ — LOCAL DRAFTS ONLY',flush=True)
    if args.open:
        import threading, webbrowser
        threading.Timer(0.5,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}/')).start()
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
