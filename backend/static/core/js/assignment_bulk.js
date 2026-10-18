(() => {
  'use strict';
  let catalog=[];try{catalog=JSON.parse(document.getElementById('bulk-catalog').textContent)||[];}catch{}
  const select=document.getElementById('bulk-project'),root=document.getElementById('bulk-field-catalog');
  function render(){root.replaceChildren();for(const project of catalog.filter(p=>!select.value||String(p.project_id)===select.value)){const section=document.createElement('section'),title=document.createElement('h3');title.textContent=project.project_name;section.append(title);for(const field of project.fields){const row=document.createElement('p'),code=document.createElement('code');row.textContent=field.label;code.textContent=field.id+' · '+field.type;row.append(code);section.append(row);}root.append(section);}}
  select.addEventListener('change',render);render();
  document.getElementById('bulk-download-template').onclick=()=>{const project=catalog.find(p=>String(p.project_id)===select.value),headers=['project','engineer','site_id','latitude','longitude','description',...(project?.fields||[]).map(f=>f.id)];const csv=headers.map(x=>'"'+x.replaceAll('"','""')+'"').join(',')+'\r\n';const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='site-assignment-template.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
})();
