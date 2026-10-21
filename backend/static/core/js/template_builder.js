(() => {
 'use strict';
 const data=document.getElementById('schema-data'),form=document.getElementById('builder-form');if(!data||!form)return;
 const locked=form.dataset.locked==='true',disabled=locked?'disabled':'',model=new ChecklistEditorState(JSON.parse(data.textContent),locked);
 const tree=document.getElementById('editor-tree'),props=document.getElementById('editor-properties'),recRoot=document.getElementById('editor-recommendations');
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const uid=prefix=>prefix+'_'+crypto.randomUUID().replaceAll('-','').slice(0,20);
 const storageKey='isurvix-template-editor:'+form.dataset.templateId+':'+form.dataset.version;
 let stored={};try{stored=JSON.parse(sessionStorage.getItem(storageKey)||'{}')}catch{}
 let selected=stored.selected||{kind:'section',id:model.schema.sections[0].id},dirty=form.dataset.unsaved==='true',recItems=[],recPage=1,remoteLocked=false;
 const expanded=new Set(stored.expanded||[...model.groups().map(g=>'g:'+g),'g:','s:'+model.schema.sections[0].id]);
 if(dirty)form.dataset.dirty='true';
 const checked=new Set(),recEdits=new Map();
 const message=(text,error=false)=>{const node=document.getElementById('editor-status');node.textContent=text;node.classList.toggle('is-error',error)};
 const markDirty=()=>{dirty=true;form.dataset.dirty='true'};
 function remember(){try{sessionStorage.setItem(storageKey,JSON.stringify({selected,expanded:[...expanded],treeScroll:tree.scrollTop,propsScroll:props.scrollTop}))}catch{}}
 const nodeKey=(kind,id)=>(kind==='group'?'g:':kind==='section'?'s:':'f:')+id;
 const isSelected=(kind,id)=>selected.kind===kind&&selected.id===id;
 function currentSection(){if(selected.kind==='section')return model.section(selected.id);if(selected.kind==='field')return model.field(selected.id).section;return model.schema.sections.find(s=>(s.group||'')===selected.id)}
 function choose(kind,id,focus=false){selected={kind,id};renderTree();renderProperties();remember();if(focus)[...tree.querySelectorAll('.editor-node')].find(n=>n.dataset.kind===kind&&n.dataset.id===id)?.focus()}
 function button(kind,id,label,level,icon,expandable=false,extra=''){
  const key=nodeKey(kind,id);return `<button type="button" class="editor-node" role="treeitem" aria-level="${level}" aria-selected="${isSelected(kind,id)}" tabindex="${isSelected(kind,id)?0:-1}" data-kind="${kind}" data-id="${escape(id)}" ${expandable?`aria-expanded="${expanded.has(key)}"`:''}><span class="editor-node-icon" aria-hidden="true">${icon}</span><span>${escape(label)}</span>${extra}</button>`;
 }
 function disclosure(key,title){return `<button type="button" class="editor-disclosure" tabindex="-1" data-expand="${escape(key)}" aria-label="${expanded.has(key)?'Collapse':'Expand'} ${escape(title)}">${expanded.has(key)?'▾':'▸'}</button>`}
 function renderTree(){const scroll=tree.scrollTop;let html='<ul role="group">';
  const groups=[...model.groups()];if(model.schema.sections.some(s=>!s.group)||!groups.length)groups.push('');
  for(const group of groups){const key='g:'+group,sections=model.schema.sections.filter(s=>(s.group||'')===group),title=group||'Ungrouped';html+=`<li role="none"><div class="editor-tree-row">${disclosure(key,title)}${button('group',group,title,1,'▦',true,`<small>${sections.length}</small>`)}</div><ul role="group" ${expanded.has(key)?'':'hidden'}>`;
   for(const section of sections){const skey='s:'+section.id;html+=`<li role="none"><div class="editor-tree-row">${locked?'':`<input type="checkbox" data-select-section="${escape(section.id)}" aria-label="Select section ${escape(section.title)}" ${checked.has(section.id)?'checked':''}>`}${disclosure(skey,section.title)}${button('section',section.id,section.title,2,'▤',true,`<small>${section.fields.length}</small>`)}</div><ul role="group" ${expanded.has(skey)?'':'hidden'}>`;
    for(const field of section.fields)html+=`<li role="none"><div class="editor-tree-row">${button('field',field.id,field.label,3,'·',false,field.required?'<small title="Answer required">Required</small>':'')}</div></li>`;
    html+='</ul></li>';
   }html+='</ul></li>';
  }tree.innerHTML=html+'</ul>';tree.scrollTop=scroll;
  const visible=[...tree.querySelectorAll('.editor-node')].filter(n=>!n.closest('[hidden]'));if(!visible.some(n=>n.tabIndex===0)&&visible.length)visible[0].tabIndex=0;
  document.getElementById('field-count').textContent=model.schema.sections.length+' sections · '+model.schema.sections.reduce((n,s)=>n+s.fields.length,0)+' fields';
 }
 function evidenceEditor(f,si,fi){const rules=f.evidence_rules||{}, attrs=key=>`data-action="evidence-rule" data-rule="${key}" data-section="${si}" data-field="${fi}" ${disabled}`;
 const lists=[['required_subjects','Required subjects'],['any_subjects','Any of these subjects'],['required_text','Required visible text'],['forbidden_subjects','Contradictory subjects']];
 const flags=[['require_readable_text','Readable text required'],['require_qr','QR evidence required'],['require_gps','GPS required'],['require_capture_time','Capture time required']];
 return `<details class="builder-evidence-rules"><summary>Evidence sufficiency rules${Object.keys(rules).length?' ? configured':''}</summary><p class="small text-muted">These shared checkpoint rules assess source evidence only. They cannot set an inspection result or approve work. Saved surveys retain their checklist revision.</p><div class="builder-evidence-grid">${lists.map(([key,label])=>`<label>${label}<textarea rows="2" aria-label="${label} for ${escape(f.label)}" ${attrs(key)} placeholder="One phrase per line, up to 12">${escape((rules[key]||[]).join('\n'))}</textarea></label>`).join('')}<label>Expected site ID<input type="text" maxlength="64" aria-label="Expected site ID for ${escape(f.label)}" value="${escape(rules.expected_site_id||'')}" ${attrs('expected_site_id')} placeholder="Exact site ID, no expressions"></label><label>Minimum photos<input type="number" min="1" max="20" step="1" aria-label="Minimum photos for ${escape(f.label)}" value="${escape(rules.min_photos??'')}" ${attrs('min_photos')} placeholder="No rule"></label><label>Minimum image quality<select aria-label="Minimum image quality for ${escape(f.label)}" ${attrs('minimum_quality')}><option value="">No rule</option><option value="any" ${rules.minimum_quality==='any'?'selected':''}>Any</option><option value="clear" ${rules.minimum_quality==='clear'?'selected':''}>Clear</option></select></label>${flags.map(([key,label])=>`<label class="builder-evidence-check"><input type="checkbox" ${rules[key]?'checked':''} ${attrs(key)}> ${label}</label>`).join('')}<label>Rule notes<textarea rows="2" maxlength="1000" aria-label="Evidence rule notes for ${escape(f.label)}" ${attrs('notes')}>${escape(rules.notes||'')}</textarea></label></div><small>Rule format version 1. Leave controls empty to use no additional evidence rules.</small></details>`;
 }

 const controls=(kind,id)=>locked?'':`<div class="editor-properties-actions"><button type="button" data-editor-action="move-up" title="Move selected ${kind} up">↑ Up</button><button type="button" data-editor-action="move-down" title="Move selected ${kind} down">↓ Down</button>${kind!=='group'?`<button type="button" data-editor-action="remove">Remove ${kind}</button>`:''}</div>`;
 function renderProperties(){let html='';document.getElementById('editor-node-kind').textContent=selected.kind;
  try{
   if(selected.kind==='group'){
    if(!selected.id)html='<p>Sections without a named group. Select a section to move it into a group.</p>';
    else{html=`<label for="editor-group-title">Group name</label><input id="editor-group-title" data-prop="group-title" maxlength="160" value="${escape(selected.id)}" ${disabled}>${controls('group',selected.id)}${locked?'':'<button type="button" data-editor-action="ungroup">Ungroup · keep all sections and fields</button>'}`}
    if(!locked)html+='<div class="editor-properties-actions"><button type="button" data-editor-action="add-section">＋ Add section</button></div>';
   }else if(selected.kind==='section'){
    const section=model.section(selected.id);html=`<label for="editor-section-title">Section name</label><input id="editor-section-title" data-prop="section-title" maxlength="160" value="${escape(section.title)}" ${disabled}><label for="editor-section-group">Parent group</label><select id="editor-section-group" data-prop="section-group" ${disabled}><option value="">Ungrouped</option>${model.groups().map(g=>`<option ${section.group===g?'selected':''}>${escape(g)}</option>`).join('')}</select>${controls('section',section.id)}${locked?'':`<div class="editor-properties-actions"><button type="button" data-editor-action="add-field">＋ Add field</button>${section.room?'':'<button type="button" data-editor-action="duplicate-section">Duplicate section</button>'}</div>`}<p class="editor-id">Section ID: ${escape(section.id)}</p>`;
   }else{
    const {field:f,section}=model.field(selected.id);html=`<p class="editor-id">${escape(section.group||'Ungrouped')} → ${escape(section.title)}</p><label for="editor-field-label">Checklist field</label><textarea id="editor-field-label" data-prop="field-label" rows="3" maxlength="3000" required ${disabled}>${escape(f.label)}</textarea><label for="editor-field-type">Input type</label><select id="editor-field-type" data-prop="field-type" ${locked||f.system?'disabled':''}>${['text','textarea','number','date','select','inspection','table','photo'].map(type=>`<option ${f.type===type?'selected':''}>${type}</option>`).join('')}</select><label class="editor-check"><input type="checkbox" data-prop="field-required" ${f.required?'checked':''} ${disabled}> Answer required</label><label class="editor-check"><input type="checkbox" data-prop="field-photo-required" ${f.photo_required?'checked':''} ${disabled}> Photo evidence required</label><label for="editor-field-description">Checkpoint instructions / condition details</label><textarea id="editor-field-description" data-prop="field-description" rows="3" ${disabled}>${escape(f.description||'')}</textarea>`;
    if(f.type==='number')html+=`<label for="editor-field-unit">Unit</label><input id="editor-field-unit" data-prop="field-unit" value="${escape(f.unit||'')}" ${disabled}>`;
    if(f.type==='select')html+=`<label for="editor-field-options">Choices (one per line)</label><textarea id="editor-field-options" data-prop="field-options" rows="4" ${disabled}>${escape((f.options||[]).join('\n'))}</textarea>`;
    if(f.type==='table')html+=`<label for="editor-field-columns">Table column labels (one per line)</label><textarea id="editor-field-columns" data-prop="field-columns" rows="4" ${disabled}>${escape((f.columns||[]).map(c=>c.label).join('\n'))}</textarea>`;
    html+=evidenceEditor(f,0,0)+controls('field',f.id)+`<p class="editor-id">Stable field ID: ${escape(f.id)}${f.system?' · linked Site ID':''}</p>`;
    if(f.recommendation_source)html+=`<p class="editor-id">Recommendation source: ${escape(f.recommendation_source)}</p>`;
   }
  }catch{selected={kind:'section',id:model.schema.sections[0].id};renderProperties();return}
  props.innerHTML=html;
 }
 tree.addEventListener('click',event=>{const expand=event.target.closest('[data-expand]');if(expand){const key=expand.dataset.expand;expanded.has(key)?expanded.delete(key):expanded.add(key);renderTree();remember();return}const node=event.target.closest('.editor-node');if(node)choose(node.dataset.kind,node.dataset.id)});
 tree.addEventListener('change',event=>{const id=event.target.dataset.selectSection;if(id){event.target.checked?checked.add(id):checked.delete(id)}});
 tree.addEventListener('keydown',event=>{
  const node=event.target.closest('.editor-node');if(!node||!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();
  const nodes=[...tree.querySelectorAll('.editor-node')].filter(n=>!n.closest('[hidden]')),index=nodes.indexOf(node);let next;
  if(event.key==='ArrowUp')next=nodes[Math.max(0,index-1)];if(event.key==='ArrowDown')next=nodes[Math.min(nodes.length-1,index+1)];if(event.key==='Home')next=nodes[0];if(event.key==='End')next=nodes.at(-1);
  const key=nodeKey(node.dataset.kind,node.dataset.id);
  if(event.key==='ArrowRight'){if(node.hasAttribute('aria-expanded')&&!expanded.has(key)){expanded.add(key);renderTree();remember();choose(node.dataset.kind,node.dataset.id,true)}else next=nodes[index+1]}
  if(event.key==='ArrowLeft'){if(expanded.has(key)){expanded.delete(key);renderTree();remember();choose(node.dataset.kind,node.dataset.id,true)}else{if(node.dataset.kind==='field')choose('section',model.field(node.dataset.id).section.id,true);else if(node.dataset.kind==='section')choose('group',model.section(node.dataset.id).group||'',true)}}
  if(next)choose(next.dataset.kind,next.dataset.id,true);
 });
 props.addEventListener('input',event=>{
  if(locked)return;const t=event.target,p=t.dataset.prop;
  if(selected.kind==='field'){
   const f=model.field(selected.id).field;
   if(t.dataset.action==='evidence-rule'){const rules={...(f.evidence_rules||{})},key=t.dataset.rule;let value=t.type==='checkbox'?t.checked:t.value;if(['required_subjects','any_subjects','required_text','forbidden_subjects'].includes(key))value=[...new Set(value.split('\n').map(x=>x.trim()).filter(Boolean))];if(key==='min_photos'&&value!=='')value=Number(value);if(value===''||value===false||(Array.isArray(value)&&!value.length))delete rules[key];else rules[key]=value;delete rules.version;if(Object.keys(rules).length)f.evidence_rules={version:1,...rules};else delete f.evidence_rules;markDirty();return}
   if(p==='field-label')f.label=t.value;if(p==='field-required')f.required=t.checked;if(p==='field-photo-required')f.photo_required=t.checked;if(p==='field-description')f.description=t.value;if(p==='field-unit')f.unit=t.value;
   if(p==='field-options')f.options=t.value.split('\n').map(x=>x.trim()).filter(Boolean);
   if(p==='field-columns')f.columns=t.value.split('\n').map(x=>x.trim()).filter(Boolean).map((label,i)=>({...f.columns[i],id:f.columns[i]?.id||uid('column'),label}));
  }else if(selected.kind==='section'&&p==='section-title')model.section(selected.id).title=t.value;
  if(p&&p!=='field-type'&&p!=='group-title'&&p!=='section-group'){markDirty();renderTree();remember()}
 });
 props.addEventListener('change',event=>{if(locked)return;const t=event.target;try{
  if(t.dataset.prop==='group-title'){const old=selected.id,name=model.renameGroup(old,t.value);selected={kind:'group',id:name};if(expanded.delete('g:'+old))expanded.add('g:'+name);t.value=name;t.setCustomValidity('');markDirty();renderTree();renderRecommendations();remember()}
  if(t.dataset.prop==='section-group'){model.moveSection(selected.id,t.value);expanded.add('g:'+t.value);markDirty();renderTree();renderRecommendations();remember()}
  if(t.dataset.prop==='field-type'){const f=model.field(selected.id).field;f.type=t.value;if(f.type==='select'&&!f.options)f.options=['Yes','No','Not applicable'];if(f.type==='table'&&!f.columns)f.columns=[{id:uid('column'),label:'Value'}];markDirty();renderProperties()}
 }catch(error){message(error.message,true);if(t.dataset.prop==='group-title')t.setCustomValidity(error.message)}});
 const groupDialog=document.getElementById('editor-group-dialog');
 document.querySelectorAll('[data-editor-action]').forEach(button=>button.addEventListener('click',()=>perform(button.dataset.editorAction)));
 props.addEventListener('click',event=>{const button=event.target.closest('[data-editor-action]');if(button)perform(button.dataset.editorAction)});
 function perform(action){try{
  if(action==='expand-all'){model.groups().forEach(g=>expanded.add('g:'+g));expanded.add('g:');model.schema.sections.forEach(s=>expanded.add('s:'+s.id));renderTree();remember();return}
  if(action==='collapse-all'){expanded.clear();renderTree();remember();return}
  model.editable();
  if(action==='add-group'){let name='New group',n=2;while(model.groups().includes(name))name='New group '+n++;model.addGroup(name);selected={kind:'group',id:name};expanded.add('g:'+name)}
  if(action==='add-section'){const group=selected.kind==='group'?selected.id:(currentSection()?.group||'');const section=model.addSection(group);selected={kind:'section',id:section.id};expanded.add('g:'+group);expanded.add('s:'+section.id)}
  if(action==='add-field'){const section=currentSection();if(!section)throw Error('Add or select a section first.');const field=model.addField(section.id);selected={kind:'field',id:field.id};expanded.add('g:'+(section.group||''));expanded.add('s:'+section.id)}
  if(action==='group-selected'){if(!checked.size)throw Error('Select one or more section checkboxes first.');document.getElementById('editor-group-existing').innerHTML='<option value="">Create a new group</option>'+model.groups().map(g=>`<option>${escape(g)}</option>`).join('');document.getElementById('editor-group-name').value='';groupDialog.showModal();return}
  if(action==='ungroup'){if(selected.kind==='group'){model.ungroup(selected.id);selected={kind:'group',id:''}}else if(selected.kind==='section')model.moveSection(selected.id,'');else throw Error('Select a group or section to ungroup.');expanded.add('g:')}
  if(action==='move-up'||action==='move-down')model.reorder(selected.kind,selected.id,action==='move-up'?-1:1);
  if(action==='duplicate-section'){const section=model.duplicateSection(selected.id);selected={kind:'section',id:section.id};expanded.add('s:'+section.id)}
  if(action==='remove'){if(!confirm('Remove this '+selected.kind+' from the draft? Saved surveys keep their original fields.'))return;model.remove(selected.kind,selected.id);selected={kind:'section',id:model.schema.sections[0].id}}
  markDirty();renderTree();renderProperties();renderRecommendations();remember();message('Draft structure updated. Save draft to retain the changes.');
 }catch(error){message(error.message,true)}}
 groupDialog.addEventListener('close',()=>{if(groupDialog.returnValue!=='confirm')return;try{let group=document.getElementById('editor-group-existing').value;if(!group)group=model.addGroup(document.getElementById('editor-group-name').value);model.groupSections([...checked],group);checked.clear();selected={kind:'group',id:group};expanded.add('g:'+group);markDirty();renderTree();renderProperties();renderRecommendations();remember();message('Selected sections grouped. Their fields and IDs are preserved. Save draft to retain the hierarchy.')}catch(error){message(error.message,true)}});
 function recValues(card,rec){return {sectionId:card.querySelector('[data-rec-prop=section]')?.value==='__new__'?'':card.querySelector('[data-rec-prop=section]')?.value||rec.section_id||'',sectionTitle:card.querySelector('[data-rec-prop=title]')?.value??rec.section_title,group:card.querySelector('[data-rec-prop=group]')?.value||'',field:{label:card.querySelector('[data-rec-prop=label]')?.value??rec.field.label,type:card.querySelector('[data-rec-prop=type]')?.value||rec.field.type,required:card.querySelector('[data-rec-prop=required]')?.checked??!!rec.field.required,photo_required:card.querySelector('[data-rec-prop=photo]')?.checked??!!rec.field.photo_required,...((card.querySelector('[data-rec-prop=type]')?.value||rec.field.type)==='select'?{options:(card.querySelector('[data-rec-prop=options]')?.value||(rec.field.options||['Yes','No']).join('\n')).split('\n').map(x=>x.trim()).filter(Boolean)}:{})}}}
 function captureRecEdits(){for(const card of recRoot.querySelectorAll('[data-rec-id]')){const rec=recItems.find(item=>item.id===card.dataset.recId);if(rec&&card.querySelector('[data-rec-prop]'))recEdits.set(rec.id,recValues(card,rec))}}
 function renderRecommendations(){captureRecEdits();const decisions=model.schema.editor_recommendation_decisions||{},query=document.getElementById('editor-rec-search').value.toLocaleLowerCase(),showDismissed=document.getElementById('editor-show-dismissed').checked;
  const items=recItems.filter(rec=>(showDismissed||decisions[rec.id]!=='dismissed')&&[rec.field.label,rec.section_title,rec.source].join(' ').toLocaleLowerCase().includes(query)),pages=Math.max(1,Math.ceil(items.length/5));recPage=Math.min(recPage,pages);
  document.getElementById('editor-rec-count').textContent=items.length+' available';document.getElementById('editor-rec-page').textContent=recPage+' / '+pages;document.getElementById('editor-rec-previous').disabled=recPage<=1;document.getElementById('editor-rec-next').disabled=recPage>=pages;
  recRoot.innerHTML=items.slice((recPage-1)*5,recPage*5).map(rec=>{
   const saved=decisions[rec.id],added=model.schema.sections.flatMap(s=>s.fields.map(f=>({section:s,field:f}))).find(x=>x.field.id==='rec_'+rec.id.replace(/^p_/,'')),values=(saved==='accepted'&&added?{sectionId:added.section.id,sectionTitle:added.section.title,group:added.section.group||'',field:added.field}:recEdits.get(rec.id))||{sectionId:rec.section_id||'',sectionTitle:rec.section_title,group:rec.group||'',field:rec.field},f=values.field,d=locked||remoteLocked?'disabled':'';
   return `<article class="editor-rec-card" data-rec-id="${escape(rec.id)}"><h3>${escape(f.label)}</h3><p>Target: ${escape((values.sectionId?model.schema.sections.find(s=>s.id===values.sectionId)?.group:values.group)||'Ungrouped')} → ${escape(values.sectionId?model.schema.sections.find(s=>s.id===values.sectionId)?.title||values.sectionTitle:values.sectionTitle)}</p><p>${escape(rec.reason||'')}</p><p>Source: ${escape(rec.source||'Not recorded')}</p>${saved?`<p><strong>${saved==='accepted'?'Added to draft':'Dismissed'}</strong></p>`:`<details><summary>Review &amp; edit</summary><label>Proposed field<textarea data-rec-prop="label" maxlength="3000" rows="3" ${d}>${escape(f.label)}</textarea></label><label>Target section<select data-rec-prop="section" ${d}><option value="__new__" ${!values.sectionId?'selected':''}>New section</option>${model.schema.sections.map(s=>`<option value="${escape(s.id)}" ${values.sectionId===s.id?'selected':''}>${escape(s.title)}</option>`).join('')}</select></label><label>New section name<input data-rec-prop="title" maxlength="160" value="${escape(values.sectionTitle)}" ${d}></label><label>Group for a new section<select data-rec-prop="group" ${d}><option value="">Ungrouped</option>${model.groups().map(g=>`<option ${values.group===g?'selected':''}>${escape(g)}</option>`).join('')}</select></label><label>Input type<select data-rec-prop="type" ${d}>${['text','textarea','number','date','select','inspection','table','photo'].map(type=>`<option ${f.type===type?'selected':''}>${type}</option>`).join('')}</select></label><label><input type="checkbox" data-rec-prop="required" ${f.required?'checked':''} ${d}> Answer required</label><label><input type="checkbox" data-rec-prop="photo" ${f.photo_required?'checked':''} ${d}> Photo required</label><label>Dropdown choices (one per line)<textarea data-rec-prop="options" rows="3" ${d}>${escape((f.options||[]).join('\n'))}</textarea></label></details>`}<div class="editor-rec-actions">${saved==='dismissed'?`<button type="button" data-rec-action="restore" ${d}>Restore</button>`:saved==='accepted'?'':`<button type="button" data-rec-action="accept" ${d}>Accept addition</button><button type="button" data-rec-action="dismiss" ${d}>Dismiss</button>`}</div></article>`;
  }).join('')||'<p class="editor-id">No recommendations match this view.</p>';
 }
 recRoot.addEventListener('click',event=>{const action=event.target.closest('[data-rec-action]');if(!action)return;try{
  if(locked||remoteLocked)throw Error('Recommendations can be applied only to an editable draft.');const card=action.closest('[data-rec-id]'),rec=recItems.find(item=>item.id===card.dataset.recId);
  if(action.dataset.recAction==='accept'){const result=model.apply(rec,recValues(card,rec));if(result.field){selected={kind:'field',id:result.field.id};expanded.add('g:'+(result.section.group||''));expanded.add('s:'+result.section.id)}message(result.already?'This checkpoint is already present. No duplicate was added.':'Recommendation added to the intended section. Save draft to keep it.')}
  else{model.decision(rec.id,action.dataset.recAction==='dismiss'?'dismissed':null);message(action.dataset.recAction==='dismiss'?'Recommendation dismissed. Save draft to retain this choice.':'Recommendation restored for review.')}
  markDirty();renderTree();renderProperties();renderRecommendations();remember();
 }catch(error){message(error.message,true)}});
 document.getElementById('editor-rec-search').addEventListener('input',()=>{recPage=1;renderRecommendations()});document.getElementById('editor-show-dismissed').addEventListener('change',()=>{recPage=1;renderRecommendations()});
 document.getElementById('editor-rec-previous').addEventListener('click',()=>{recPage--;renderRecommendations()});document.getElementById('editor-rec-next').addEventListener('click',()=>{recPage++;renderRecommendations()});
 async function loadRecommendations(){const status=document.getElementById('editor-rec-status'),retry=document.getElementById('editor-rec-retry');retry.hidden=true;status.textContent='Loading available recommendations…';try{
  const response=await fetch(form.dataset.recommendationsUrl,{credentials:'same-origin',cache:'no-store'});let payload;try{payload=await response.json()}catch{throw Error('Recommendation data is unavailable ('+response.status+').')}
  if(!response.ok)throw Error(payload.error||payload.message||'Recommendations are unavailable.');if(String(payload.template_id)!==form.dataset.templateId||String(payload.version)!==form.dataset.version)throw Error('Recommendations belong to another checklist revision. Refresh this editor.');
  recItems=payload.recommendations||[];remoteLocked=!!payload.locked;status.textContent=recItems.length?(locked||remoteLocked?'Read-only suggestions. Open an editable draft to accept additions.':'Review additions from standards and permitted published checklists. Accepting updates this draft; save to keep it.'):'No additions are available from current standards and permitted published checklists.';renderRecommendations();
 }catch(error){recItems=[];status.textContent=error.message;retry.hidden=false;renderRecommendations()}}
 document.getElementById('editor-rec-retry').addEventListener('click',loadRecommendations);
 form.addEventListener('input',event=>{if(event.target.closest('.editor-compact-header,.editor-branding')){markDirty();if(event.target.id==='template-name'){const current=document.querySelector('.editor-template-list [aria-current=page] strong');if(current)current.textContent=event.target.value}}});
 form.addEventListener('submit',()=>{model.schema.title=document.getElementById('template-name').value;document.getElementById('definition-input').value=JSON.stringify(model.schema);remember();dirty=false});
 window.addEventListener('beforeunload',event=>{remember();if(dirty){event.preventDefault();event.returnValue=''}});
 tree.addEventListener('scroll',remember,{passive:true});props.addEventListener('scroll',remember,{passive:true});
 const picker=document.getElementById('editor-template-picker');if(innerWidth<=800)picker.open=false;
 const active=document.querySelector('.editor-template-list .selected');if(active)active.parentElement.scrollTop=Math.max(0,active.offsetTop-active.parentElement.offsetTop-20);
 function fit(){const workspace=document.querySelector('.editor-workspace');if(innerWidth>1250)workspace.style.height=Math.max(350,innerHeight-workspace.getBoundingClientRect().top-55)+'px'}
 window.addEventListener('resize',fit);document.fonts?.ready.then(fit);
 renderTree();renderProperties();tree.scrollTop=stored.treeScroll||0;props.scrollTop=stored.propsScroll||0;fit();loadRecommendations();
})();
