import {get,fieldFor,validate,key,changesList,recover,imageType,MAX_IMAGE_BYTES,MAX_TOTAL_BYTES,MAX_VIDEO_BYTES,MAX_VIDEO_TOTAL_BYTES,mediaKind,checkVideoFile,checkVideoMetadata,escapeText as esc} from './model.js';
const $=id=>document.getElementById(id), frame=$('preview');
let boot,db,page='parties',selected='',changes={},media={},history=[],pending=null,saveTimer,saveChain=Promise.resolve(),saveFailed=false,saving=0,recoveryRaw,confirmAction;
let frameReady=false,toastTimer;
const toast=s=>{$('toast').textContent=s;$('toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('visible'),4500);};
const value=(p,path)=>Object.hasOwn(changes,key(p,path))?changes[key(p,path)]:get(boot.pages[p].content,path);
const photoURL=v=>v?.startsWith('draft:')?media[v]?.data:'/site/'+v?.replace(/^\//,'');
function openDB(){return new Promise((res,rej)=>{const req=indexedDB.open(boot?.auth?.user?'olv-visual-editor-'+boot.auth.user.id:'olv-visual-editor',1);req.onupgradeneeded=()=>req.result.createObjectStore('drafts');req.onsuccess=()=>res(req.result);req.onerror=()=>rej(req.error);});}
function readDB(){return new Promise((res,rej)=>{const req=db.transaction('drafts').objectStore('drafts').get('current');req.onsuccess=()=>res(req.result);req.onerror=()=>rej(req.error);});}
function writeDB(data){return new Promise((res,rej)=>{const tx=db.transaction('drafts','readwrite');tx.objectStore('drafts').put(data,'current');tx.oncomplete=res;tx.onerror=()=>rej(tx.error);tx.onabort=()=>rej(tx.error);});}
function snapshot(){const used=new Set(Object.values(changes).filter(v=>v.startsWith?.('draft:')));return {version:1,baseHash:boot.baseHash,changes:{...changes},media:Object.fromEntries(Object.entries(media).filter(([id])=>used.has(id))),page,selected,pending:pending?{...pending}:null,savedAt:new Date().toISOString()};}
function save(){
  clearTimeout(saveTimer);saveTimer=null;saving++;$('saveStatus').textContent='Saving draft on this computer…';
  const data=snapshot();
  saveChain=saveChain.catch(()=>{}).then(()=>writeDB(data)).then(()=>{saveFailed=false;$('saveStatus').textContent='Draft saved on this computer';}).catch(()=>{saveFailed=true;$('saveStatus').textContent='Draft could not be saved. Download a backup.';toast('Browser storage is unavailable or full. Download your draft from Review changes.');});
  saveChain=saveChain.finally(()=>saving--);return saveChain;
}
function scheduleSave(){ $('saveStatus').textContent='Saving draft on this computer…';clearTimeout(saveTimer);saveTimer=setTimeout(save,250); }
function updateCount(){const n=Object.keys(changes).length;$('count').textContent=n;$('undo').disabled=history.length===0;}
function send(scrollTo){if(!frameReady)return;const fields=boot.pages[page].fields;const values={};for(const f of fields)values[f.path]=value(page,f.path);frame.contentWindow.postMessage({olvEditor:true,type:'update',fields:fields.map(f=>({...f,original:get(boot.pages[page].content,f.path)})),values,media:Object.fromEntries(Object.entries(media).filter(([id])=>Object.values(values).includes(id))),selected,highlight:$('highlights').checked,scrollTo},location.origin);}
function loadPage(next){page=next;selected='';pending=null;frameReady=false;$('page').value=page;$('previewName').textContent=boot.pages[page].name;frame.src='/site/'+boot.pages[page].file;renderPanel();scheduleSave();}
function checkpoint(){history.push({changes:{...changes},media:{...media}});if(history.length>30)history.shift();}
function commit(edits){for(const [path,v] of edits)validate(boot,page,path,v,media);checkpoint();for(const [path,v] of edits){const k=key(page,path);if(v===get(boot.pages[page].content,path))delete changes[k];else changes[k]=v;}pending=null;updateCount();send();scheduleSave();}
function discardPending(){if(!pending)return Promise.resolve(true);return ask('Leave this unfinished edit?','The words in the editing box have not been applied to the preview. Leave this edit and keep the rest of your saved draft?','Leave this edit').then(yes=>{if(yes)pending=null;return yes;});}
function ask(title,text,button='Discard changes'){return new Promise(res=>{$('confirmTitle').textContent=title;$('confirmText').textContent=text;$('confirmYes').textContent=button;confirmAction=res;$('confirmDialog').showModal();});}
$('confirmYes').onclick=()=>{$('confirmDialog').close();confirmAction?.(true);confirmAction=null;};
$('confirmCancel').onclick=()=>{$('confirmDialog').close();confirmAction?.(false);confirmAction=null;};
$('confirmDialog').addEventListener('cancel',()=>{confirmAction?.(false);confirmAction=null;});
function picker(){return `<details class="field-picker"><summary>Find something to edit</summary><label class="field-label" for="fieldSearch">Search words, photos or videos</label><input id="fieldSearch" type="search" placeholder="For example, party or photo"><div id="fieldList" class="field-list"></div></details>`;}
function bindPicker(){const list=$('fieldList');function draw(){const q=$('fieldSearch').value.toLowerCase();list.replaceChildren();boot.pages[page].fields.filter(f=>f.kind!=='alt'&&(!q||f.label.toLowerCase().includes(q)||value(page,f.path).toLowerCase().includes(q))).forEach(f=>{const b=document.createElement('button');b.type='button';b.innerHTML=`${esc(f.label)}<small>${f.kind==='image'?'Photo':f.kind==='video'?'Looping video':esc(value(page,f.path).replace(/\*/g,''))}</small>`;b.onclick=()=>choose(f.path,true);list.append(b);});if(!list.childElementCount)list.textContent='No matching words, photos or videos on this page.';}draw();$('fieldSearch').oninput=draw;}
async function choose(path,scroll=false){if(pending && selected!==path && !(await discardPending()))return;selected=path;renderPanel();send(scroll?path:undefined);scheduleSave();if(matchMedia('(max-width:720px)').matches)$('panel').scrollIntoView({behavior:'smooth',block:'start'});else $('editText')?.focus();}
function renderPanel(){
  const f=fieldFor(boot,page,selected),panel=$('panel');
  if(!f){panel.innerHTML=`<div class="welcome-icon" aria-hidden="true">✎</div><p class="eyebrow">A LITTLE CHANGE, MADE EASY</p><h2>Your website.<br>Your words.</h2><p class="intro">Click words, a photo or a looping video in the preview to make a change.</p><div class="tip"><strong>Try it:</strong> click the big heading, type something new, then choose “Apply to preview.”</div><p class="field-help">Layout, colors, contact details and the opening film are protected, so you can focus on your content.</p>${picker()}`;bindPicker();return;}
  panel.innerHTML=`<button class="back" id="done">Done editing</button><p class="eyebrow">${f.kind==='video'?'REPLACE A VIDEO':f.kind==='image'?'REPLACE A PHOTO':'EDIT YOUR WORDS'}</p><h2>${esc(f.kind==='video'?'Keep the village moving.':f.kind==='image'?'Picture this.':'Make it your own.')}</h2><p class="field-help">${esc(f.label)}</p><div id="fieldControls"></div>${picker()}`;
  $('done').onclick=async()=>{if(await discardPending()){selected='';renderPanel();send();scheduleSave();}};
  if(f.kind==='video')renderVideo(f);else if(f.kind==='image') renderImage(f); else renderText(f);
  bindPicker();
}
function renderText(f){
  const p=pending?.page===page&&pending.path===f.path?pending.value:value(page,f.path);
  $('fieldControls').innerHTML=`<label class="field-label" for="editText">${f.kind==='alt'?'Describe the photo':'Your words'}</label><textarea id="editText" maxlength="${f.maxLength}" spellcheck="true"></textarea><p class="field-help">${f.accent?'Put *stars* around words for the existing accent style. Example: Birthday *Parties*.':'Plain text keeps the website’s existing style.'}</p><p id="fieldError" class="error" role="alert"></p><div class="field-actions"><button id="apply" class="primary">Apply to preview</button><button id="revert">Revert</button></div><p class="fine">Applied changes save automatically in this browser.</p>`;
  $('editText').value=p;$('editText').oninput=()=>{pending={page,path:f.path,value:$('editText').value};$('fieldError').textContent='';$('revert').disabled=false;scheduleSave();};
  $('apply').onclick=()=>{try{commit([[f.path,$('editText').value]]);toast('Applied to your local preview.');renderPanel();}catch(e){$('fieldError').textContent=e.message;}};
  $('editText').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')$('apply').click();};
  $('revert').disabled=!Object.hasOwn(changes,key(page,f.path))&&!pending;
  $('revert').onclick=()=>{commit([[f.path,get(boot.pages[page].content,f.path)]]);renderPanel();toast('Original words restored.');};
}
function renderImage(f){
  const alt=value(page,f.altPath),curr=value(page,f.path);
  $('fieldControls').innerHTML=`<div class="image-fit" id="photoFit"><img id="selectedPhoto" alt="Selected photo preview"></div><div class="fit-switch" role="group" aria-label="Photo inspection"><button id="crop" aria-pressed="true">Crop view</button><button id="full" aria-pressed="false">Full photo</button></div><p class="fine">The website keeps its original photo shape. Check the photo in the page for its actual crop.</p><button class="primary upload" id="upload">Choose a photo from this computer</button><input id="photoFile" type="file" accept="image/jpeg,image/png,image/webp" hidden><p class="fine">JPEG, PNG or WebP · up to 5 MB per photo</p><p id="imageError" class="error" role="alert"></p><details class="library"><summary>Or choose from existing photos</summary><div id="libraryGrid" class="library-grid"></div></details><label class="field-label" for="editText">Describe this photo</label><textarea class="alt" id="editText" maxlength="500"></textarea><p class="field-help">One short sentence for people using screen readers.</p><p id="fieldError" class="error" role="alert"></p><div class="field-actions"><button class="primary" id="apply">Apply description</button><button id="revert">Revert photo & description</button></div>`;
  $('selectedPhoto').src=photoURL(curr);$('editText').value=pending?.page===page&&pending.path===f.altPath?pending.value:alt;
  $('editText').oninput=()=>{pending={page,path:f.altPath,value:$('editText').value};$('revert').disabled=false;scheduleSave();};
  $('apply').onclick=()=>{try{commit([[f.altPath,$('editText').value]]);toast('Photo description saved in your draft.');renderPanel();}catch(e){$('fieldError').textContent=e.message;}};
  $('full').onclick=()=>{$('photoFit').classList.add('contain');$('full').setAttribute('aria-pressed','true');$('crop').setAttribute('aria-pressed','false');};
  $('crop').onclick=()=>{$('photoFit').classList.remove('contain');$('full').setAttribute('aria-pressed','false');$('crop').setAttribute('aria-pressed','true');};
  $('upload').onclick=()=>$('photoFile').click();
  $('photoFile').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{
    if(file.size>MAX_IMAGE_BYTES)throw Error('That photo is over 5 MB. Please choose a smaller version.');
    const bytes=await file.arrayBuffer(),mime=imageType(bytes);
    if(file.type&&file.type!==mime)throw Error('This file’s contents do not match its photo type. Please choose another photo.');
    const data=await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=()=>rej(Error('That photo could not be read.'));r.readAsDataURL(new Blob([bytes],{type:mime}));});
    const img=new Image();img.src=data;await img.decode();
    if(img.naturalWidth<20||img.naturalHeight<20||img.naturalWidth*img.naturalHeight>50000000)throw Error('Choose a photo between 20 pixels and 50 megapixels.');
    const used=new Set(Object.values(changes));const total=Object.entries(media).filter(([id,m])=>used.has(id)&&mediaKind(m)==='image').reduce((n,[,m])=>n+(m.bytes||0),file.size);
    if(total>MAX_TOTAL_BYTES)throw Error('This draft has too many large photos. Download a backup, then try smaller photos.');
    const id='draft:'+crypto.randomUUID();media[id]={data,name:file.name,bytes:file.size,width:img.naturalWidth,height:img.naturalHeight,mime};
    replacePhoto(f,id);toast('Photo replaced in your local preview. Check its crop and description.');
  }catch(err){$('imageError').textContent=err.message;}};
  const grid=$('libraryGrid');[...boot.media,...Object.keys(media).filter(id=>mediaKind(media[id])==='image')].forEach(src=>{const b=document.createElement('button');b.type='button';b.setAttribute('aria-label','Use '+(media[src]?.name||src.split('/').pop()));b.setAttribute('aria-pressed',String(src===curr));const img=document.createElement('img');img.loading='lazy';img.src=photoURL(src);img.alt=media[src]?.name||src.split('/').pop();b.append(img);b.onclick=()=>replacePhoto(f,src);grid.append(b);});
  $('revert').disabled=![f.path,f.altPath].some(path=>Object.hasOwn(changes,key(page,path)))&&!pending;
  $('revert').onclick=()=>{commit([[f.path,get(boot.pages[page].content,f.path)],[f.altPath,get(boot.pages[page].content,f.altPath)]]);renderPanel();toast('Original photo and description restored.');};
}
function replacePhoto(f,src){const edits=[[f.path,src]];if(pending?.path===f.altPath)edits.push([f.altPath,pending.value]);try{commit(edits);renderPanel();}catch(e){$('fieldError').textContent=e.message;}}
function probeVideo(source){return new Promise((resolve,reject)=>{
  const v=document.createElement('video');v.muted=true;v.playsInline=true;v.preload='auto';
  const timer=setTimeout(()=>finish(Error('This video took too long to load. Try a shorter MP4 (H.264) clip.')),15000);
  function finish(error){clearTimeout(timer);const result={duration:v.duration,width:v.videoWidth,height:v.videoHeight};v.onloadeddata=null;v.onerror=null;v.pause();v.removeAttribute('src');v.load();if(error)reject(error);else resolve(result);}
  v.onloadeddata=()=>{try{checkVideoMetadata({duration:v.duration,width:v.videoWidth,height:v.videoHeight});finish();}catch(e){finish(e);}};
  v.onerror=()=>finish(Error('This video cannot play in this browser. Export as MP4 with H.264 video, or WebM.'));
  v.src=source;v.load();
});}
async function inspectSavedMedia(m){
  if(mediaKind(m)==='video'){const meta=await probeVideo(m.data);Object.assign(m,meta);}
  else{const img=new Image();img.src=m.data;await img.decode();if(img.naturalWidth*img.naturalHeight>50000000)throw Error('A saved photo is too large.');}
}
function renderVideo(f){
  const curr=value(page,f.path),current=media[curr];
  $('fieldControls').innerHTML=`<div class="video-inspect"><video id="selectedVideo" controls muted loop playsinline preload="metadata" aria-label="Selected looping video preview"></video></div><button id="playVideo" class="full-width">Play video preview</button><p class="fine" id="videoInfo"></p><button class="primary upload" id="uploadVideo">Replace video</button><input id="videoFile" type="file" accept="video/mp4,video/webm,.mp4,.webm" hidden><p class="fine">MP4 (H.264) or WebM · up to 20 MB · 2 minutes maximum. Short clips work best. The website keeps the same looping, muted video shape.</p><p id="videoStatus" class="field-help" role="status"></p><p id="videoError" class="error" role="alert"></p><details class="library"><summary>Or choose an existing video</summary><div id="videoLibrary" class="video-library"></div></details><div class="field-actions"><button id="revertVideo" class="full-width">Revert to original video</button></div><p class="fine">Video changes save only in this browser. The opening film and contact-page video remain protected.</p>`;
  const player=$('selectedVideo');player.src=photoURL(curr);player.muted=true;player.loop=true;player.playsInline=true;
  player.onloadedmetadata=()=>{if($('selectedVideo')!==player)return;$('videoInfo').textContent=`${player.videoWidth} × ${player.videoHeight} · ${Math.round(player.duration)} seconds${current?' · '+(current.bytes/1024/1024).toFixed(1)+' MB':''}`;};
  player.onerror=()=>{if($('selectedVideo')!==player)return;$('videoError').textContent='This video could not play. Choose another MP4 (H.264) or WebM clip, or revert.';};
  player.onplay=()=>{if($('selectedVideo')!==player)return;$('playVideo').textContent='Pause video preview';};player.onpause=()=>{if($('selectedVideo')!==player)return;$('playVideo').textContent='Play video preview';};
  $('playVideo').onclick=()=>{if(player.paused)player.play().catch(()=>$('videoError').textContent='Playback could not start. Try another video.');else player.pause();};
  $('uploadVideo').onclick=()=>$('videoFile').click();
  $('videoFile').onchange=async e=>{
    const file=e.target.files[0];if(!file)return;
    const targetPage=page,targetPath=f.path,button=$('uploadVideo');let objectURL;
    button.disabled=true;$('videoError').textContent='';$('videoStatus').textContent='Checking video format and playback…';
    try{
      if(!/\.(mp4|webm)$/i.test(file.name))throw Error('Choose an MP4 or WebM file. Export MOV videos to MP4 first.');
      if(file.size>MAX_VIDEO_BYTES||!file.size)throw Error('Choose a video up to 20 MB. Short clips work best.');
      const bytes=await file.arrayBuffer(),mime=checkVideoFile(file.size,file.type,bytes);
      objectURL=URL.createObjectURL(new Blob([bytes],{type:mime}));const meta=await probeVideo(objectURL);
      const used=new Set(Object.entries(changes).filter(([k])=>k!==key(targetPage,targetPath)).map(([,v])=>v));
      const total=Object.entries(media).filter(([id,m])=>used.has(id)&&mediaKind(m)==='video').reduce((sum,[,m])=>sum+m.bytes,file.size);
      if(total>MAX_VIDEO_TOTAL_BYTES)throw Error('This draft has over 60 MB of videos. Use smaller clips or revert another video first.');
      const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('This video could not be read.'));reader.readAsDataURL(new Blob([bytes],{type:mime}));});
      if(page!==targetPage||selected!==targetPath){toast('Video selection changed while loading. Choose the clip again.');return;}
      const id='draft:'+crypto.randomUUID();media[id]={kind:'video',data,mime,name:file.name,bytes:file.size,...meta};
      commit([[targetPath,id]]);renderPanel();toast('Video replaced in your local preview. Your live website is unchanged.');
    }catch(err){if($('videoError'))$('videoError').textContent=err.message;}
    finally{if(objectURL)URL.revokeObjectURL(objectURL);if(button.isConnected)button.disabled=false;if($('videoStatus'))$('videoStatus').textContent='';}
  };
  const library=$('videoLibrary');[...(boot.videos||[]),...Object.keys(media).filter(id=>mediaKind(media[id])==='video')].forEach(src=>{
    const b=document.createElement('button');b.type='button';b.textContent=media[src]?.name||src.split('/').pop();b.setAttribute('aria-label','Use video '+b.textContent);b.setAttribute('aria-pressed',String(src===curr));
    b.onclick=async()=>{const targetPage=page,targetPath=selected;b.disabled=true;try{await probeVideo(photoURL(src));if(page!==targetPage||selected!==targetPath)return;commit([[f.path,src]]);renderPanel();toast('Existing video applied to your local preview.');}catch(e){$('videoError').textContent=e.message;b.disabled=false;}};library.append(b);
  });
  $('revertVideo').disabled=!Object.hasOwn(changes,key(page,f.path));$('revertVideo').onclick=()=>{commit([[f.path,get(boot.pages[page].content,f.path)]]);renderPanel();toast('Original looping video restored.');};
}

