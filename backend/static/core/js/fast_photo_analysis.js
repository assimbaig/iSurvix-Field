/* Batched visual retrieval stays separate from detailed verification and approval. */
(()=>{'use strict';
const api=window.photoWorkspace,panel=document.getElementById('fast-photo-panel');if(!api||!panel)return;
const el=id=>document.getElementById(id),node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;};
let page=1,pages=1,loading=false,last='',saving=false;
async function refresh(force=false){
 if(loading||saving||document.hidden&&!force)return;loading=true;
 try{
  const fast=await api.request('fast-state/?page='+page);panel.hidden=!fast.enabled;if(!fast.enabled)return;
  const data=api.getState(),photos=new Map((data.photos||[]).map(p=>[p.id,p])),fields=new Map((data.field_catalog||[]).map(f=>[f.id,f]));
  pages=fast.pages;page=fast.page;
  const bar=el('fast-photo-progress');bar.value=fast.total?Math.floor(fast.ready/fast.total*100):0;
  const verified=(data.analysis?.analyzed_photo_ids||[]).length;
  el('fast-photo-status').textContent=fast.runtime?.error||('Fast AI Analysis: '+fast.ready+' / '+fast.total+' photos · Detailed verification: '+verified+' / '+fast.total+(fast.ready===fast.total?' · Suggestions ready for inspection.':' · Preparing suggestions...'));
  el('fast-photo-page').textContent='Page '+page+' / '+pages;el('fast-photo-prev').disabled=page<=1;el('fast-photo-next').disabled=page>=pages;
  const signature=JSON.stringify([fast.results,data.schema_digest,[...fields.values()].filter(f=>f.locked).map(f=>f.id),(data.mappings||[]).filter(m=>fast.results.some(r=>r.photo_id===m.photo_id)).map(m=>[m.field_id,m.status])]);
  if(!force&&signature===last)return;last=signature;
  const root=el('fast-photo-results');root.replaceChildren();
  for(const result of fast.results){
   const photo=photos.get(result.photo_id);if(!photo)continue;
   const card=node('article'),title=node('h3',photo.filename),image=node('img');image.src=photo.preview_url;image.alt=photo.filename;image.loading='lazy';
   const view=node('button','Inspect photo');view.type='button';view.onclick=()=>{api.selectPhoto(photo.id);document.getElementById('photo-viewer')?.scrollIntoView({block:'center',behavior:'smooth'});};
   card.append(title,image,view,node('p','Similar checklist subjects · unverified'));
   const list=node('ul');
   for(const match of result.candidates){const field=fields.get(match.field_id);if(!field)continue;
    const rejected=(data.mappings||[]).some(m=>m.photo_id===photo.id&&m.field_id===field.id&&m.status==='rejected');
    list.append(node('li',field.label+' · similarity '+Number(match.similarity).toFixed(2)+(rejected?' · previously rejected':'')));
   }
   if(!list.children.length)list.append(node('li','No close subject found. Select a checklist point after inspecting the original.'));card.append(list);
   if(!api.readOnly){
    const label=node('label','Checklist point'),select=node('select');select.id='fast-photo-field-'+photo.id;label.htmlFor=select.id;select.append(new Option('Choose after inspecting this photo',''));
    for(const field of fields.values()){if(!field.locked)select.append(new Option(field.section_title+' / '+field.label,field.id));}
    const button=node('button','Confirm inspected photo link');button.type='button';button.disabled=true;
    select.onchange=()=>{button.disabled=!select.value;};
    button.onclick=async()=>{
     if(saving||!select.value)return;saving=true;button.disabled=true;
     try{await api.request('mapping/',{expected_schema_digest:data.schema_digest,decisions:[{photo_id:photo.id,field_id:select.value,action:'manual'}]});api.message('Your inspected photo link was saved. Checklist answers and approvals are unchanged.');await api.refresh();last='';}
     catch(error){api.message(error.message);}finally{saving=false;await refresh(true);}
    };
    card.append(label,select,button);
   }
   root.append(card);
  }
  if(!root.children.length)root.append(node('p',fast.total?'The local worker is preparing fast photo suggestions.':'Upload photos to start AI Analysis.'));
 }catch(error){panel.hidden=false;el('fast-photo-status').textContent='Fast AI Analysis unavailable: '+error.message+' Refresh to retry. Detailed verification remains available.';}
 finally{loading=false;}
}
el('fast-photo-refresh').onclick=()=>refresh(true);el('fast-photo-prev').onclick=()=>{if(page>1){page--;refresh(true);}};el('fast-photo-next').onclick=()=>{if(page<pages){page++;refresh(true);}};
document.addEventListener('photo-state',()=>refresh());refresh();setInterval(refresh,3000);
})();
