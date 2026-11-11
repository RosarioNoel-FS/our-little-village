/* Pause control for everything that moves on its own. Loaded before the page scripts. */
(function(){
  var root = document.documentElement;
  if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var KEY = 'olv-motion-paused', paused = false;
  try { paused = localStorage.getItem(KEY) === '1'; } catch (e) {}
  root.classList.toggle('motion-paused', paused);

  // Anything that tries to start while paused is stopped straight away. The intro has its own Skip button.
  document.addEventListener('play', function(e){
    if (paused && e.target.id !== 'film') e.target.pause();
  }, true);

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'motion-btn';
  document.body.appendChild(btn);

  function onScreen(v){
    var r = v.getBoundingClientRect();
    return r.bottom > 0 && r.top < window.innerHeight;
  }
  function apply(){
    root.classList.toggle('motion-paused', paused);
    btn.setAttribute('aria-pressed', paused ? 'true' : 'false');
    btn.innerHTML = paused
      ? '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 1.5v9l7-4.5z"/></svg>Play motion'
      : '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 1.5h2.5v9H2.5zM7 1.5h2.5v9H7z"/></svg>Pause motion';
    [].forEach.call(document.querySelectorAll('video'), function(v){
      if (v.id === 'film') return;
      if (paused) { v.pause(); }
      else if (v.getAttribute('src') && onScreen(v)) {
        var p = v.play();
        if (p && p.catch) p.catch(function(){});
      }
    });
  }
  btn.addEventListener('click', function(){
    paused = !paused;
    try { localStorage.setItem(KEY, paused ? '1' : '0'); } catch (e) {}
    apply();
  });
  apply();
})();
