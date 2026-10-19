(() => {
  'use strict';
  const toggle=document.getElementById('enterprise-nav-toggle'),nav=document.getElementById('role-navigation');
  const narrow=matchMedia('(max-width:980px)');
  function sync(){if(toggle)toggle.setAttribute('aria-expanded',String(narrow.matches?!!nav?.open:!document.body.classList.contains('enterprise-nav-collapsed')));}
  toggle?.addEventListener('click',()=>{if(narrow.matches){if(nav)nav.open=!nav.open;}else{document.body.classList.toggle('enterprise-nav-collapsed');}sync();});
  narrow.addEventListener('change',sync);sync();
  const project=document.getElementById('enterprise-project'),module=document.getElementById('enterprise-module');
  const params=new URLSearchParams(location.search);
  if(project&&params.has('project'))project.value=params.get('project')||'all';
  if(module&&params.has('module'))module.value=params.get('module')||'';
  function navigate(){const url=new URL(document.body.dataset.role==='SUPER_ADMIN'?'/governance/':'/governance/tasks/',location.origin);if(project)url.searchParams.set('project',project.value);if(module?.value){url.searchParams.set('module',module.value);url.searchParams.set('industry',module.selectedOptions[0].dataset.industry);}if(document.body.dataset.role==='SUPER_ADMIN')url.searchParams.set('view','projects');location.assign(url);}
  project?.addEventListener('change',navigate);module?.addEventListener('change',navigate);
  document.querySelectorAll('.platform-nav a').forEach(link=>link.title=link.textContent.trim());
  // Context is navigation only; every destination still enforces its server permissions.
  const user=document.querySelector('.enterprise-user summary')?.textContent.trim()||'';
  const recordId=path=>path.match(/^\/(?:custom-checklist|local\/photos|governance\/activities)\/(\d+)(?:\/|$)/)?.[1];
  const id=recordId(location.pathname),key='isurvix-task-return:'+user+':'+id;
  function safeReturn(value){try{if(!value||value.length>4000)return '';const url=new URL(value,location.origin);return url.origin===location.origin&&url.pathname==='/governance/tasks/'?url.pathname+url.search:'';}catch{return '';}}
  let back=safeReturn(params.get('return_to'));
  if(id){try{if(back)sessionStorage.setItem(key,back);else back=safeReturn(sessionStorage.getItem(key));}catch{}
    if(back){
      const existing=document.getElementById('inspection-return');if(existing)existing.href=back;document.querySelectorAll('[data-task-return]').forEach(link=>link.href=back);
      const crumb=document.querySelector('.enterprise-breadcrumb a[href="/governance/tasks/"]');if(crumb)crumb.href=back;
      const bar=document.createElement('a');bar.href=back;bar.textContent='Back to filtered tasks';bar.className='enterprise-return';document.querySelector('.enterprise-breadcrumb')?.append(bar);
      document.querySelectorAll('a[href]').forEach(link=>{const url=new URL(link.href,location.origin);if(url.origin===location.origin&&recordId(url.pathname)===id&&!url.pathname.includes('/evidence/')&&!url.pathname.includes('/photo/')){url.searchParams.set('return_to',back);link.href=url.pathname+url.search+url.hash;}});
    }
  }
  if(location.pathname==='/governance/tasks/'){
    const scrollKey='isurvix-task-scroll:'+user+':'+location.search;
    try{const previous=JSON.parse(sessionStorage.getItem(scrollKey)||'null');if(previous)requestAnimationFrame(()=>window.scrollTo(previous.x,previous.y));}catch{}
    window.addEventListener('pagehide',()=>{try{sessionStorage.setItem(scrollKey,JSON.stringify({x:scrollX,y:scrollY}));}catch{}});
  }
})();
