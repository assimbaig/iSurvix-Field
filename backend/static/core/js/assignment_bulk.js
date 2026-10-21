(() => {
  'use strict';
  let catalog=[];try{catalog=JSON.parse(document.getElementById('bulk-catalog').textContent)||[];}catch{}
  const select=document.getElementById('bulk-project'),root=document.getElementById('bulk-field-catalog');
  function render(){root.replaceChildren();for(const project of catalog.filter(p=>!select.value||String(p.project_id)===select.value)){const section=document.createElement('section'),title=document.createElement('h3');title.textContent=project.project_name;section.append(title);for(const field of project.fields){const row=document.createElement('p'),code=document.createElement('code');row.textContent=field.label;code.textContent=field.id+' · '+field.type;row.append(code);section.append(row);}root.append(section);}}
  select.addEventListener('change',render);render();
  document.getElementById('bulk-download-template').onclick=()=>{if(!select.value){select.focus();select.setCustomValidity('Choose a project before downloading its CSV template.');select.reportValidity();return}select.setCustomValidity('');window.location.assign(document.getElementById('bulk-download-template').dataset.sampleUrl+'?project='+encodeURIComponent(select.value));};
})();
