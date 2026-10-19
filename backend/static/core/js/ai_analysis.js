/* Real worker progress and explicit human matching; no simulated completion. */
(() => {
  'use strict';
  const api=window.photoWorkspace,el=id=>document.getElementById(id);
  if(!api||!el('ai-analysis-progress'))return;
  const dialog=el('ai-matching-dialog');
  let data=api.getState(),photoId=null,fieldId=null,selectionDigest=null,busy=false,opener=null;
  const text=value=>String(value??'').replace(/metadata/gi,'AI Analysis');
  const node=(tag,value)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=text(value);return n;};
  const sources=()=>[...new Map((data.photos||[]).map(p=>[p.id,p])).values()];
  const jobs=()=> (data.jobs||[]).filter(j=>j.current_schema!==false&&['queued','running'].includes(j.status));
  function sets(){
    const ids=new Set(sources().map(p=>p.id)),analyzed=new Set((data.analysis?.analyzed_photo_ids||[]).filter(id=>ids.has(id))),matched=new Set(),confirmed=new Set();
    for(const link of data.mappings||[]){if(!ids.has(link.photo_id))continue;if(['proposed','confirmed','manual'].includes(link.status))matched.add(link.photo_id);if(['confirmed','manual'].includes(link.status))confirmed.add(link.photo_id);}
    const unmatched=new Set([...analyzed].filter(id=>!matched.has(id)));
    return{ids,analyzed,matched,confirmed,unmatched};
  }
  function summary(){
    const s=sets(),total=s.ids.size,active=jobs(),job=active.find(j=>j.status==='running')||active[0];
    const complete=s.analyzed.size,denominator=total;
    const ready=new Set((data.analysis?.workflow?.metadata_ready_photo_ids||[]).filter(id=>s.ids.has(id)));
    let partial=0,label='';
    if(job){partial=job.status==='running'&&job.progress?.stage==='matching_checklist'&&s.ids.has(job.progress?.photo_id)&&!s.analyzed.has(job.progress?.photo_id) ? .5 : 0;label=job.status==='queued'?'Queued - waiting for the local worker':'Running batch: '+(Number(job.completed)||0)+' / '+(Number(job.total)||job.photo_ids?.length||total);}
    // Only durable stages advance progress; elapsed time never simulates work.
    const staged=job?.progress?.pipeline==='dedicated-photo-v1';
    const doneUnits=staged?(ready.size+complete)/2:complete+partial;
    const percent=denominator?Math.min(job?99:100,Math.floor(doneUnits/denominator*100)):0;
    if(!job)label=!total?'Upload photos to start':complete<total?(data.jobs||[]).some(j=>j.current_schema!==false&&j.status==='failed'&&(j.photo_ids||[]).some(id=>s.ids.has(id)&&!s.analyzed.has(id)))?'Stopped — retry failed analysis':'Waiting for analysis':'Complete — review suggested links';
    const bar=el('ai-analysis-progress');bar.max=100;bar.value=percent;bar.setAttribute('aria-valuetext',percent+'% · '+complete+' of '+denominator+' photos · '+label);
    el('ai-analysis-progress-label').textContent=(el('fast-photo-panel')?'Detailed AI verification: ':'AI Analysis: ')+percent+'% · '+complete+' / '+denominator+' photos · '+(staged?'Images analyzed: '+ready.size+' · Checklist comparison: '+complete+' · ':'')+label;
    el('ai-matched-count').textContent='Matched: '+s.matched.size;
    el('ai-mismatched-open').textContent='Mismatched: '+s.unmatched.size+' · Match manually';
    el('ai-pending-count').textContent='Pending analysis: '+(total-s.analyzed.size);
    el('ai-confirmed-count').textContent='Human-confirmed: '+s.confirmed.size;
    el('ai-mismatched-open').disabled=!total;
  }
  function selection(){
    const s=sets(),photo=sources().find(p=>p.id===photoId),field=(data.field_catalog||[]).find(f=>f.id===fieldId);
    el('ai-manual-selection').textContent=(field?'Checklist: '+field.section_title+' / '+field.label:'Select a checklist point')+' · '+(photo?'Photo: '+photo.filename:'Select an unmatched photo');
    const button=el('ai-manual-confirm');button.hidden=api.readOnly;button.disabled=busy||api.readOnly||jobs().length>0||!photo||!field||field.locked||!s.unmatched.has(photoId);
  }
  function tables(){
    const s=sets();if(photoId&&!s.unmatched.has(photoId)){photoId=null;el('ai-manual-status').textContent='The photo list changed. Select an available photo again.';}
    if(fieldId&&!(data.field_catalog||[]).some(f=>f.id===fieldId&&!f.locked))fieldId=null;
    const cq=el('ai-checklist-search').value.trim().toLowerCase(),pq=el('ai-photo-search').value.trim().toLowerCase(),cr=el('ai-checklist-rows'),pr=el('ai-photo-rows');
    const scrolls=[cr.closest('.ai-matching-scroll'),pr.closest('.ai-matching-scroll')].map(n=>n?.scrollTop||0);
    const focus=document.activeElement,focusKind=focus?.dataset.aiKind,focusId=focus?.dataset.aiId;
    cr.replaceChildren();pr.replaceChildren();
    for(const field of data.field_catalog||[]){
      if(cq&&!([field.section_title,field.label,field.description,field.id].join(' ').toLowerCase().includes(cq)))continue;
      const row=node('tr'),cell=node('td'),pick=node('td'),button=node('button',fieldId===field.id?'Selected':'Select');button.type='button';button.dataset.aiKind='field';button.dataset.aiId=field.id;button.setAttribute('aria-label','Select '+field.label);button.setAttribute('aria-pressed',String(fieldId===field.id));button.disabled=busy||field.locked;cell.append(node('strong',field.section_title+' / '+field.label+(field.locked?' - Locked':'')));
      button.onclick=()=>{fieldId=field.id;selectionDigest=data.schema_digest;tables();};pick.append(button);if(field.description)cell.append(node('small',field.description));row.append(pick,cell);cr.append(row);
    }
    for(const photo of sources().filter(p=>s.unmatched.has(p.id))){
      if(pq&&![photo.filename,photo.group,photo.visual_metadata?.caption].join(' ').toLowerCase().includes(pq))continue;
      const row=node('tr'),cell=node('td'),pick=node('td'),button=node('button',photoId===photo.id?'Selected':'Select');button.type='button';button.dataset.aiKind='photo';button.dataset.aiId=photo.id;button.setAttribute('aria-label','Select '+photo.filename);button.setAttribute('aria-pressed',String(photoId===photo.id));button.disabled=busy;
      const image=node('img');image.src=photo.preview_url;image.alt='';image.loading='lazy';cell.append(image,node('strong',photo.filename));button.onclick=()=>{photoId=photo.id;selectionDigest=data.schema_digest;tables();};pick.append(button);if(photo.visual_metadata?.caption)cell.append(node('small',photo.visual_metadata.caption));if(photo.original_url){const original=node('a','View full photo');original.href=photo.original_url;original.target='_blank';original.rel='noopener';cell.append(original);}row.append(pick,cell);pr.append(row);
    }
    if(!cr.children.length){const r=node('tr');const c=node('td','No checklist points match this search.');c.colSpan=2;r.append(c);cr.append(r);}
    if(!pr.children.length){const r=node('tr');r.append(node('td',s.unmatched.size?'No unmatched photos match this search.':'No unmatched photos available. Photos still awaiting AI Analysis appear after processing. If evidence is missing, close this window and upload the required photo.'));r.firstChild.colSpan=2;pr.append(r);}
    [cr,pr].forEach((root,i)=>{const scroller=root.closest('.ai-matching-scroll');if(scroller)scroller.scrollTop=scrolls[i];});
    if(focusKind&&focusId)[...dialog.querySelectorAll('button[data-ai-kind]')].find(b=>b.dataset.aiKind===focusKind&&b.dataset.aiId===focusId)?.focus({preventScroll:true});
    if(jobs().length&&!busy)el('ai-manual-status').textContent='AI Analysis is running. Review photos now; save links after it finishes.';
    selection();
  }
  el('ai-mismatched-open').onclick=()=>{opener=document.activeElement;photoId=null;fieldId=null;selectionDigest=null;el('ai-manual-status').textContent=api.readOnly?'Read-only review. Photo links cannot be changed.':'Select a checklist point and a photo, then confirm their link.';tables();dialog.showModal();el('ai-checklist-search').focus();};
  el('ai-matching-close').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>opener?.focus({preventScroll:true}));
  dialog.addEventListener('cancel',event=>{if(busy){event.preventDefault();el('ai-manual-status').textContent='Saving your link. Wait for the result.';}});
  el('ai-checklist-search').oninput=tables;el('ai-photo-search').oninput=tables;
  el('ai-manual-confirm').onclick=async()=>{
    if(busy||api.readOnly||jobs().length||!photoId||!fieldId)return;
    const selectedPhoto=photoId,selectedField=fieldId,digest=selectionDigest;busy=true;tables();el('ai-matching-close').disabled=true;el('ai-manual-status').textContent='Checking the latest checklist and photo…';
    try{
      data=await api.request('state/');
      if(jobs().length)throw Error('AI Analysis is running. Wait for it to finish, then review your selections again.');
      if(data.schema_digest!==digest){fieldId=null;throw Error('The checklist changed. Select the checklist point again.');}
      if(!sets().unmatched.has(selectedPhoto))throw Error('This photo already has a suggested or confirmed link, or is no longer available. Review its current links first.');
      if(!(data.field_catalog||[]).some(f=>f.id===selectedField&&!f.locked))throw Error('This checklist point is locked or no longer available.');
      await api.request('mapping/',{expected_schema_digest:digest,decisions:[{photo_id:selectedPhoto,field_id:selectedField,action:'manual'}]});
      photoId=null;el('ai-manual-status').textContent='Photo link confirmed. Checklist answers and approvals are unchanged.';await api.refresh();
    }catch(error){el('ai-manual-status').textContent=text(error.message);}
    finally{busy=false;el('ai-matching-close').disabled=false;summary();tables();}
  };
  document.addEventListener('photo-state',event=>{data=event.detail;summary();if(dialog.open)tables();});
  summary();
})();