function renderReview(){
  const list=changesList(boot,changes),pages=new Set(list.map(c=>c.page));$('reviewIntro').textContent=list.length?`${list.length} change${list.length===1?'':'s'} across ${pages.size} page${pages.size===1?'':'s'}. ${boot.auth?'These are draft changes. Publishing updates staging only.':'These changes are saved only on this computer.'}`:'Your website preview matches the original. Try editing a heading or replacing a photo.';
  $('reviewList').replaceChildren();$('discardAll').disabled=!list.length;$('export').disabled=!list.length&&!pending;if($('staffPublish'))$('staffPublish').disabled=!list.length;
  if(!list.length)$('reviewList').innerHTML='<div class="empty-review">No applied changes yet.</div>';
  if(pending){const p=document.createElement('p');p.className='callout';p.textContent='There are unfinished words in the editing box. Apply them to include them in the preview. They are saved for recovery in this browser.';$('reviewList').append(p);}
  for(const c of list){const div=document.createElement('article');div.className='review-item';div.innerHTML=`<p class="eyebrow">${esc(boot.pages[c.page].name)}</p><h3>${esc(c.label)}</h3>`;
    if(c.kind==='video'){const videos=document.createElement('div');videos.className='review-videos';for(const [v,label]of [[c.before,'Original video'],[c.value,'Draft video']]){const box=document.createElement('div'),caption=document.createElement('p'),clip=document.createElement('video');caption.textContent=label;clip.controls=true;clip.muted=true;clip.loop=true;clip.playsInline=true;clip.preload='metadata';clip.src=photoURL(v);clip.setAttribute('aria-label',label);box.append(caption,clip);videos.append(box);}div.append(videos);}else if(c.kind==='image'){const photos=document.createElement('div');photos.className='review-photo';for(const [v,label] of [[c.before,'Original photo'],[c.value,'Draft photo']]){const im=document.createElement('img');im.src=photoURL(v);im.alt=label;photos.append(im);}div.append(photos);}else{for(const [v,cls,label] of [[c.before,'before','Original'],[c.value,'after','Draft']]){const p=document.createElement('p');p.className=cls;p.textContent=label+': '+v;div.append(p);}}
    const b=document.createElement('button');b.textContent='Revert this change';b.onclick=()=>{checkpoint();delete changes[key(c.page,c.path)];updateCount();send();renderPanel();scheduleSave();renderReview();};div.append(b);$('reviewList').append(div);
  }
}
function download(data,name){const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
$('page').onchange=async()=>{const next=$('page').value;if(await discardPending())loadPage(next);else $('page').value=page;};
$('desktop').onclick=()=>setSize(false);$('mobile').onclick=()=>setSize(true);
function resizePreview(){const wrap=$('frameWrap'),width=wrap.classList.contains('mobile')?390:1280,scale=wrap.clientWidth/width;frame.style.width=width+'px';frame.style.height=(wrap.clientHeight/scale)+'px';frame.style.transform='scale('+scale+')';}
new ResizeObserver(resizePreview).observe($('frameWrap'));
function setSize(mobile){$('frameWrap').classList.toggle('mobile',mobile);requestAnimationFrame(resizePreview);$('desktop').setAttribute('aria-pressed',String(!mobile));$('mobile').setAttribute('aria-pressed',String(mobile));$('previewSize').textContent=mobile?'Mobile · 390 px':'Desktop · 1280 px';}
$('highlights').onchange=()=>send();
$('undo').onclick=async()=>{if(!(await discardPending()))return;const prev=history.pop();if(!prev)return;changes=prev.changes;media=prev.media;updateCount();send();renderPanel();scheduleSave();toast('Last change undone.');};
$('reviewDialog').addEventListener('close',()=>{$('reviewList').querySelectorAll('video').forEach(v=>v.pause());});
$('review').onclick=()=>{renderReview();$('reviewDialog').showModal();};$('help').onclick=()=>$('helpDialog').showModal();
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
$('restore').onclick=()=>$('draftFile').click();
$('draftFile').onchange=async e=>{
  const file=e.target.files[0];if(!file)return;
  try{
    if(file.size>110*1024*1024)throw Error('This backup is too large.');
    const saved=JSON.parse(await file.text()),restored=recover(boot,saved);
    for(const m of Object.values(restored.media))await inspectSavedMedia(m);
    if(!(await ask('Restore this draft backup?','This replaces the current browser draft with the backup. Your live website will stay the same.','Restore backup')))return;
    checkpoint();changes=restored.changes;media=restored.media;pending=null;
    const target=boot.pages[saved.page]?saved.page:page;loadPage(target);updateCount();send();await save();renderReview();toast('Draft backup restored on this computer.');
  }catch(err){toast('Backup could not be restored. '+err.message);}finally{$('draftFile').value='';}
};
$('export').onclick=()=>download(snapshot(),'our-little-village-draft-'+new Date().toISOString().slice(0,10)+'.json');
$('discardAll').onclick=async()=>{if(await ask('Discard all your changes?','This removes all applied changes and unfinished words from this browser. The original website preview will return.')){checkpoint();changes={};media={};pending=null;updateCount();send();renderPanel();save();renderReview();toast('All changes discarded.');}};
$('recoveryDialog').addEventListener('cancel',e=>e.preventDefault());
$('downloadRecovery').onclick=()=>download(recoveryRaw,'our-little-village-recovered-draft.json');
$('startFresh').onclick=async()=>{if(await ask('Start a fresh draft?','Download the previous draft first if you want to keep it. Starting fresh replaces this browser’s saved draft.','Start fresh')){changes={};media={};pending=null;recoveryRaw=null;$('recoveryDialog').close();await save();}};
addEventListener('message',async e=>{if(e.origin!==location.origin||e.source!==frame.contentWindow||!e.data?.olvEditor)return;const m=e.data;if(m.type==='ready'){frameReady=true;send();}if(m.type==='select')choose(m.path);if(m.type==='locked')toast('That link is protected. Choose a page from the editor’s page menu.');if(m.type==='video-error')toast('A video could not play. Replace it with MP4 (H.264) or WebM, or revert.');if(m.type==='video-autoplay-blocked')toast('Automatic playback is paused. Use Play video preview in the controls.');if(m.type==='image-error')toast('A photo could not load. Choose a different photo or revert it.');});
addEventListener('beforeunload',e=>{if(saveTimer||saveFailed||saving){save();e.preventDefault();e.returnValue='';}});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&boot&&!recoveryRaw)save();});
async function init(){try{
  const r=await fetch('/api/bootstrap');if(r.status===401){location.assign('/signin');return;}if(!r.ok)throw Error('Could not load the website.');boot=await r.json();configureStaff();
  for(const [id,p] of Object.entries(boot.pages)){const o=document.createElement('option');o.value=id;o.textContent=p.name;$('page').append(o);}$('page').disabled=false;
  let stored;
  try{db=await openDB();stored=await readDB();}catch{saveFailed=true;$('saveStatus').textContent='Storage unavailable. Download draft backups.';}
  if(stored){try{
    const recovered=recover(boot,stored);changes=recovered.changes;media=recovered.media;
    // Decode recovered photo data before allowing it into the preview.
    for(const m of Object.values(media))await inspectSavedMedia(m);
    if(boot.pages[stored.page])page=stored.page;
    if(fieldFor(boot,page,stored.selected))selected=stored.selected;
    if(stored.pending){const p=stored.pending;if(fieldFor(boot,p.page,p.path)&&typeof p.value==='string'&&p.value.length<=4000){pending=p;page=p.page;selected=p.path.endsWith('/alt')?p.path.replace(/\/alt$/,'/image'):p.path;}}
    if(Object.keys(changes).length||pending)toast('Your saved draft has been recovered. Nothing is live.');
  }catch(e){changes={};media={};pending=null;recoveryRaw=stored;$('recoveryText').textContent=e.message;$('recoveryDialog').showModal();}}
  const restoredSelected=selected,restoredPending=pending;loadPage(page);selected=restoredSelected;pending=restoredPending;renderPanel();updateCount();
  if(recoveryRaw){clearTimeout(saveTimer);saveTimer=null;$('saveStatus').textContent='Previous draft kept for recovery.';}else if(db)await save();
}catch(e){$('panel').innerHTML=`<h2>The preview could not load.</h2><p class="error">${esc(e.message)}</p><p>Refresh this page, or restart the preview using the included instructions.</p>`;$('saveStatus').textContent='Preview unavailable.';}}
let activePublish=null,publishTimer;
async function api(path,method='GET',body){
 const r=await fetch(path,{method,headers:{'Content-Type':'application/json',...(method==='GET'?{}:{'X-CSRF-Token':boot.auth.csrf})},...(body?{body:JSON.stringify(body)}:{})});const data=await r.json();
 if(!r.ok)throw Error(r.status===401?'Your session expired. Download your local draft and sign in again.':data.error||'The staging service could not complete this request.');return data;
}
function configureStaff(){
 if(!boot.auth)return;
 document.body.classList.add('staff-mode');
 document.querySelector('.draft-badge').textContent=boot.publishing.local?'Staff staging · on this Mac':'Staff staging · production protected';
 const actions=document.querySelector('.top-actions'),logout=document.createElement('button');logout.textContent='Sign out';logout.className='quiet';logout.onclick=async()=>{await save();try{await api('/api/auth/logout','POST',{});location.assign('/signin');}catch(e){toast(e.message);}};actions.prepend(logout);const historyButton=document.createElement('button');historyButton.textContent='Staging history';historyButton.className='quiet staff-history';historyButton.onclick=async()=>{$('publishStatus').textContent='Choose an earlier verified staging version to restore.';$('publishDialog').showModal();$('releaseHistory').click();try{const result=await api('/api/jobs');if(result.jobs.length)showJob(result.jobs[0]);}catch(e){toast(e.message);}};actions.prepend(historyButton);
 const button=$('publishButton');button.textContent='Review & publish to staging';button.disabled=false;button.onclick=()=>{renderReview();$('reviewDialog').showModal();};
 $('publishReason').textContent='Signed in as '+boot.auth.user.name+'. Publishing updates staging only. The live website is protected.';
 for(const id of ['staffSave','staffLoad','staffPublish'])$(id).hidden=false;
 $('staffSave').onclick=async()=>{try{await api('/api/draft','PUT',snapshot());toast('Draft saved to your staff account. Nothing has been published.');}catch(e){toast(e.message);}};
 $('staffLoad').onclick=async()=>{try{const result=await api('/api/draft');if(!result.draft){toast('There is no saved staff draft yet.');return;}const resultDraft=recover(boot,result.draft);for(const m of Object.values(resultDraft.media))await inspectSavedMedia(m);if(!(await ask('Open your saved staff draft?','This replaces your current local draft with the saved staff draft.','Open staff draft')))return;checkpoint();changes=resultDraft.changes;media=resultDraft.media;pending=null;updateCount();send();renderPanel();scheduleSave();renderReview();toast('Your saved staff draft is open.');}catch(e){toast(e.message);}};
 $('staffPublish').onclick=async()=>{
   if(pending){toast('Apply or revert the unfinished edit before publishing.');return;}
   if(!(await ask('Publish these changes to staging?','Only the separate Our Little Village staging site will change. Your live website will remain the same.','Publish to staging')))return;
   try{const payload={...snapshot(),revision:boot.revision,requestId:crypto.randomUUID()};$('staffPublish').disabled=true;const job=await api('/api/publish','POST',payload);$('reviewDialog').close();$('publishDialog').showModal();activePublish=job.id;showJob(job);pollPublish();}catch(e){toast(e.message);$('staffPublish').disabled=false;}
 };
 $('refreshContent').onclick=async()=>{if(Object.keys(changes).length&&!await ask('Refresh from the staging version?','Download a backup first if you want to keep this local draft. The editor will load the latest staging content.','Refresh from staging'))return;clearTimeout(saveTimer);saveTimer=null;await saveChain;await writeDB(null);saveFailed=false;boot=null;location.reload();};
 $('releaseHistory').onclick=async()=>{try{const result=await api('/api/releases');const list=$('releaseList');list.replaceChildren();for(const [i,release]of result.releases.entries()){const b=document.createElement('button');b.textContent=release.active?'Current staging version':'Restore earlier version '+(i+1);b.disabled=release.active;b.onclick=async()=>{if(!await ask('Restore this staging version?','The earlier editable content will become a new staging update. The live website will remain the same.','Restore staging version'))return;try{const job=await api('/api/restore','POST',{revision:release.revision,expectedRevision:result.revision,requestId:crypto.randomUUID()});activePublish=job.id;showJob(job);pollPublish();}catch(e){toast(e.message);}};list.append(b);}}catch(e){toast(e.message);}};
 api('/api/jobs').then(r=>{const job=r.jobs.find(j=>['queued','validating','committing','awaiting-build','building'].includes(j.state));if(job){activePublish=job.id;$('publishDialog').showModal();showJob(job);pollPublish();}}).catch(()=>{});
}
function showJob(job){$('publishStatus').textContent=job.message;$('stagingLink').hidden=job.state!=='published-staging';if(job.state==='published-staging'){$('stagingLink').href=job.url;$('refreshContent').textContent='Load the published staging content';}}
async function pollPublish(){if(!activePublish)return;clearTimeout(publishTimer);try{const job=await api('/api/jobs/'+activePublish);showJob(job);if(['published-staging','failed','conflict'].includes(job.state)){activePublish=null;return;}}catch(e){$('publishStatus').textContent=e.message;}publishTimer=setTimeout(pollPublish,3000);}
init();
