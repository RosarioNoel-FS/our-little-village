"""Independent server validation: the browser's registry and media metadata are never trusted."""
import base64, copy, hashlib, io, json, math, re, subprocess, tempfile, warnings
from pathlib import Path
from PIL import Image

class Invalid(ValueError): pass
class Conflict(Invalid): pass
MAX_BODY=110*1024*1024
MAX_IMAGE=5*1024*1024
MAX_VIDEO=20*1024*1024

def strict_json(data):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise Invalid('Duplicate JSON keys are not accepted.')
            out[k]=v
        return out
    try:return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Invalid('Invalid number.')))
    except (ValueError,UnicodeError) as e:raise Invalid('Invalid JSON request.') from e

def set_path(doc,path,value):
    parts=path[1:].split('/');node=doc
    for k in parts[:-1]:node=node[int(k)] if isinstance(node,list) else node[k]
    key=parts[-1]
    if isinstance(node,list):node[int(key)]=value
    else:node[key]=value

def media_bytes(entry,kind):
    if not isinstance(entry,dict) or not isinstance(entry.get('data'),str):raise Invalid('Missing uploaded media.')
    data=entry['data'];limit=MAX_VIDEO if kind=='video' else MAX_IMAGE
    if len(data)>math.ceil(limit/3)*4+100:raise Invalid('Uploaded media is too large.')
    match=re.fullmatch(r'data:(image/(?:jpeg|png|webp)|video/(?:mp4|webm));base64,([A-Za-z0-9+/]+=*)',data)
    if not match or not match[1].startswith(kind if kind=='video' else 'image'):raise Invalid('Uploaded media type does not match the selected field.')
    try:raw=base64.b64decode(match[2],validate=True)
    except ValueError as e:raise Invalid('Invalid uploaded media encoding.') from e
    if not raw or len(raw)>limit:raise Invalid('Uploaded media is empty or too large.')
    mime=match[1]
    if kind=='image':
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as im:
                    expected={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}.get(im.format)
                    if expected!=mime or min(im.size)<20 or im.width*im.height>50_000_000:raise Invalid('Choose a genuine JPEG, PNG or WebP photo between 20 pixels and 50 megapixels.')
                    im.verify()
                with Image.open(io.BytesIO(raw)) as im:im.load()
        except Exception as e:raise Invalid('The photo could not be decoded safely.') from e
    else:validate_video(raw,mime)
    ext={'image/jpeg':'jpg','image/png':'png','image/webp':'webp','video/mp4':'mp4','video/webm':'webm'}[mime]
    return raw,ext

def validate_video(raw,mime):
    if mime=='video/mp4':
        if len(raw)<16 or raw[4:8]!=b'ftyp' or not re.fullmatch(rb'(isom|iso[2-9]|mp4[12]|avc1|M4V |dash)',raw[8:12]):raise Invalid('Choose a genuine MP4 with H.264 video.')
    elif not(raw[:4]==bytes([0x1a,0x45,0xdf,0xa3]) and b'webm' in raw[:4096]):raise Invalid('Choose a genuine WebM video.')
    with tempfile.TemporaryDirectory() as td:
        file=Path(td)/('clip.mp4' if mime=='video/mp4' else 'clip.webm');file.write_bytes(raw)
        try:
            p=subprocess.run(['ffprobe','-v','error','-protocol_whitelist','file','-show_format','-show_streams','-of','json',str(file)],capture_output=True,timeout=12,check=True)
            info=json.loads(p.stdout);streams=[s for s in info['streams'] if s.get('codec_type')=='video']
            if len(streams)!=1:raise Invalid('The clip must contain exactly one video stream.')
            v=streams[0];w=int(v.get('width',0));h=int(v.get('height',0));duration=float(info['format'].get('duration',v.get('duration',0)))
            codecs=['h264'] if mime=='video/mp4' else ['vp8','vp9','av1']
            if v.get('codec_name') not in codecs or not math.isfinite(duration) or not 0<duration<=120 or min(w,h)<1 or max(w,h)>3840 or w*h>3840*2160:raise Invalid('Use a playable MP4 (H.264) or WebM, at most 2 minutes and 4K.')
            subprocess.run(['ffmpeg','-v','error','-nostdin','-protocol_whitelist','file','-i',str(file),'-frames:v','1','-f','null','-'],capture_output=True,timeout=15,check=True)
        except Invalid:raise
        except Exception as e:raise Invalid('The video could not be decoded. Export as MP4 (H.264) or WebM.') from e

