// Optional CMS loop replacement for home panels. Legacy pages omit this script.
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('[data-video-src]').forEach(arch=>{
    const video=arch.querySelector('video'); if(!video)return;
    video.dataset.src=arch.dataset.videoSrc;
    if(video.hasAttribute('src')) {video.src=video.dataset.src;if(!document.documentElement.classList.contains('motion-paused'))video.play()?.catch(()=>{});}
  });
});
