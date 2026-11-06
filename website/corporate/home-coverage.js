(() => {
  'use strict';
  document.querySelectorAll('.coverage-service').forEach(service => {
    const tabs=[...service.querySelectorAll('[role="tab"]')];
    const panels=[...service.querySelectorAll('[role="tabpanel"]')];
    const state=service.querySelector('.coverage-image-state');
    const photo=service.querySelector('.coverage-media>img');
    function choose(index,focus=false){
      service.dataset.activeStep=String(index);
      tabs.forEach((tab,i)=>{tab.setAttribute('aria-selected',String(i===index));tab.tabIndex=i===index?0:-1;});
      panels.forEach((panel,i)=>panel.hidden=i!==index);
      if(photo.getAttribute('src')!==panels[index].dataset.stageImage)photo.setAttribute('src',panels[index].dataset.stageImage);
      photo.setAttribute('alt',panels[index].dataset.stageAlt);
      state.textContent=panels[index].dataset.stageCaption;
      if(focus)tabs[index].focus();
    }
    service.querySelectorAll('[data-coverage-step]').forEach(button=>button.addEventListener('click',()=>choose(Number(button.dataset.coverageStep))));
    tabs.forEach((tab,index)=>tab.addEventListener('keydown',event=>{
      let next=index;
      if(event.key==='ArrowRight')next=(index+1)%tabs.length;
      else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
      else if(event.key==='Home')next=0;
      else if(event.key==='End')next=tabs.length-1;
      else return;
      event.preventDefault();choose(next,true);
    }));
    choose(0);
    service.classList.add('coverage-ready');
  });
})();
