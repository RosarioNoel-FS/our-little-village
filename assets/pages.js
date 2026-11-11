(function(){
  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var LOOK = {
    parties: {word:'Celebrate', colors:['#ffb3cd','#ffffff','#ff5c97','#ffd27a']},
    'private': {word:'Together', colors:['#e8417f','#ffffff','#f58fb4','#d9b24c']},
    toddler: {word:'Play', colors:['#ff5a5f','#2f7bff','#17b897','#ffffff']},
    art: {word:'Create', colors:['#ffd24d','#ff6fb5','#46e8e2','#ffffff']},
    special: {word:'Gather', colors:['#c68cff','#46e8e2','#d9b24c','#78b2ff']},
    balloons: {word:'Balloons', colors:['#ffffff','#f2e6c9','#02403c','#d9b24c']},
    contact: {word:'Hello', colors:['#ff5c97','#46e8e2','#ffd24d','#c68cff']},
    privacy: {word:'Privacy', colors:['#c68cff','#46e8e2','#78b2ff','#ff5c97']}
  };
  var look = LOOK[document.body.getAttribute('data-theme')] || LOOK.parties;
  var made = 0;

  // left %, top %, size px, scroll speed, bob delay, hide on phones
  function balloons(spots){
    return spots.map(function(b, k){
      var c = look.colors[k % look.colors.length], id = 'bal' + (made++);
      return '<div class="bal' + (b[5] ? ' extra' : '') + '" aria-hidden="true" style="--x:' + b[0] + ';--y:' + b[1] + ';--s:' + b[2] + ';--v:' + b[3] + ';--d:' + b[4] + 's">' +
        '<svg viewBox="0 0 100 150"><defs><radialGradient id="' + id + '" cx=".36" cy=".3" r=".82"><stop offset="0" style="stop-color:color-mix(in srgb,' + c + ' 35%,#fff)"/><stop offset=".38" style="stop-color:' + c + '"/><stop offset="1" style="stop-color:color-mix(in srgb,' + c + ' 68%,#000)"/></radialGradient></defs>' +
        '<path d="M50 118c-2 12 6 16 2 30" fill="none" stroke="' + c + '" stroke-opacity=".6" stroke-width="1.2"/><path d="M44 121h12l-4-7h-4Z" fill="' + c + '"/>' +
        '<ellipse cx="50" cy="58" rx="46" ry="57" fill="url(#' + id + ')"/><ellipse cx="33" cy="33" rx="9" ry="15" transform="rotate(24 33 33)" fill="#fff" opacity=".55"/></svg></div>';
    }).join('');
  }

  var hero = document.querySelector('header.panel');
  var statement = document.querySelector('.statement');
  var gallery = document.querySelector('.gallery-wrap');
  if (hero) hero.insertAdjacentHTML('afterbegin', '<div class="ghost" aria-hidden="true">' + look.word + '</div>' +
    balloons([[91,12,170,90,-2.1],[-3,66,130,-110,0,1],[46,84,95,-70,-3.4,1],[93,76,115,120,-1.2,1]]));
  if (statement) statement.insertAdjacentHTML('afterbegin', balloons([[2,22,115,-70,-1,1],[91,14,135,70,-2.6,1]]));
  if (gallery) gallery.insertAdjacentHTML('afterbegin', balloons([[-3,24,135,-120,-1.6,1],[94,8,155,110,-.4,1],[-2,72,100,90,-3,1],[95,64,115,-90,-2.2,1]]));

  var ways = document.querySelector('.ways-wrap');
  var visit = document.querySelector('.visit');
  if (ways) ways.insertAdjacentHTML('afterbegin', balloons([[-3,8,150,-120,-1.2,1],[93,4,170,110,-.4,1],[-2,70,105,90,-3,1],[95,64,125,-90,-2.2,1]]));
  if (visit) visit.insertAdjacentHTML('afterbegin', '<div class="ghost" aria-hidden="true">Visit</div>' + balloons([[92,8,160,90,-1,1],[46,84,95,-70,-2.8,1],[-3,70,120,100,-.2,1]]));

  var STARS = [[50,3],[93,30],[80,86],[18,83],[6,36]];
  [].forEach.call(document.querySelectorAll('.stage'), function(stage){
    stage.insertAdjacentHTML('afterbegin', '<svg class="orbit" viewBox="0 0 100 100" aria-hidden="true">' +
      '<circle cx="50" cy="50" r="47" fill="none" stroke="currentColor" stroke-width=".35"/><circle cx="50" cy="50" r="44" fill="none" stroke="currentColor" stroke-width=".2" stroke-dasharray="1 2.4"/>' +
      STARS.map(function(s){ return '<path transform="translate(' + s[0] + ' ' + s[1] + ')" d="M0-2.6.7-.7 2.6 0 .7.7 0 2.6-.7.7-2.6 0-.7-.7Z" fill="currentColor"/>'; }).join('') + '</svg>');
  });

  var film = document.querySelector('.arch video');
  if (film && !reduced) {
    film.src = film.dataset.src;
    var started = film.play();
    if (started && started.catch) started.catch(function(){});
  }

  // Wrap each word of the big headings so they can write on one by one; <em> accents stay intact.
  if (!reduced) [].forEach.call(document.querySelectorAll('.statement h2,.group-head'), function(h){
    var n = 0;
    (function wrap(node){
      [].slice.call(node.childNodes).forEach(function(c){
        if (c.nodeType === 1) return wrap(c);
        if (c.nodeType !== 3) return;
        var frag = document.createDocumentFragment();
        c.textContent.split(/(\s+)/).forEach(function(part){
          if (!part) return;
          if (/^\s+$/.test(part)) return frag.appendChild(document.createTextNode(part));
          var w = document.createElement('span'), inner = document.createElement('span');
          w.className = 'w'; inner.textContent = part; inner.style.setProperty('--w', n++);
          w.appendChild(inner); frag.appendChild(w);
        });
        c.parentNode.replaceChild(frag, c);
      });
    })(h);
    h.classList.add('split');
  });

  [].forEach.call(document.querySelectorAll('.card'), function(card){
    [].forEach.call(card.children, function(c, j){ c.style.setProperty('--j', j); });
    // soft light that follows the pointer
    card.addEventListener('pointermove', function(ev){
      var r = card.getBoundingClientRect();
      card.style.setProperty('--mx', (ev.clientX - r.left) + 'px');
      card.style.setProperty('--my', (ev.clientY - r.top) + 'px');
    });
  });

  var items = [].slice.call(document.querySelectorAll('.reveal'));
  if ('IntersectionObserver' in window && !reduced) {
    var seen = new IntersectionObserver(function(entries){
      entries.forEach(function(e){ if (e.isIntersecting) { e.target.classList.add('in'); seen.unobserve(e.target); } });
    }, { threshold: .14 });
    items.forEach(function(el){ seen.observe(el); });
  } else {
    items.forEach(function(el){ el.classList.add('in'); });
  }

  if (reduced) return;
  var movers = [].slice.call(document.querySelectorAll('header.panel,.stage,.statement,.gallery-wrap,.ways-wrap,.visit'));
  var queued = false;
  function update(){
    queued = false;
    var vh = window.innerHeight;
    movers.forEach(function(m){
      var r = m.getBoundingClientRect();
      if (r.bottom < -vh * .3 || r.top > vh * 1.3) return;
      var p = Math.max(-1, Math.min(1, (r.top + r.height / 2 - vh / 2) / vh));
      m.style.setProperty('--p', p.toFixed(3));
    });
  }
  function ask(){ if (!queued) { queued = true; requestAnimationFrame(update); } }
  window.addEventListener('scroll', ask, { passive: true });
  window.addEventListener('resize', ask);
  update();
})();
