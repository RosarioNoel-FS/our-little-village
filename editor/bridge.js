(()=>{
  // This bridge exists only in generated local preview pages.
  const origin=location.origin;
  try { sessionStorage.setItem('olv-intro','1'); } catch {}
  let registry={}, selected='', highlight=true;
  function send(type,extra={}) { parent.postMessage({olvEditor:true,type,...extra},origin); }
  function mark() {
    document.querySelectorAll('[data-cms]').forEach(el=>{
      const f=registry[el.dataset.cms]; if(!f) return;

      el.tabIndex=el.closest('[aria-hidden="true"]')?-1:0; el.closest('a')?.setAttribute('tabindex','-1'); el.setAttribute('role','button');
      el.setAttribute('aria-label','Edit '+f.label);
      el.title='Click to edit '+f.label;
      el.classList.toggle('cms-selected',el.dataset.cms===selected || el.dataset.cmsAlt===selected);
    });
    document.documentElement.classList.toggle('cms-highlights',highlight);
  }
  addEventListener('message',e=>{
    if(e.origin!==origin||e.source!==parent||!e.data?.olvEditor) return;
    const m=e.data;
    if(m.type==='update') {
      registry=Object.fromEntries(m.fields.map(f=>[f.path,f])); selected=m.selected; highlight=m.highlight;
      document.querySelectorAll('[data-cms-video]').forEach(arch=>{if(arch.querySelector('video'))arch.dataset.cms=arch.dataset.cmsVideo;});
      document.querySelectorAll('video[data-cms]').forEach(v=>{const arch=v.closest('.arch');if(arch){arch.dataset.cms=v.dataset.cms;v.removeAttribute('data-cms');}});
      document.querySelectorAll('[data-cms]').forEach(el=>{
        const path=el.dataset.cms, f=registry[path]; if(!f) return;
        if(Object.hasOwn(m.values,path)) {
          if(f.kind==='video') {
            const player=el.matches('video')?el:el.querySelector('video');if(!player)return;
            if(el.dataset.current===undefined){el.dataset.current=f.original;el.dataset.originalPoster=player.getAttribute('poster')||'';}
            const value=m.values[path];
            if(el.dataset.current!==value){
              const source=value.startsWith('draft:')?m.media[value]?.data:'/site/'+value.replace(/^\//,'');
              if(!source)return;el.dataset.current=value;player.dataset.src=source;player.src=source;
              player.muted=true;player.loop=true;player.playsInline=true;
              if(value===f.original)player.setAttribute('poster',el.dataset.originalPoster);else player.removeAttribute('poster');
              player.load();
              const rect=player.getBoundingClientRect(),visible=rect.bottom>0&&rect.top<innerHeight;
              if(visible&&!document.documentElement.classList.contains('motion-paused')&&!matchMedia('(prefers-reduced-motion: reduce)').matches){player.autoplay=true;player.play()?.catch(()=>send('video-autoplay-blocked'));}else{player.autoplay=false;player.pause();}
            }
          }
          else if(f.kind==='image') { const value=m.values[path]; el.src=value.startsWith('draft:')?m.media[value]?.data:'/site/'+value.replace(/^\//,''); }
          else {
            if(el.dataset.current===undefined)el.dataset.current=f.original;
            if(el.dataset.current===m.values[path])return;
            const str=m.values[path], escaped=str.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
            el.innerHTML=f.accent?escaped.replace(/\*(.+?)\*/g,'<em>$1</em>'):escaped;
            el.dataset.current=str;
            // Original letter animations put an aria-label on a containing heading.
            const heading=el.closest('h1,h2,h3'); if(heading) heading.setAttribute('aria-label',str.replace(/\*/g,''));
          }
        }
        if(el.dataset.cmsAlt && Object.hasOwn(m.values,el.dataset.cmsAlt)) el.alt=m.values[el.dataset.cmsAlt];
      });
      mark();
      if(m.scrollTo) {
        const node=[...document.querySelectorAll('[data-cms]')].find(el=>el.dataset.cms===m.scrollTo||el.dataset.cmsAlt===m.scrollTo);
        node?.scrollIntoView({block:'center',behavior:'smooth'});
      }
    }
  });
  function select(e) {
    const el=e.target.closest('[data-cms]')||e.target.closest('a')?.querySelector('[data-cms]');
    if(el && registry[el.dataset.cms]) { e.preventDefault();e.stopImmediatePropagation();send('select',{path:el.dataset.cms});return true; }
    return false;
  }
  document.addEventListener('click',e=>{
    if(select(e))return;
    const a=e.target.closest('a');
    if(a) {e.preventDefault();e.stopImmediatePropagation();const href=a.getAttribute('href');if(href?.startsWith('#'))document.getElementById(href.slice(1))?.scrollIntoView({behavior:'smooth'});else send('locked');}
  },true);
  document.addEventListener('keydown',e=>{ if((e.key==='Enter'||e.key===' ')&&e.target.closest('[data-cms]')) select(e); },true);
  document.addEventListener('error',e=>{if(e.target.matches?.('img[data-cms]')) send('image-error',{path:e.target.dataset.cms});if(e.target.matches?.('video')&&e.target.closest('[data-cms]'))send('video-error',{path:e.target.closest('[data-cms]').dataset.cms});},true);
  document.addEventListener('DOMContentLoaded',()=>{
    const style=document.createElement('style');
    style.textContent=`[data-cms]{cursor:pointer;scroll-margin:100px}[data-cms]:focus-visible,[data-cms].cms-selected{outline:3px solid #753bda!important;outline-offset:6px!important}.cms-highlights [data-cms]:hover{outline:2px dashed #753bda;outline-offset:5px}span[data-cms]{border-radius:3px}img[data-cms].cms-selected{outline-offset:8px!important}`;
    document.head.append(style); send('ready');
    if(location.pathname.endsWith('index.html')) {
      // Start at the only editable home section. The opening film remains protected.
      document.querySelector('#skip')?.click();
      setTimeout(()=>document.querySelector('#offer')?.scrollIntoView(),200);
    }
  });
})();
