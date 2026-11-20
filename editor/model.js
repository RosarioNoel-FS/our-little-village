export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const MAX_TOTAL_BYTES = 16 * 1024 * 1024;
export const MAX_VIDEO_BYTES = 20 * 1024 * 1024;
export const MAX_VIDEO_TOTAL_BYTES = 60 * 1024 * 1024;
export const MAX_VIDEO_SECONDS = 120;
export function mediaKind(m) { return m?.kind || (m?.mime?.startsWith('video/') || m?.data?.startsWith('data:video/') ? 'video' : 'image'); }
export function checkVideoFile(size,mime,bytes) {
  if(!size || size>MAX_VIDEO_BYTES) throw Error('Choose a video up to 20 MB. Short clips work best.');
  const actual=videoType(bytes);
  if(mime && mime!==actual) throw Error('This file’s contents do not match its video type. Export it as MP4 (H.264) or WebM.');
  return actual;
}
export function checkVideoMetadata({duration,width,height}) {
  if(!Number.isFinite(duration)||duration<=0||duration>MAX_VIDEO_SECONDS) throw Error('Choose a video no longer than 2 minutes.');
  if(!width||!height||width>3840||height>3840||width*height>3840*2160) throw Error('Choose a playable video up to 4K resolution. Audio-only files are not supported.');
}
export function videoType(bytes) {
  const b=new Uint8Array(bytes), ascii=(a,z)=>String.fromCharCode(...b.slice(a,z));
  if(b.length>=16 && ascii(4,8)==='ftyp') {
    const size=new DataView(b.buffer,b.byteOffset,b.byteLength).getUint32(0);
    if(size>=16 && size<=b.length && /^(isom|iso[2-9]|mp4[12]|avc1|M4V |dash)$/.test(ascii(8,12))) return 'video/mp4';
  }
  if(b.length>=12 && [0x1a,0x45,0xdf,0xa3].every((v,i)=>b[i]===v) && ascii(4,Math.min(b.length,4096)).includes('webm')) return 'video/webm';
  throw Error('Please choose an MP4 (H.264) or WebM video. MOV and other formats need to be exported first.');
}
export function get(doc, path) { return path.slice(1).split('/').reduce((v,k)=>v[k],doc); }
export function fieldFor(boot,page,path) { return boot.pages[page]?.fields.find(f=>f.path===path); }
export function validate(boot,page,path,value,media={}) {
  const f=fieldFor(boot,page,path);
  if(!f) throw Error('This part of the website is protected.');
  if(typeof value!=='string') throw Error('Please enter text.');
  if(f.kind==='image'||f.kind==='video') {
    const library=f.kind==='video'?(boot.videos||[]):boot.media;
    const draft=Object.hasOwn(media,value) && /^draft:[a-z0-9-]+$/.test(value) && mediaKind(media[value])===f.kind;
    if(!library.includes(value) && !draft) throw Error(f.kind==='video'?'Choose an existing video or upload a new MP4 or WebM video.':'Choose a photo from the library or upload a new photo.');
  } else {
    if(f.required && !value.trim()) throw Error('Please enter some words before applying.');
    if(value.length>f.maxLength) throw Error(`Please use ${f.maxLength} characters or fewer.`);
    if(/<\/?[a-z][^>]*>/i.test(value)) throw Error('Please use plain text. HTML is not supported.');
    if(f.accent && value.split('*').length%2===0) throw Error('Add a closing * after the accent words.');
  }
  return f;
}
export function imageType(bytes) {
  const b=new Uint8Array(bytes);
  if(b.length>=3 && b[0]===255 && b[1]===216 && b[2]===255) return 'image/jpeg';
  if(b.length>=8 && [137,80,78,71,13,10,26,10].every((v,i)=>b[i]===v)) return 'image/png';
  if(b.length>=12 && String.fromCharCode(...b.slice(0,4))==='RIFF' && String.fromCharCode(...b.slice(8,12))==='WEBP') return 'image/webp';
  throw Error('Please choose a JPEG, PNG or WebP photo.');
}
export function escapeText(s) { return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
export function displayText(s,accent) { const safe=escapeText(s); return accent?safe.replace(/\*(.+?)\*/g,'<em>$1</em>'):safe; }
export function key(page,path) { return page+'|'+path; }
export function changesList(boot,changes) {
  return Object.entries(changes).map(([k,value])=>{
    const [page,path]=k.split('|'), f=fieldFor(boot,page,path);
    return {page,path,value,before:get(boot.pages[page].content,path),...f};
  });
}
export function recover(boot,saved) {
  if(!saved || saved.version!==1 || saved.baseHash!==boot.baseHash) throw Error('This draft belongs to an earlier website version. Download it for safekeeping before starting a new draft.');
  const changes=saved.changes||{}, media=saved.media||{};
  if(Object.keys(changes).length>2000 || Object.keys(media).length>100) throw Error('This draft is too large.');
  let imageTotal=0,videoTotal=0;
  for(const [id,m] of Object.entries(media)) {
    if(!/^draft:[a-z0-9-]+$/.test(id) || typeof m?.data!=='string' || !/^data:(image\/(jpeg|png|webp)|video\/(mp4|webm));base64,[A-Za-z0-9+/]+=*$/.test(m.data)) throw Error('A saved photo or video could not be recovered.');
    const kind=mediaKind(m),limit=kind==='video'?MAX_VIDEO_BYTES:MAX_IMAGE_BYTES;
    if(m.data.length>Math.ceil(limit/3)*4+100) throw Error('A saved photo or video is too large.');
    const bytes=Uint8Array.from(atob(m.data.split(',')[1]),c=>c.charCodeAt(0));
    const mime=kind==='video'?videoType(bytes):imageType(bytes);
    if(bytes.length>limit || !m.data.startsWith('data:'+mime+';')) throw Error('A saved photo or video is invalid or too large.');
    m.bytes=bytes.length;m.kind=kind;m.mime=mime;
    if(kind==='video')videoTotal+=bytes.length;else imageTotal+=bytes.length;
  }
  if(imageTotal>MAX_TOTAL_BYTES || videoTotal>MAX_VIDEO_TOTAL_BYTES) throw Error('The saved photos or videos are too large.');
  for(const [k,v] of Object.entries(changes)) { const [page,path,...extra]=k.split('|'); if(extra.length) throw Error('Invalid draft field.'); validate(boot,page,path,v,media); }
  return {changes,media};
}
