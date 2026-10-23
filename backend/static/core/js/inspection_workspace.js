/* Inspection navigation only; evidence mutations stay with the existing photo APIs. */
(() => {
  'use strict';
  const api=window.photoWorkspace,app=document.getElementById('photo-app');if(!api||!app)return;
  const el=id=>document.getElementById(id),tree=el('inspection-tree'),storageKey='inspection-ui:'+location.pathname;
  let state=api.getState(),activeField=null,zoom=1,metadata=true,restored=false,saved={};
  try{saved=JSON.parse(sessionStorage.getItem(storageKey)||'{}');}catch{}
  const openSections=new Map((Array.isArray(saved.open)?saved.open:[]).filter(row=>Array.isArray(row)&&typeof row[0]==='string'&&typeof row[1]==='boolean'));let answers={};try{answers=JSON.parse(el('inspection-saved-answers')?.textContent||'{}').custom||{};}catch{}
  function resultStatus(field){const value=answers[field.id];if(value&&typeof value==='object'&&!Array.isArray(value)){if(value.result==='Checked')return 'passed';if(value.result==='Defect found')return 'failed';if(value.result==='Not applicable')return 'not_applicable';return value.result?'review':'pending';}return value===undefined||value===null||value===''||Array.isArray(value)&&!value.length?'pending':'review';}
  const resultLabels={passed:'Passed · Checked',failed:'Failed · Defect found',not_applicable:'Not applicable',pending:'Pending answer',review:'Recorded · review'};
  function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function persist(){tree.querySelectorAll('details[data-section],details[data-group]').forEach(d=>openSections.set(d.dataset.section||'group:'+d.dataset.group,d.open));try{sessionStorage.setItem(storageKey,JSON.stringify({open:[...openSections],field:activeField,photo:api.getCurrent(),scroll:scrollY,treeScroll:tree.scrollTop,width:app.style.getPropertyValue('--inspection-tree-width')}));}catch{}}
  function itemStatus(field){const slot=(state.coverage?.evidence_slots||state.coverage?.required||[]).find(x=>x.field_id===field.id);return slot?.status||'unreported';}
  const labels={missing:'Evidence gap',uncertain:'Needs confirmation',covered:'Evidence linked',not_applicable:'Not applicable',unreported:'Checklist item'};
  function buildTree(){
    const scroll=tree.scrollTop;
    tree.querySelectorAll('details[data-section],details[data-group]').forEach(d=>openSections.set(d.dataset.section||'group:'+d.dataset.group,d.open));
    tree.replaceChildren();
    const query=el('inspection-search').value.toLowerCase().trim(),filter=el('inspection-filter').value,catalog=state.field_catalog||[],groups=new Map();
    let schema={};try{schema=JSON.parse(el('inspection-schema')?.textContent||'{}');}catch{}
    const sectionInfo=new Map((schema.sections||[]).map(section=>[section.id,section]));
    const all=node('button','All uploaded photos','inspection-all');all.type='button';all.setAttribute('aria-pressed',String(!activeField));all.onclick=()=>chooseField(null);tree.append(all);
    let count=0;
    for(const field of catalog){
      const status=itemStatus(field),section=sectionInfo.get(field.section_id),heading=section?.group||field.group||'Checklist';
      if(query&&!((field.label||'')+' '+(field.section_title||'')+' '+heading+' '+field.id).toLowerCase().includes(query))continue;
      if(filter==='locked'&&!field.locked||['missing','uncertain','covered'].includes(filter)&&filter!==status||['pending','passed','failed','review','not_applicable'].includes(filter)&&filter!==resultStatus(field))continue;
      if(!groups.has(heading))groups.set(heading,new Map());
      const sections=groups.get(heading);if(!sections.has(field.section_id))sections.set(field.section_id,{title:field.section_title,fields:[]});sections.get(field.section_id).fields.push(field);count++;
    }
    let sectionCount=0;
    for(const[groupName,sections]of groups){
      const group=node('details',undefined,'inspection-group');group.dataset.group=groupName;group.open=query?true:(openSections.get('group:'+groupName)??true);
      const groupSummary=node('summary'),groupTitle=node('span',groupName),groupCount=node('small',String([...sections.values()].reduce((total,section)=>total+section.fields.length,0)),'inspection-section-count');groupSummary.append(groupTitle,groupCount);group.append(groupSummary);
      for(const[id,section]of sections){
        sectionCount++;const details=node('details',undefined,'inspection-tree-section');details.dataset.section=id;details.open=query?true:(openSections.get(id)??true);
        const summary=node('summary'),title=node('span',section.title||id),answered=section.fields.filter(field=>resultStatus(field)!=='pending').length,total=node('span',answered+'/'+section.fields.length,'inspection-section-count');total.title='Answered / checklist points';summary.append(title,total);details.append(summary);
        for(const field of section.fields){
          const status=itemStatus(field),button=node('button',undefined,'inspection-tree-item');button.type='button';button.dataset.field=field.id;button.dataset.status=status;button.dataset.result=resultStatus(field);button.setAttribute('aria-pressed',String(activeField===field.id));
          button.append(node('span',field.label||field.id),node('small',(field.locked?'Locked · ':'')+resultLabels[resultStatus(field)]));
          if(app.dataset.engineer!=='true')button.append(node('small',labels[status]));button.onclick=()=>chooseField(field);
          const row=node('div',undefined,'inspection-tree-row');row.append(button);
          if(app.dataset.engineer!=='true'){const link=node('a','Open item'),target=new URL(app.dataset.checklistUrl,location.origin);target.searchParams.set('field',field.id);const back=new URLSearchParams(location.search).get('return_to');if(back?.startsWith('/governance/tasks/'))target.searchParams.set('return_to',back);link.href=target.pathname+target.search;link.className='inspection-open-item';row.append(link);}
          details.append(row);
        }
        group.append(details);
      }
      tree.append(group);
    }
    if(!count)tree.append(node('p',catalog.length?'No checklist items match these filters.':'Checklist details will appear when evidence state is available.'));
    el('inspection-tree-count').textContent=count+' of '+catalog.length+' points · '+sectionCount+' sections';tree.scrollTop=scroll;
  }
  function chooseField(field){activeField=field?.id||null;el('inspection-active-item').textContent=field?(field.section_title||field.section_id)+' / '+field.label+(field.locked?' · Locked':''):'All site evidence';api.filterField(app.dataset.engineer==='true'?null:activeField);document.dispatchEvent(new CustomEvent('inspection-field',{detail:field}));buildTree();persist();if(matchMedia('(max-width:900px)').matches)closeTree();}
  function closeTree(){app.classList.remove('inspection-drawer-open');el('inspection-tree-open')?.setAttribute('aria-expanded','false');}
  if(el('inspection-tree-open'))el('inspection-tree-open').onclick=()=>{const open=app.classList.toggle('inspection-drawer-open');el('inspection-tree-open')?.setAttribute('aria-expanded',String(open));if(open)el('inspection-search').focus();};el('inspection-tree-close').onclick=closeTree;
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&app.classList.contains('inspection-drawer-open')){closeTree();el('inspection-tree-open')?.focus();}});
  el('inspection-search').oninput=buildTree;el('inspection-filter').onchange=buildTree;
  for(const[id,open]of[['inspection-expand',true],['inspection-collapse',false]])el(id).onclick=()=>tree.querySelectorAll('details').forEach(d=>{d.open=open;openSections.set(d.dataset.section||'group:'+d.dataset.group,open);});
  function navigate(delta){const photos=api.getVisiblePhotos(),index=photos.findIndex(p=>p.id===api.getCurrent());if(photos.length)api.selectPhoto(photos[(Math.max(0,index)+delta+photos.length)%photos.length].id);}
  el('photo-previous').onclick=()=>navigate(-1);el('photo-next').onclick=()=>navigate(1);
  function applyZoom(){const img=el('photo-selected');img.style.width=zoom*100+'%';img.style.height=zoom*100+'%';el('photo-viewer').classList.toggle('is-zoomed',zoom>1);el('photo-zoom-level').textContent=Math.round(zoom*100)+'%';el('photo-zoom-out').disabled=zoom<=1;el('photo-zoom-in').disabled=zoom>=4;}
  el('photo-zoom-in').onclick=()=>{zoom=Math.min(4,zoom+.25);applyZoom();};el('photo-zoom-out').onclick=()=>{zoom=Math.max(1,zoom-.25);applyZoom();};el('photo-zoom-reset').onclick=()=>{zoom=1;applyZoom();};
  function applyMetadata(){for(const id of ['photo-caption','photo-metadata-status','photo-visual-observations'])el(id).classList.toggle('inspection-metadata-hidden',!metadata);el('photo-metadata-toggle').setAttribute('aria-expanded',String(metadata));}
  el('photo-metadata-toggle').onclick=()=>{metadata=!metadata;applyMetadata();};
  const separator=el('inspection-resizer');function resize(width){width=Math.max(240,Math.min(520,width));app.style.setProperty('--inspection-tree-width',width+'px');separator.setAttribute('aria-valuenow',String(width));}
  separator.onpointerdown=event=>{separator.setPointerCapture(event.pointerId);separator.dataset.dragging='true';};separator.onpointermove=event=>{if(separator.dataset.dragging==='true')resize(event.clientX-app.getBoundingClientRect().left);};separator.onpointerup=()=>{delete separator.dataset.dragging;persist();};separator.onpointercancel=()=>delete separator.dataset.dragging;
  separator.onkeydown=event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const width=Number(separator.getAttribute('aria-valuenow'));resize(event.key==='Home'?240:event.key==='End'?520:width+(event.key==='ArrowRight'?20:-20));persist();}};
  if(/^\d+(\.\d+)?px$/.test(saved.width||''))resize(parseFloat(saved.width));
  document.addEventListener('photo-state',event=>{state=event.detail;buildTree();applyMetadata();if(!restored&&(state.field_catalog?.length||state.photos?.length)){restored=true;const field=(state.field_catalog||[]).find(f=>f.id===saved.field);if(field)chooseField(field);if(saved.photo)api.selectPhoto(saved.photo);if(Number.isFinite(saved.treeScroll))tree.scrollTop=saved.treeScroll;if(Number.isFinite(saved.scroll))requestAnimationFrame(()=>scrollTo({top:saved.scroll,behavior:'instant'}));}});
  document.addEventListener('engineer-answer-saved',event=>{answers[event.detail.id]=event.detail.value;buildTree();});
  document.addEventListener('inspection-select-source',()=>chooseField(null));
  document.addEventListener('photo-selected',()=>{zoom=1;applyZoom();applyMetadata();persist();});addEventListener('pagehide',persist);
  buildTree();applyZoom();
})();
