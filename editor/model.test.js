import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {validate,recover,imageType,displayText,changesList} from './model.js';
const boot=JSON.parse(execFileSync('python3',['-c','from serve import prepare; import json; print(json.dumps(prepare()))'],{cwd:import.meta.dirname,encoding:'utf8'}));
test('every registered field accepts its baseline and rejects type confusion',()=>{
  for(const [page,p]of Object.entries(boot.pages))for(const f of p.fields){const v=f.path.slice(1).split('/').reduce((o,k)=>o[k],p.content);validate(boot,page,f.path,v);assert.throws(()=>validate(boot,page,f.path,{}));}
});
test('protects destinations, CSS, new arrays, other pages and prototype paths',()=>{
  for(const path of ['/buttons/0/to','/sections/0/cards/0/wide','/gallery/99/image','/__proto__','/heading/x','/contact'])assert.throws(()=>validate(boot,'parties',path,'changed'));
  assert.throws(()=>validate(boot,'contact','/heading','changed'));
});
test('plain text and accent boundaries reject arbitrary HTML and invalid input',()=>{
  validate(boot,'parties','/heading','Birthday *Magic*');
  for(const value of ['','   ','<img src=x onerror=alert(1)>','Unclosed *accent','x'.repeat(4001)])assert.throws(()=>validate(boot,'parties','/heading',value));
  assert.equal(displayText('< & *Party*',true),'&lt; &amp; <em>Party</em>');
  assert.equal(displayText('*not an accent*',false),'*not an accent*');
});
test('images require library membership or validated local draft identifier',()=>{
  for(const value of ['https://evil.example/a.jpg','javascript:alert(1)','/assets/work/../../secret.png','data:image/svg+xml,<svg/>','draft:missing'])assert.throws(()=>validate(boot,'parties','/photo/image',value));
  validate(boot,'parties','/photo/image','draft:test',{'draft:test':{}});
});
test('binary image signatures distinguish genuine photo formats from renamed files',()=>{
  assert.equal(imageType([255,216,255,0]),'image/jpeg');
  assert.equal(imageType([137,80,78,71,13,10,26,10]),'image/png');
  assert.equal(imageType([...Buffer.from('RIFF1234WEBP')]),'image/webp');
  for(const b of [[],[255],Buffer.from('<svg/>'),Buffer.from('not a jpeg')])assert.throws(()=>imageType(b));
});
test('draft recovery retains edits, refuses stale baselines and forbidden paths',()=>{
  const saved={version:1,baseHash:boot.baseHash,changes:{'parties|/heading':'Birthday *Magic*'},media:{}};
  assert.deepEqual(recover(boot,saved).changes,saved.changes);
  assert.throws(()=>recover(boot,{...saved,baseHash:'old'}));
  assert.throws(()=>recover(boot,{...saved,changes:{'parties|/buttons/0/to':'evil'}}));
  assert.throws(()=>recover(boot,{...saved,media:{'draft:x':{data:'data:image/svg+xml,<svg/>'}}}));
  const list=changesList(boot,saved.changes);assert.equal(list[0].before,'Birthday *Parties*');assert.equal(list[0].value,'Birthday *Magic*');
});

test('video types, byte limits, duration and playable dimensions are enforced',async()=>{
  const {videoType,checkVideoFile,checkVideoMetadata,MAX_VIDEO_BYTES}=await import('./model.js');
  const mp4=Uint8Array.from([0,0,0,20,...Buffer.from('ftypisom'),0,0,0,0,...Buffer.from('mp42')]);
  assert.equal(videoType(mp4),'video/mp4');
  assert.equal(checkVideoFile(mp4.length,'video/mp4',mp4),'video/mp4');
  assert.throws(()=>checkVideoFile(MAX_VIDEO_BYTES+1,'video/mp4',mp4));
  assert.throws(()=>checkVideoFile(0,'video/mp4',mp4));
  assert.throws(()=>checkVideoFile(mp4.length,'video/webm',mp4));
  const mov=Uint8Array.from([0,0,0,20,...Buffer.from('ftypqt  '),0,0,0,0,...Buffer.from('qt  ')]);
  for(const bytes of [mov,Buffer.from('<svg>'),[255,216,255],[]])assert.throws(()=>videoType(bytes));
  assert.equal(videoType([0x1a,0x45,0xdf,0xa3,...Buffer.from('1234webm1234')]),'video/webm');
  assert.throws(()=>videoType([0x1a,0x45,0xdf,0xa3,...Buffer.from('matroska1234')]));
  checkVideoMetadata({duration:8,width:1080,height:1920});
  for(const meta of [{duration:121,width:1920,height:1080},{duration:Infinity,width:1,height:1},{duration:10,width:0,height:0},{duration:1,width:7680,height:4320}])assert.throws(()=>checkVideoMetadata(meta));
});
test('video drafts recover with exact bindings and reject cross-kind or unsafe media',()=>{
  const mp4=Buffer.from([0,0,0,20,...Buffer.from('ftypisom'),0,0,0,0,...Buffer.from('mp42')]);
  const entry={kind:'video',mime:'video/mp4',data:'data:video/mp4;base64,'+mp4.toString('base64')};
  validate(boot,'private-events','/video','draft:loop',{'draft:loop':entry});
  validate(boot,'home','/panels/private/video','/assets/work/art.mp4');
  assert.throws(()=>validate(boot,'private-events','/photo/image','draft:loop',{'draft:loop':entry}));
  assert.throws(()=>validate(boot,'private-events','/video','/assets/work/private-a.jpg'));
  assert.throws(()=>validate(boot,'home','/video','draft:loop',{'draft:loop':entry}));
  const saved={version:1,baseHash:boot.baseHash,changes:{'private-events|/video':'draft:loop'},media:{'draft:loop':entry}};
  assert.equal(recover(boot,saved).changes['private-events|/video'],'draft:loop');
  assert.throws(()=>recover(boot,{...saved,media:{'draft:loop':{...entry,data:'data:video/mp4;base64,'+Buffer.from('not a video').toString('base64')}}}));
  assert.throws(()=>recover(boot,{...saved,media:{'draft:loop':{...entry,data:entry.data.replace('video/mp4','video/webm')}}}));
});
