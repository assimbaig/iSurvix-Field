(() => {
  'use strict';
  const carousel=document.querySelector('.home-showcase');if(!carousel)return;
  const slides=[...carousel.querySelectorAll('.showcase-slide')],selectors=[...carousel.querySelectorAll('[data-slide]')];
  const pause=carousel.querySelector('#showcase-pause'),status=carousel.querySelector('#showcase-status');
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let current=0,stopped=reduced,hovered=false,inView=true,lastChange=Date.now(),startX=null;
  function updatePause(){pause.setAttribute('aria-pressed',String(stopped));pause.setAttribute('aria-label',stopped?'Play automatic slides':'Pause automatic slides');pause.textContent=stopped?'▶':'Ⅱ';}
  function select(index,manual=false){current=(index+slides.length)%slides.length;slides.forEach((slide,i)=>{slide.hidden=i!==current;});selectors.forEach((button,i)=>button.setAttribute('aria-current',String(i===current)));lastChange=Date.now();if(manual){stopped=true;updatePause();status.textContent=slides[current].getAttribute('aria-label');}}
  carousel.querySelector('[data-map-interaction]').addEventListener('pointerdown',()=>{stopped=true;updatePause();});
  selectors.forEach((button,index)=>button.addEventListener('click',()=>select(index,true)));
  carousel.querySelector('#showcase-prev').addEventListener('click',()=>select(current-1,true));carousel.querySelector('#showcase-next').addEventListener('click',()=>select(current+1,true));
  pause.addEventListener('click',()=>{stopped=!stopped;lastChange=Date.now();updatePause();});
  carousel.addEventListener('mouseenter',()=>hovered=true);carousel.addEventListener('mouseleave',()=>hovered=false);
  carousel.addEventListener('keydown',event=>{if(event.target.closest('[data-map-interaction]'))return;if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();select(current+(event.key==='ArrowRight'?1:-1),true);selectors[current].focus();}});
  carousel.addEventListener('touchstart',event=>{if(event.target.closest('[data-map-interaction]')){startX=null;return;}startX=event.touches.length===1?event.touches[0].clientX:null;},{passive:true});
  carousel.addEventListener('touchend',event=>{if(startX===null)return;const delta=event.changedTouches[0].clientX-startX;startX=null;if(Math.abs(delta)>65)select(current+(delta<0?1:-1),true);},{passive:true});
  if('IntersectionObserver' in window)new IntersectionObserver(entries=>{inView=entries[0].isIntersecting;},{threshold:.25}).observe(carousel);
  setInterval(()=>{if(stopped||hovered||!inView||document.hidden||carousel.contains(document.activeElement)){lastChange=Date.now();return;}if(Date.now()-lastChange>8000)select(current+1);},500);
  updatePause();
})();
