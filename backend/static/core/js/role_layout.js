/* Presentation only: no application requests or permission decisions. */
(() => {
  'use strict';
  if (!document.body.classList.contains('role-layout')) return;
  const nav=document.getElementById('role-navigation');
  const narrow=window.matchMedia('(max-width:980px)');
  const adapt=()=>{if(nav)nav.open=!narrow.matches;document.querySelectorAll(".photo-context-details").forEach(details=>details.open=!narrow.matches&&document.body.dataset.layout!=='enterprise');};
  adapt();
  if(narrow.addEventListener)narrow.addEventListener('change',adapt);else narrow.addListener(adapt);
  if(document.getElementById('system-appearance'))return; // Global color-only appearance owns mode and account-scoped storage.
  const root=document.documentElement;
  const appearance=document.getElementById('role-appearance');
  let value='system';
  try {value=localStorage.getItem('role-appearance')||localStorage.getItem('workspace-theme')||localStorage.getItem('photo-theme')||'system';}catch{}
  if(!['light','dark','system'].includes(value))value='system';
  const system=window.matchMedia('(prefers-color-scheme:dark)');
  function apply(next,persist=false){
    value=['light','dark','system'].includes(next)?next:'system';
    root.dataset.roleAppearance=value==='system'?(system.matches?'dark':'light'):value;
    for(const attribute of ['data-workspace-theme','data-photo-theme']){
      if(value==='system')root.removeAttribute(attribute);else root.setAttribute(attribute,value);
    }
    for(const id of ['role-appearance','workspace-theme','photo-theme']){const select=document.getElementById(id);if(select)select.value=value;}
    if(persist)try{for(const key of ['role-appearance','workspace-theme','photo-theme'])localStorage.setItem(key,value);}catch{}
  }
  apply(value);
  for(const id of ['role-appearance','workspace-theme','photo-theme'])document.getElementById(id)?.addEventListener('change',event=>apply(event.target.value,true));
  if(system.addEventListener)system.addEventListener('change',()=>{if(value==='system')apply(value);});
})();