def validate_draft(boot,payload,revision=None):
    if not isinstance(payload,dict):raise Invalid('Expected a draft object.')
    if set(payload)-{'version','baseHash','changes','media','page','selected','pending','savedAt','revision','requestId'}:raise Invalid('Unexpected request fields.')
    if payload.get('version')!=1:raise Invalid('Unsupported draft version.')
    if payload.get('baseHash')!=boot['baseHash']:raise Conflict('Website content has changed. Download your draft, then refresh and review it.')
    if revision is not None and payload.get('revision')!=revision:raise Conflict('The staging version has changed. Refresh before publishing.')
    changes=payload.get('changes',{});uploads=payload.get('media',{})
    if not isinstance(changes,dict) or not isinstance(uploads,dict) or len(changes)>1000 or len(uploads)>100:raise Invalid('Invalid or oversized draft.')
    docs={k:copy.deepcopy(p['content']) for k,p in boot['pages'].items()};files={};used=set();totals={'image':0,'video':0};decoded={}
    for field_key,value in changes.items():
        if not isinstance(field_key,str) or field_key.count('|')!=1 or not isinstance(value,str):raise Invalid('Invalid editable field.')
        page,path=field_key.split('|');p=boot['pages'].get(page)
        field=next((f for f in p['fields'] if f['path']==path),None) if p else None
        if not field:raise Invalid('This field is protected or does not exist.')
        kind=field['kind']
        if kind in ('image','video'):
            if value.startswith('draft:'):
                if not re.fullmatch(r'draft:[a-z0-9-]{1,80}',value) or value not in uploads:raise Invalid('Missing uploaded media.')
                if value in decoded:
                    previous_kind,media_path=decoded[value]
                    if previous_kind!=kind:raise Invalid('Media types cannot be mixed.')
                else:
                    raw,ext=media_bytes(uploads[value],kind);totals[kind]+=len(raw)
                    media_path='/assets/work/olv-'+hashlib.sha256(raw).hexdigest()+'.'+ext
                    files[media_path.lstrip('/')]=raw;decoded[value]=(kind,media_path)
                used.add(value);value=media_path
            elif value not in boot['videos' if kind=='video' else 'media']:raise Invalid('Only approved site media can be used.')
        else:
            if not value.strip() or len(value)>field['maxLength'] or any(ord(c)<32 and c not in '\n\r\t' for c in value):raise Invalid('Text is empty, too long or contains unsupported characters.')
            if re.search(r'</?[a-z][^>]*>',value,re.I):raise Invalid('Use plain text rather than HTML.')
            if field['accent'] and value.count('*')%2:raise Invalid('Accent words need matching stars.')
        set_path(docs[page],path,value)
    if set(uploads)!=used:raise Invalid('Unreferenced uploads are not accepted.')
    if totals['image']>16*1024*1024 or totals['video']>60*1024*1024:raise Invalid('This draft contains too much media.')
    # Preserve original JSON structure and unknown fields, including absent optional video defaults.
    for page,p in boot['pages'].items():
        relevant=[k for k in changes if k.startswith(page+'|')]
        if not relevant:continue
        original=copy.deepcopy(p.get('rawContent',p['content']))
        for k in relevant:
            path=k.split('|')[1];value=docs[page]
            for part in path[1:].split('/'):value=value[int(part)] if isinstance(value,list) else value[part]
            set_path(original,path,value)
        files[p['source']]=(json.dumps(original,ensure_ascii=False,indent=2)+'\n').encode()
    return files
