(() => {
 'use strict';
 const node=document.getElementById('schema-data');if(!node)return;
 let schema=JSON.parse(node.textContent);
 const form=document.getElementById('builder-form'), locked=form.dataset.locked==='true',root=document.getElementById('schema-editor');
 const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const uid=prefix=>prefix+'_'+crypto.randomUUID().replaceAll('-','').slice(0,12);
 const disabled=locked?'disabled':'';
 const types=['text','textarea','number','date','select','inspection','table','photo'];
 function render(){
  document.getElementById('field-count').textContent=schema.sections.length+' sections · '+schema.sections.reduce((n,s)=>n+s.fields.length,0)+' fields';
  root.innerHTML=schema.sections.map((s,si)=>`<details class="schema-section" ${si===0?'open':''}><summary><strong class="flex-grow-1">${escape(s.title)}</strong><small class="text-muted">${s.fields.length} fields</small></summary><div class="section-meta"><div><label class="small">Section name</label><input class="form-control" value="${escape(s.title)}" data-action="section-title" data-section="${si}" ${disabled}></div><div><label class="small">Group / parent heading</label><input class="form-control" value="${escape(s.group||'')}" data-action="section-group" data-section="${si}" ${disabled}></div></div>${locked?'':`<div class="field-actions"><button type="button" class="tiny-btn" data-action="section-up" data-section="${si}" aria-label="Move section up">↑</button><button type="button" class="tiny-btn" data-action="section-down" data-section="${si}" aria-label="Move section down">↓</button><button type="button" class="tiny-btn text-danger" data-action="section-delete" data-section="${si}">Remove section</button></div>`}<div class="section-fields">${s.fields.map((f,fi)=>`<div class="builder-field"><div class="field-controls"><textarea class="form-control" rows="2" aria-label="Question or field label" data-action="field-label" data-section="${si}" data-field="${fi}" ${disabled}>${escape(f.label)}</textarea><select class="form-select" aria-label="Field type" data-action="field-type" data-section="${si}" data-field="${fi}" ${disabled}>${types.map(t=>`<option ${f.type===t?'selected':''}>${t}</option>`).join('')}</select><label class="small"><input type="checkbox" data-action="field-required" data-section="${si}" data-field="${fi}" ${f.required?'checked':''} ${disabled}> Required</label>${locked?'':`<div class="field-actions"><button type="button" class="tiny-btn" data-action="field-up" data-section="${si}" data-field="${fi}" aria-label="Move field up">↑</button><button type="button" class="tiny-btn" data-action="field-down" data-section="${si}" data-field="${fi}" aria-label="Move field down">↓</button><button type="button" class="tiny-btn text-danger" data-action="field-delete" data-section="${si}" data-field="${fi}" aria-label="Remove field">×</button></div>`}</div>${f.type==='select'?`<label class="small mt-2">Choices, one per line</label><textarea class="form-control" data-action="field-options" data-section="${si}" data-field="${fi}" ${disabled}>${escape((f.options||[]).join('\n'))}</textarea>`:''}${f.type==='table'?`<label class="small mt-2">Table column labels, one per line</label><textarea class="form-control" data-action="field-columns" data-section="${si}" data-field="${fi}" ${disabled}>${escape((f.columns||[]).map(c=>c.label).join('\n'))}</textarea>`:''}${f.type==='number'?`<input class="form-control mt-2" placeholder="Unit, e.g. m, A, V, Ah" value="${escape(f.unit||'')}" data-action="field-unit" data-section="${si}" data-field="${fi}" ${disabled}>`:''}<small class="text-muted">Stable ID: ${escape(f.id)}${f.system?' · Site ID stays linked to the assignment':''}</small></div>`).join('')}</div>${locked?'':`<button type="button" class="btn btn-sm btn-outline-success mt-3" data-action="field-add" data-section="${si}">+ Add field</button>`}</details>`).join('');
 }
 function swap(a,i,j){if(j>=0&&j<a.length)[a[i],a[j]]=[a[j],a[i]]}
 root.addEventListener('input',e=>{
  if(locked)return;const t=e.target,a=t.dataset.action,si=Number(t.dataset.section),fi=Number(t.dataset.field),s=schema.sections[si],f=s?.fields[fi];if(!a)return;
  if(a==='section-title')s.title=t.value;
  if(a==='section-group')s.group=t.value;
  if(a==='field-label')f.label=t.value;
  if(a==='field-required')f.required=t.checked;
  if(a==='field-unit')f.unit=t.value;
  if(a==='field-options')f.options=t.value.split('\n').map(v=>v.trim()).filter(Boolean);
  if(a==='field-columns')f.columns=t.value.split('\n').map(v=>v.trim()).filter(Boolean).map((label,i)=>({id:f.columns[i]?.id||uid('col'),label}));
 });
 root.addEventListener('change',e=>{if(locked)return;const t=e.target;if(t.dataset.action==='field-type'){const f=schema.sections[Number(t.dataset.section)].fields[Number(t.dataset.field)];f.type=t.value;if(f.type==='select'&&!f.options)f.options=['Yes','No','Not applicable'];if(f.type==='table'&&!f.columns)f.columns=[{id:'value',label:'Value'}];render()}});
 root.addEventListener('click',e=>{
  const t=e.target.closest('button[data-action]');if(!t||locked)return;
  const a=t.dataset.action,si=Number(t.dataset.section),fi=Number(t.dataset.field),s=schema.sections[si];
  if(a==='field-add')s.fields.push({id:uid('field'),label:'New field',type:'text',required:false});
  if(a==='field-delete'&&confirm('Remove this field from the draft? Existing surveys keep their previous template.'))s.fields.splice(fi,1);
  if(a==='section-delete'&&confirm('Remove this section and its fields from the draft?'))schema.sections.splice(si,1);
  if(a==='section-up')swap(schema.sections,si,si-1);
  if(a==='section-down')swap(schema.sections,si,si+1);
  if(a==='field-up')swap(s.fields,fi,fi-1);
  if(a==='field-down')swap(s.fields,fi,fi+1);
  render();
 });
 document.getElementById('add-section')?.addEventListener('click',()=>{schema.sections.push({id:uid('section'),title:'New section',fields:[{id:uid('field'),label:'New field',type:'text',required:false}]});render()});
 form.addEventListener('submit',()=>{schema.title=document.getElementById('template-name').value;document.getElementById('definition-input').value=JSON.stringify(schema)});
 render();
})();
