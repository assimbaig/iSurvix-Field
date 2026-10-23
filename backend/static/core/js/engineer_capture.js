(() => {
  'use strict';
  const root = document.getElementById('engineer-capture');
  if (!root) return;
  const el = id => document.getElementById(id);
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const categories = [{value:'Civil',label:'Civil'},{value:'Electrical',label:'Electrical'},{value:'Tower',label:'Tower'}];
  const galleryCategories = [{value:'',label:'Uncategorised (existing photos)'},...categories];
  const label = value => galleryCategories.find(c => c.value === value)?.label || 'Uncategorised (existing photos)';
  let saved = null, stale = true, category = 'Civil', currentView = 'general', pending = [], serial = 0;
  let generalInfo=null,generalLoaded=false,generalBusy=false,generalExpectedDigest='',generalSignature='',generalNeedsSave=false,generalLoadError='';
  let generalDraft=new Map(),generalBase=new Map(),generalDirty=new Set();
  const generalDraftKey=`capture-general-draft:${root.dataset.draftKey||location.pathname}`;
  let uploadBusy = false, mutationBusy = false, submitBusy = false, uploadToken = null, heartbeat = null;
  let viewerItems = [], viewerIndex = 0, viewerKind = 'saved', focusedBeforeViewer = null, bulkTarget = '__choose__';
  const selectionKey = `capture-selected-photos:${location.pathname}`;
  let selection = new Set();
  try {const stored=JSON.parse(sessionStorage.getItem(selectionKey)||'[]');if(Array.isArray(stored)&&stored.length<=1000)selection=new Set(stored.map(String));}catch{}
  const limits = new Map(), openGroups = new Set(['','Civil']);
  const node = (tag, text, className) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;};
  const message = (text, error=false) => {el('capture-message').textContent=text;el('capture-message').classList.toggle('capture-error',error);const viewerMessage=el('capture-preview-message');if(viewerMessage&&el('capture-preview').open){viewerMessage.textContent=text;viewerMessage.classList.toggle('capture-error',error);}};
  function rememberSelection(){try{sessionStorage.setItem(selectionKey,JSON.stringify(Array.from(selection)));}catch{}}
  function reconcileSelection(){const present=new Set((saved?.photos||[]).map(p=>String(p.id)));selection=saved?.can_edit?new Set(Array.from(selection).filter(id=>present.has(id))):new Set();rememberSelection();}
  function selectPhoto(id,checked){if(!saved?.can_edit||stale||uploadBusy||mutationBusy||submitBusy)return;const key=String(id);if(!saved.photos.some(p=>String(p.id)===key))return;if(checked)selection.add(key);else selection.delete(key);rememberSelection();selectionControls();}
  function selectionControls(){
    const editable=!!saved?.can_edit,blocked=stale||uploadBusy||mutationBusy||submitBusy||generalBusy;
    el('capture-selection-toolbar').hidden=!editable;
    el('capture-selected-count').textContent=`${selection.size} selected of ${saved?.photos.length||0} saved photos`;
    el('capture-select-all').textContent=`Select all saved photos (${saved?.photos.length||0})`;
    el('capture-select-all').title='Select every saved photo across all categories, including collapsed groups and photos not yet shown.';
    el('capture-select-all').disabled=!editable||blocked||!saved?.photos.length;
    el('capture-clear-selection').disabled=!editable||blocked||!selection.size;
    const targetValid=categories.some(c=>c.value===bulkTarget);
    ['capture-bulk-category','capture-preview-bulk-category'].forEach(id=>{el(id).value=bulkTarget;el(id).disabled=!editable||blocked||!selection.size;});
    ['capture-move-selected','capture-preview-move-selected'].forEach(id=>{el(id).disabled=!editable||blocked||!selection.size||!targetValid;el(id).textContent=mutationBusy?'Please wait...':'Move selected';});
    const current=viewerItems[viewerIndex],savedViewer=viewerKind==='saved'&&!!current;
    el('capture-preview-select-label').hidden=el('capture-preview-selected-count').hidden=el('capture-preview-bulk-controls').hidden=!editable||!savedViewer;
    el('capture-preview-refresh').hidden=!editable||!savedViewer||!stale;el('capture-preview-refresh').disabled=uploadBusy||mutationBusy||submitBusy;el('capture-preview-select').disabled=!editable||blocked||!savedViewer;
    el('capture-preview-select').checked=savedViewer&&selection.has(String(current.id));
    el('capture-preview-selected-count').textContent=`${selection.size} selected`;
    el('capture-preview-select').setAttribute('aria-label',current?`Select ${current.name}`:'Select current saved photo');
    root.querySelectorAll('[data-select-saved-photo]').forEach(input=>{input.checked=selection.has(input.dataset.selectSavedPhoto);input.disabled=!editable||blocked;input.closest('.capture-photo-card')?.classList.toggle('is-selected',input.checked);});
  }
  const generalKey=field=>`${field.scope}:${field.id}`;
  const asText=value=>value===null||value===undefined?'':String(value);
  function generalSource(field){const names={assigned_account:'Assigned account',project_company:'Project company',assignment:'Task assignment',photo_exif:'Photo capture details',saved:'Saved site information',manual:'Entered on site',engineer:'Engineer entry'};const source=names[field.source]||asText(field.source).replaceAll('_',' ');return(field.prefilled?'Prefilled · ':'')+(source||'Not recorded')+(generalDirty.has(generalKey(field))?' · Unsaved edit':'');}
  function rememberGeneral(){try{if(!generalDirty.size){sessionStorage.removeItem(generalDraftKey);return;}sessionStorage.setItem(generalDraftKey,JSON.stringify({digest:generalExpectedDigest,values:Object.fromEntries(Array.from(generalDirty).map(key=>[key,generalDraft.get(key)])),baseline:Object.fromEntries(Array.from(generalDirty).map(key=>[key,generalBase.get(key)]))}));}catch{}}
  function generalStatus(text,error=false){el('capture-general-status').textContent=text;el('capture-general-status').classList.toggle('capture-error',error);}
  function restoreGeneral(){try{const draft=JSON.parse(sessionStorage.getItem(generalDraftKey)||'null');if(!draft||!draft.values||typeof draft.values!=='object'||typeof draft.digest!=='string')return;for(const field of generalInfo.fields){const key=generalKey(field);if(!field.editable||field.locked||typeof draft.values[key]!=='string')continue;if(draft.values[key]===asText(field.stored_value))continue;generalDraft.set(key,draft.values[key]);generalBase.set(key,asText(draft.baseline?.[key]));generalDirty.add(key);}if(generalDirty.size){generalExpectedDigest=draft.digest;generalStatus('Your unsaved site information has been restored.');}}catch{}}
  function updateGeneral(info){
    if(!info||typeof info.digest!=='string'||!Array.isArray(info.fields)||!Array.isArray(info.context)){generalInfo=null;generalLoaded=false;generalLoadError='Site information is unavailable.';el('capture-general-fields').textContent='Site information is unavailable. Refresh the saved site to retry.';generalStatus('Site information could not be loaded.',true);return;}
    const first=!generalLoaded;generalInfo=info;generalLoadError='';if(!info.can_edit){generalDirty.clear();generalDraft.clear();generalBase.clear();rememberGeneral();}
    if(first||!generalDirty.size)generalExpectedDigest=info.digest;
    for(const field of info.fields){const key=generalKey(field);if(!generalDirty.has(key)){generalDraft.set(key,asText(field.value));generalBase.set(key,asText(field.value));}}
    generalLoaded=true;if(first&&info.can_edit)restoreGeneral();
    generalNeedsSave=info.fields.some(field=>field.editable&&!field.locked&&asText(field.value)!==asText(field.stored_value));
    const context=el('capture-general-context');context.replaceChildren();info.context.forEach(item=>{const row=node('div');row.dataset.contextId=item.id;row.append(node('dt',item.label),node('dd',asText(item.value)||'Not recorded'));const source=node('small',asText(item.source).replaceAll('_',' '),'capture-info-source');row.append(source);context.append(row);});
    renderGeneralFields();
  }
  function renderGeneralFields(){
    if(!generalInfo)return;const signature=JSON.stringify(generalInfo.fields.map(field=>[field.scope,field.id,field.type,field.options,field.editable,field.locked]));
    if(signature!==generalSignature){const host=el('capture-general-fields');host.replaceChildren();generalInfo.fields.forEach((field,index)=>{
      const row=node('div',undefined,'capture-info-field'),title=node('label',field.label+(field.unit?' ('+field.unit+')':''));row.dataset.infoKey=generalKey(field);
      const type=field.type==='textarea'?'textarea':field.type==='select'?'select':'input',input=node(type);input.id=`capture-info-${field.scope}-${index}`;title.htmlFor=input.id;input.dataset.generalField=field.id;input.dataset.generalScope=field.scope;
      if(type==='input')input.type=['number','date'].includes(field.type)?field.type:'text';if(field.type==='number')input.step='any';if(type==='textarea')input.rows=2;if(Number.isInteger(field.max_length)&&field.max_length>0)input.maxLength=field.max_length;
      if(type==='select'){input.append(new Option('Not recorded',''));for(const option of field.options||[]){const value=typeof option==='object'?option.value:option;input.append(new Option(typeof option==='object'?option.label:value,value));}}
      const hint=node('small',undefined,'capture-info-source');hint.id=input.id+'-source';input.setAttribute('aria-describedby',hint.id);input.addEventListener('input',()=>generalChanged(field,input));input.addEventListener('change',()=>generalChanged(field,input));row.append(title,input,hint);host.append(row);
    });if(!generalInfo.fields.length)host.append(node('p','No additional site information is configured.','capture-help'));generalSignature=signature;}
    for(const field of generalInfo.fields){const key=generalKey(field),row=Array.from(el('capture-general-fields').children).find(n=>n.dataset.infoKey===key);if(!row)continue;const input=row.querySelector('[data-general-field]'),value=generalDraft.get(key)??asText(field.value);
      if(input.tagName==='SELECT'&&value&&!Array.from(input.options).some(option=>option.value===value))input.append(new Option(value+' (saved value)',value));
      if(input.value!==value)input.value=value;if(field.type==='date'&&value&&input.value===''){input.type='text';input.value=value;input.placeholder='YYYY-MM-DD';}
      input.readOnly=!!field.locked||!field.editable;row.querySelector('.capture-info-source').textContent=generalSource(field)+(field.source_note?' · '+field.source_note:'');row.classList.toggle('is-dirty',generalDirty.has(key));row.classList.toggle('has-source-conflict',!!field.suggestion_conflict);
    }
  }
  function generalChanged(field,input){field=generalInfo?.fields.find(current=>current.id===field.id&&current.scope===field.scope)||field;if(!generalInfo?.can_edit||field.locked||!field.editable||generalBusy||submitBusy)return;const key=generalKey(field);generalDraft.set(key,input.value);if(input.value===generalBase.get(key)&&!input.validity.badInput)generalDirty.delete(key);else generalDirty.add(key);el('capture-uploads-finished').checked=false;rememberGeneral();generalStatus(generalDirty.size?'Unsaved site information. Save it now, or Submit to QA will save it first.':'');const row=input.closest('.capture-info-field');row.classList.toggle('is-dirty',generalDirty.has(key));row.querySelector('.capture-info-source').textContent=generalSource(field)+(field.source_note?' · '+field.source_note:'');controls();}
  function generalControls(){const busy=uploadBusy||mutationBusy||submitBusy||generalBusy,editable=!!generalInfo?.can_edit&&!stale;
    el('capture-general-panel').hidden=currentView!=='general';el('capture-photo-area').hidden=currentView==='general';el('capture-general-tab').disabled=busy;el('capture-general-tab').setAttribute('aria-selected',String(currentView==='general'));el('capture-general-tab').setAttribute('aria-pressed',String(currentView==='general'));
    el('capture-general-state').textContent=generalDirty.size?'Unsaved':generalInfo?.read_only?'Read-only':'Site data';el('capture-general-mode').textContent=!generalLoaded?(generalLoadError?'Site information unavailable':'Loading saved site data...'):generalInfo.frozen?'Submitted snapshot · read-only':generalInfo.read_only?'Read-only':generalDirty.size?'Unsaved changes':generalNeedsSave?'Prefilled information':'Saved site data';
    el('capture-general-save').hidden=!!generalInfo&&!generalInfo.can_edit;el('capture-general-save').disabled=!editable||busy||!generalLoaded||!generalDirty.size&&!generalNeedsSave;el('capture-general-save').textContent=generalBusy?'Saving site information...':'Save site information';el('capture-general-discard').hidden=!!generalInfo&&!generalInfo.can_edit;el('capture-general-discard').disabled=busy||!generalDirty.size;
    el('capture-general-fields').querySelectorAll('[data-general-field]').forEach(input=>{const field=generalInfo?.fields.find(f=>f.id===input.dataset.generalField&&f.scope===input.dataset.generalScope);input.disabled=!editable||busy||!field?.editable||!!field?.locked;});
  }
  function showGeneral(){currentView='general';controls();}
  async function saveGeneral(fromSubmit=false){
    if(!generalInfo||!generalLoaded)throw new Error('Refresh the site information before saving or submitting.');if(!generalInfo.can_edit)return saved;if(generalBusy||uploadBusy||mutationBusy||submitBusy&&!fromSubmit)throw new Error('Wait for the active save or upload to finish.');
    const site_information={},general_info={};for(const field of generalInfo.fields){if(!field.editable||field.locked)continue;const value=generalDraft.get(generalKey(field))??asText(field.value);if(field.scope==='site')site_information[field.id]=value;else if(field.scope==='general')general_info[field.id]=value;}
    generalBusy=true;controls();generalStatus('Saving site information...');
    try{const result=await request(root.dataset.informationUrl,{expected_digest:saved.digest,expected_general_digest:generalExpectedDigest,site_information,general_info});if(!Array.isArray(result.photos)||typeof result.digest!=='string'||!result.general_information||typeof result.general_information.digest!=='string'||!Array.isArray(result.general_information.fields)||!Array.isArray(result.general_information.context))throw new Error('The server did not confirm the saved site information. Refresh before submitting.');generalDirty.clear();generalDraft.clear();generalBase.clear();generalLoaded=false;generalSignature='';rememberGeneral();acceptState(result);generalStatus('Site information saved.');return result;}
    catch(error){generalStatus(error.message,true);message('Site information was not confirmed as saved. Your entries are kept. '+error.message,true);throw error;}
    finally{generalBusy=false;controls();}
  }
  function safeURL(value) {try {const u=new URL(value,location.href);return u.origin===location.origin?u.href:'';}catch{return '';}}
  async function request(url, data) {
    const options={credentials:'same-origin',headers:{'Accept':'application/json'}};
    if(data!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.headers['X-CSRFToken']=csrf;options.body=JSON.stringify(data);}
    let response;
    try{response=await fetch(url,options);}catch{throw new Error('Connection interrupted. Your saved photos are preserved. Please retry.');}
    let result;try{result=await response.json();}catch{throw new Error('The server returned an unreadable response. Refresh before continuing.');}
    if(!response.ok){const error=new Error(result.error||result.message||`Request failed (${response.status}).`);error.status=response.status;throw error;}
    return result;
  }
  function incomplete(){return pending.some(p=>p.status!=='uploaded');}
  function controls(){
    const busy=uploadBusy||mutationBusy||submitBusy||generalBusy;
    const editable=!!saved?.can_edit&&!stale;
    el('capture-upload-panel').hidden=!!saved&&!saved.can_edit;
    el('capture-submit-panel').hidden=!!saved?.submitted;
    el('capture-submit-confirmation').hidden=!saved?.submitted;
    el('capture-upload').disabled=!editable||busy||!pending.some(p=>p.status==='ready');
    el('capture-retry-failed').hidden=!pending.some(p=>p.status==='failed'&&p.valid);
    el('capture-retry-failed').disabled=!editable||busy;
    el('capture-files').disabled=el('capture-camera').disabled=!editable||busy;
    el('capture-refresh').disabled=busy;
    el('capture-uploads-finished').disabled=busy||!saved?.can_submit||stale||incomplete()||!generalLoaded;
    el('capture-submit-qa').disabled=busy||!saved?.can_submit||stale||incomplete()||!generalLoaded||!el('capture-uploads-finished').checked;
    root.querySelectorAll('[data-category]').forEach(b=>{b.disabled=busy;const active=currentView==='photos'&&b.dataset.category===category;b.setAttribute('aria-pressed',String(active));b.setAttribute('aria-selected',String(active));});
    root.querySelectorAll('[data-move-photo],[data-remove-photo],[data-pending-category],[data-remove-pending]').forEach(b=>b.disabled=busy||!editable);
    el('capture-upload-category').textContent=`Add photos to ${label(category)}`;
    let guidance=generalDirty.size?'Submit to QA will save your edited site information first.':'Finish uploading and review the uploaded photos below before submitting.';
    if(stale)guidance='Refresh the saved site before submitting.';
    else if(incomplete())guidance='Upload or remove all selected photos before submitting. Retry any failed uploads.';
    else if(saved?.config_error)guidance=saved.config_error;
    else if(saved&&!saved.can_submit&&!saved.submitted)guidance='Submission is unavailable for the current task stage or your assignment.';
    el('capture-submit-guidance').textContent=guidance;
    selectionControls();
    generalControls();
  }
  function categorySelect(value,onChange,attribute){
    const select=node('select');select.setAttribute('aria-label','Photo category');select.setAttribute(attribute,'');
    if(!categories.some(c=>c.value===value)){const legacy=node('option','Uncategorised (existing photos)');legacy.value='__legacy__';legacy.disabled=true;select.append(legacy);}categories.forEach(c=>{const option=node('option',c.label);option.value=c.value;select.append(option);});select.value=categories.some(c=>c.value===value)?value:'__legacy__';select.addEventListener('change',()=>onChange(select.value));return select;
  }
  function thumbnail(src,filename,action,attribute){
    const button=node('button',undefined,'capture-thumbnail');button.type='button';button.setAttribute('aria-label',`Preview ${filename}`);button.setAttribute(attribute,'');
    const img=node('img');img.src=src;img.alt=filename;img.loading='lazy';img.decoding='async';img.addEventListener('error',()=>{img.alt='Preview unavailable';button.classList.add('capture-preview-unavailable');});button.append(img);button.addEventListener('click',action);return button;
  }
  function renderPending(){
    const list=el('capture-pending-list');list.replaceChildren();const visible=pending.filter(p=>p.status!=='uploaded');list.hidden=!visible.length;
    visible.forEach(p=>{
      const card=node('article',undefined,'capture-pending-card');card.dataset.pendingId=p.key;
      card.append(thumbnail(p.url,p.file.name,()=>previewPending(p.key),'data-preview-pending'));
      const body=node('div',undefined,'capture-photo-copy');body.append(node('strong',p.file.name,'capture-photo-name'));
      body.append(categorySelect(p.category,value=>{p.category=value;},'data-pending-category'));
      body.append(node('small',p.status==='failed'?p.error:p.status==='uploading'?'Uploading…':'Selected · not yet uploaded',p.status==='failed'?'capture-error':''));
      const actions=node('div',undefined,'capture-photo-actions'),remove=node('button','Remove');remove.type='button';remove.dataset.removePending=p.key;remove.addEventListener('click',()=>{URL.revokeObjectURL(p.url);pending=pending.filter(v=>v.key!==p.key);el('capture-uploads-finished').checked=false;renderPending();controls();});actions.append(remove);body.append(actions);card.append(body);list.append(card);
    });controls();
  }
  function renderPhotos(){
    const grid=el('capture-photo-grid');grid.replaceChildren();const photos=saved?.photos||[];
    el('capture-total').textContent=`${photos.length} saved photo${photos.length===1?'':'s'}`;
    galleryCategories.forEach(c=>{
      const groupPhotos=photos.filter(p=>(p.group||'')===c.value);
      const counter=root.querySelector(`[data-category-count="${c.value}"]`);if(counter)counter.textContent=groupPhotos.length;
      if(!groupPhotos.length)return;
      const group=node('details',undefined,'capture-category-group');group.dataset.photoCategory=c.value;group.open=openGroups.has(c.value)||!!saved.submitted;
      group.addEventListener('toggle',()=>group.open?openGroups.add(c.value):openGroups.delete(c.value));
      group.append(node('summary',`${c.label} · ${groupPhotos.length}`));const list=node('div',undefined,'capture-category-photos');
      const limit=limits.get(c.value)||36;
      groupPhotos.slice(0,limit).forEach(photo=>{
        const card=node('article',undefined,'capture-photo-card');card.dataset.photoId=photo.id;
        card.append(thumbnail(safeURL(photo.preview_url)||safeURL(photo.original_url),photo.filename,()=>previewSaved(photo.id),'data-preview-photo'));
        const body=node('div',undefined,'capture-photo-copy');body.append(node('strong',photo.filename,'capture-photo-name'));
        if(saved.can_edit){const choose=node('label',undefined,'capture-photo-select'),checkbox=node('input');checkbox.type='checkbox';checkbox.dataset.selectSavedPhoto=String(photo.id);checkbox.checked=selection.has(String(photo.id));checkbox.setAttribute('aria-label',`Select ${photo.filename}`);checkbox.addEventListener('change',()=>selectPhoto(photo.id,checkbox.checked));choose.append(checkbox,node('span','Select photo'));body.append(choose);card.classList.toggle('is-selected',checkbox.checked);body.append(categorySelect(photo.group,value=>movePhoto(photo,value),'data-move-photo'));
          const actions=node('div',undefined,'capture-photo-actions'),remove=node('button','Remove');remove.type='button';remove.dataset.removePhoto=photo.id;remove.addEventListener('click',()=>removePhoto(photo));actions.append(remove);body.append(actions);
        }else body.append(node('small',c.label));card.append(body);list.append(card);
      });group.append(list);
      if(groupPhotos.length>limit){const more=node('button',`Show ${Math.min(36,groupPhotos.length-limit)} more photos`,'capture-load-more');more.type='button';more.addEventListener('click',()=>{limits.set(c.value,limit+36);openGroups.add(c.value);renderPhotos();controls();});group.append(more);}
      grid.append(group);
    });
    if(!photos.length)grid.append(node('p','No uploaded photos yet. Choose a category and add the site photos above.','capture-empty'));
    const uncategorised=photos.filter(photo=>!photo.group).length;el('capture-uncategorised-notice').hidden=!uncategorised;el('capture-uncategorised-notice').textContent=`${uncategorised} existing uncategorised photo${uncategorised===1?' is':'s are'} preserved below.${saved?.can_edit?' Move them to Civil, Electrical or Tower when appropriate.':''}`;
    el('capture-photo-guidance').textContent=saved?.can_edit?'Preview photos and correct their categories before submitting.':'Submitted evidence is read-only at this workflow stage.';
  }
  function renderSite(){
    const correction=el('capture-correction-reason');correction.hidden=!saved.can_edit||!saved.correction_reason;correction.textContent=saved.correction_reason?'Returned for correction: '+saved.correction_reason:'';
    const stages={engineer:'Engineer preparation',quality_engineer:'QA review',team_lead:'Team Lead review',client:'Client review',customer:'Client review',closed:'Closed',completed:'Completed',final:'Completed'};
    el('capture-stage').textContent=stages[saved.stage]||String(saved.stage||'Engineer preparation').replaceAll('_',' ');
    const info=el('capture-site-info'),base=[['Site ID',saved.site_id],['Project',saved.project]];
    const extra=saved.site_info||{};[['Site name',extra.site_name],['Address',extra.address],['City',extra.city],['Region',extra.region]].forEach(pair=>{if(pair[1])base.push(pair);});
    info.replaceChildren();base.forEach(([key,value])=>{const d=node('div');d.append(node('dt',key),node('dd',value||'Not recorded'));info.append(d);});
    if(saved.submitted)el('capture-confirmation-copy').textContent=`Your site information and ${saved.photos.length} photo${saved.photos.length===1?'':'s'} are saved and submitted${saved.qa_name?' to '+saved.qa_name:' to QA'}. You can follow the task status in My tasks.`;
  }
  function renderRecovery(){
    const box=el('capture-recovery');box.replaceChildren();const sessions=saved?.upload_state?.sessions||[];
    const outstanding=sessions.filter(s=>['open','active','stale','interrupted'].includes(s.status));box.hidden=!outstanding.length||!saved.can_edit;
    if(box.hidden)return;
    box.append(node('h2','Unfinished upload session'));
    outstanding.forEach(session=>{
      const row=node('div');row.append(node('p',session.recoverable?'An interrupted upload can be closed safely. Completed photos will stay saved.':'Another upload is still active. Wait until it finishes, or refresh after an interruption.'));
      if(session.recoverable||session.can_finish){const button=node('button',session.recoverable?'Recover interrupted upload':'Finish my upload session');button.type='button';button.addEventListener('click',async()=>{if(uploadBusy||mutationBusy)return;mutationBusy=true;controls();try{await request(root.dataset.sessionUrl,{action:session.recoverable?'recover':'finish',token:session.token,reason:'Engineer recovered an interrupted site photo upload before QA submission.'});await load();message('Upload session closed. All completed photos are preserved.');}catch(error){message(error.message,true);}finally{mutationBusy=false;controls();}});row.append(button);}
      box.append(row);
    });
  }
  function acceptState(value){if(!Array.isArray(value.photos)||typeof value.digest!=='string')throw new Error('The saved site response is incomplete. Please refresh.');const current=viewerKind==='saved'?viewerItems[viewerIndex]?.id:null;saved=value;stale=false;reconcileSelection();renderSite();updateGeneral(value.general_information);renderPhotos();renderRecovery();if(viewerKind==='saved'&&viewerItems.length){viewerItems=saved.photos.map(viewerPhoto);const index=viewerItems.findIndex(photo=>photo.id===current);viewerIndex=index>=0?index:Math.min(viewerIndex,viewerItems.length-1);if(el('capture-preview').open){if(viewerIndex>=0)renderPreview();else el('capture-preview').close();}}controls();return value;}
  async function load(){
    try{return acceptState(await request(root.dataset.stateUrl));}
    catch(error){stale=true;if(!generalLoaded){generalLoadError=error.message;el('capture-general-fields').textContent='Site information could not be loaded. Refresh the saved site to retry.';generalStatus(error.message,true);}controls();throw error;}
  }
  function addFiles(files){
    if(!saved?.can_edit||stale||uploadBusy)return;
    el('capture-uploads-finished').checked=false;
    for(const file of files){let error='';if(!/\.(jpe?g|png|webp)$/i.test(file.name)||file.type&&!['image/jpeg','image/png','image/webp'].includes(file.type))error='Unsupported file. Choose JPEG, PNG or WebP.';else if(file.size>5*1024*1024)error='Photo exceeds the 5 MB limit.';else if(!file.size)error='This file is empty.';
      pending.push({key:String(++serial),file,category,url:URL.createObjectURL(file),valid:!error,status:error?'failed':'ready',error});}
    renderPending();message('Selected photos are ready. Click Upload selected photos to save them.');
  }
  function xhrUpload(batch,onProgress){return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest(),data=new FormData();data.append('group',batch[0].category);batch.forEach(p=>data.append('files',p.file));if(uploadToken)data.append('processing_upload_token',uploadToken);
    xhr.open('POST',root.dataset.uploadUrl);xhr.withCredentials=true;xhr.setRequestHeader('X-CSRFToken',csrf);xhr.setRequestHeader('Accept','application/json');xhr.upload.addEventListener('progress',event=>{if(event.lengthComputable)onProgress(event.loaded/event.total);});
    xhr.addEventListener('load',()=>{let response;try{response=JSON.parse(xhr.responseText);}catch{reject(new Error('Unreadable upload response. Retry the selected files; exact duplicates will be reused.'));return;}if(xhr.status>=200&&xhr.status<300)resolve(response);else{const error=new Error(response.error||response.message||`Upload failed (${xhr.status}).`);error.status=xhr.status;reject(error);}});
    xhr.addEventListener('error',()=>reject(new Error('Connection interrupted. Retry the failed photos; saved originals are preserved.')));xhr.addEventListener('abort',()=>reject(new Error('Upload interrupted. Please retry the selected photos.')));xhr.send(data);
  });}
  async function upload(retry=false){
    if(uploadBusy||mutationBusy||submitBusy||!saved?.can_edit||stale)return;
    if(retry)pending.filter(p=>p.status==='failed'&&p.valid).forEach(p=>{p.status='ready';p.error='';});
    const selected=pending.filter(p=>p.status==='ready');if(!selected.length)return;
    uploadBusy=true;el('capture-uploads-finished').checked=false;el('capture-upload-progress').hidden=false;el('capture-progress').value=0;controls();
    let uploaded=0,duplicates=0,failed=false,processedBytes=0;const totalBytes=selected.reduce((n,p)=>n+p.file.size,0)||1;
    const batches=[];categories.forEach(c=>{const files=selected.filter(p=>p.category===c.value);for(let i=0;i<files.length;i+=20)batches.push(files.slice(i,i+20));});
    try{
      const session=await request(root.dataset.sessionUrl,{action:'start'});uploadToken=session.token||null;
      if(!uploadToken)throw new Error('An upload session could not be started. Refresh and retry.');
      heartbeat=setInterval(()=>request(root.dataset.sessionUrl,{action:'heartbeat',token:uploadToken}).catch(error=>message(error.message,true)),30000);
      for(const batch of batches){
        batch.forEach(p=>p.status='uploading');renderPending();const bytes=batch.reduce((n,p)=>n+p.file.size,0);
        try{
          const result=await xhrUpload(batch,fraction=>{el('capture-progress').value=Math.min(99,100*(processedBytes+bytes*fraction)/totalBytes);el('capture-progress-label').textContent=`Uploading ${uploaded} of ${selected.length} photos · ${Math.round(el('capture-progress').value)}%`;});
          if(!Array.isArray(result.photos)||result.photos.length!==batch.length)throw new Error('The upload response was incomplete. Retry these files; saved duplicates will be reused.');
          result.photos.forEach(p=>{if(p.duplicate)duplicates++;});batch.forEach(p=>{p.status='uploaded';URL.revokeObjectURL(p.url);uploaded++;});
        }catch(error){failed=true;batch.forEach(p=>{p.status='failed';p.error=error.message;});message(error.message,true);if(!error.status||[401,403,409].includes(error.status))break;}
        processedBytes+=bytes;renderPending();
      }
    }catch(error){failed=true;selected.filter(p=>p.status!=='uploaded').forEach(p=>{p.status='failed';p.error=error.message;});message(error.message,true);}
    finally{
      clearInterval(heartbeat);heartbeat=null;
      if(uploadToken){try{await request(root.dataset.sessionUrl,{action:'finish',token:uploadToken});}catch(error){failed=true;try{await request(root.dataset.sessionUrl,{action:'interrupt',token:uploadToken});}catch{}message(`Photos are preserved. ${error.message}`,true);}uploadToken=null;}
      selected.filter(p=>p.status==='uploading').forEach(p=>{p.status='failed';p.error='Upload interrupted. Retry this photo.';});
      try{await load();}catch(error){failed=true;message(error.message,true);}
      uploadBusy=false;pending=pending.filter(p=>p.status!=='uploaded');renderPending();controls();
      el('capture-progress').value=100*uploaded/selected.length;
      el('capture-progress-label').textContent=`${uploaded} of ${selected.length} photos saved${duplicates?' · '+duplicates+' exact duplicates reused':''}${failed?' · retry remaining photos':''}`;
      if(!failed)message(`${uploaded} photos saved${duplicates?' ('+duplicates+' exact duplicates reused)':''}. Review the categories, then submit to QA.`);
    }
  }
  async function mutate(url,data,success){
    if(uploadBusy||mutationBusy||submitBusy||stale)return;
    mutationBusy=true;el('capture-uploads-finished').checked=false;controls();
    try{await request(url,{...data,expected_digest:saved.digest});await load();message(success);}
    catch(error){try{await load();}catch{}message(error.message,true);}
    finally{mutationBusy=false;controls();}
  }
  async function movePhoto(photo,value){if(value===(photo.group||''))return;await mutate(root.dataset.categoryUrl,{photo_id:photo.id,group:value},`Photo moved to ${label(value)}.`);openGroups.add(value);renderPhotos();controls();}
  async function moveSelected(){
    if(!saved?.can_edit||stale||uploadBusy||mutationBusy||submitBusy||!selection.size||!categories.some(c=>c.value===bulkTarget))return;
    const ids=Array.from(selection).map(Number),target=bulkTarget;mutationBusy=true;el('capture-uploads-finished').checked=false;controls();
    try{const result=await request(root.dataset.categoryUrl,{photo_ids:ids,group:target,expected_digest:saved.digest});if(!Array.isArray(result.photos)||typeof result.digest!=='string'||ids.some(id=>!result.photos.some(photo=>photo.id===id&&(photo.group||'')===target)))throw new Error('The server did not confirm every selected photo category.');openGroups.add(target);acceptState(result);message(`${ids.length} selected photo${ids.length===1?' is':'s are'} now in ${label(target)}. Selection kept.`);}
    catch(error){stale=true;message(`Move could not be confirmed. Your selection is kept. ${error.message} Refresh saved photos before retrying.`,true);}
    finally{mutationBusy=false;controls();}
  }
  async function removePhoto(photo){if(!confirm(`Remove “${photo.filename}” from this submission? Saved source evidence is retained according to the application retention rules.`))return;await mutate(root.dataset.removeUrl,{photo_id:photo.id},'Photo removed from this submission.');}
  function viewerPhoto(photo){return{id:photo.id,name:photo.filename,src:safeURL(photo.preview_url)||safeURL(photo.original_url),original:safeURL(photo.original_url)};}
  function previewSaved(id){viewerKind='saved';viewerItems=(saved?.photos||[]).map(viewerPhoto);viewerIndex=viewerItems.findIndex(p=>p.id===id);openPreview();}
  function previewPending(key){viewerKind='pending';viewerItems=pending.filter(p=>p.status!=='uploaded').map(p=>({id:p.key,name:p.file.name,src:p.url,original:''}));viewerIndex=viewerItems.findIndex(p=>p.id===key);openPreview();}
  function openPreview(){if(viewerIndex<0)return;focusedBeforeViewer=document.activeElement;el('capture-preview-message').textContent='';renderPreview();el('capture-preview').showModal();el('capture-preview-close').focus();}
  function renderPreview(){const photo=viewerItems[viewerIndex];el('capture-preview-title').textContent=photo.name;el('capture-preview-image').hidden=false;el('capture-preview-error').hidden=true;if(el('capture-preview-image').src!==photo.src)el('capture-preview-image').src=photo.src;el('capture-preview-image').alt=photo.name;el('capture-preview-position').textContent=`${viewerIndex+1} / ${viewerItems.length}`;el('capture-preview-previous').disabled=viewerIndex===0;el('capture-preview-next').disabled=viewerIndex===viewerItems.length-1;el('capture-preview-original').hidden=!photo.original;if(photo.original)el('capture-preview-original').href=photo.original;selectionControls();}
  el('capture-preview-image').addEventListener('error',()=>{el('capture-preview-image').hidden=true;el('capture-preview-error').hidden=false;});
  el('capture-preview-close').addEventListener('click',()=>el('capture-preview').close());el('capture-preview').addEventListener('close',()=>focusedBeforeViewer?.focus());
  el('capture-preview-previous').addEventListener('click',()=>{if(viewerIndex>0){viewerIndex--;renderPreview();}});el('capture-preview-next').addEventListener('click',()=>{if(viewerIndex<viewerItems.length-1){viewerIndex++;renderPreview();}});
  el('capture-preview').addEventListener('keydown',event=>{if(event.target.matches('input,select,textarea'))return;if(event.key==='ArrowLeft'&&viewerIndex>0){viewerIndex--;renderPreview();}if(event.key==='ArrowRight'&&viewerIndex<viewerItems.length-1){viewerIndex++;renderPreview();}});
  el('capture-select-all').addEventListener('click',()=>{if(!saved?.can_edit||stale||uploadBusy||mutationBusy||submitBusy)return;selection=new Set(saved.photos.map(p=>String(p.id)));rememberSelection();selectionControls();});
  el('capture-clear-selection').addEventListener('click',()=>{if(uploadBusy||mutationBusy||submitBusy)return;selection.clear();rememberSelection();selectionControls();});
  el('capture-preview-select').addEventListener('change',event=>{if(viewerKind==='saved')selectPhoto(viewerItems[viewerIndex]?.id,event.target.checked);});
  ['capture-bulk-category','capture-preview-bulk-category'].forEach(id=>el(id).addEventListener('change',event=>{bulkTarget=event.target.value;selectionControls();}));
  ['capture-move-selected','capture-preview-move-selected'].forEach(id=>el(id).addEventListener('click',moveSelected));
  el('capture-preview-refresh').addEventListener('click',async()=>{if(uploadBusy||mutationBusy||submitBusy)return;mutationBusy=true;controls();try{await load();message('Saved photos refreshed.');}catch(error){message(error.message,true);}finally{mutationBusy=false;controls();}});
  el('capture-general-tab').addEventListener('click',showGeneral);root.querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>{currentView='photos';category=button.dataset.category;openGroups.add(category);renderPhotos();controls();}));
  ['capture-files','capture-camera'].forEach(id=>el(id).addEventListener('change',event=>{addFiles(event.target.files);event.target.value='';}));
  const drop=el('capture-drop-zone');['dragenter','dragover'].forEach(type=>drop.addEventListener(type,event=>{event.preventDefault();drop.classList.add('is-dragging');}));['dragleave','drop'].forEach(type=>drop.addEventListener(type,event=>{event.preventDefault();drop.classList.remove('is-dragging');if(type==='drop')addFiles(event.dataTransfer.files);}));
  el('capture-general-form').addEventListener('submit',async event=>{event.preventDefault();try{await saveGeneral();}catch{}});
  el('capture-general-discard').addEventListener('click',async()=>{if(!generalDirty.size||generalBusy||uploadBusy||mutationBusy||submitBusy)return;if(!confirm('Discard your unsaved General Info changes and reload the saved site information?'))return;generalBusy=true;controls();try{const value=await request(root.dataset.stateUrl);if(!Array.isArray(value.photos)||typeof value.digest!=='string'||!Array.isArray(value.general_information?.fields))throw new Error('The saved site information could not be confirmed. Your draft is kept.');generalDirty.clear();generalDraft.clear();generalBase.clear();generalLoaded=false;generalSignature='';rememberGeneral();acceptState(value);generalStatus('Saved site information reloaded.');}catch(error){generalStatus(error.message,true);}finally{generalBusy=false;controls();}});
  el('capture-upload-form').addEventListener('submit',event=>{event.preventDefault();upload();});el('capture-retry-failed').addEventListener('click',()=>upload(true));
  el('capture-refresh').addEventListener('click',()=>load().then(()=>message('Saved site refreshed.')).catch(error=>message(error.message,true)));
  el('capture-uploads-finished').addEventListener('change',controls);
  el('capture-submit-form').addEventListener('submit',async event=>{
    event.preventDefault();if(el('capture-submit-qa').disabled||!el('capture-uploads-finished').checked)return;if(!el('capture-general-form').checkValidity()){showGeneral();el('capture-general-form').reportValidity();return;}
    submitBusy=true;controls();let siteSaved=false;try{await saveGeneral(true);siteSaved=true;await request(root.dataset.submitUrl,{uploads_finished:true,expected_digest:saved.digest});await load();if(!saved.submitted)throw new Error('Submission was not confirmed by the server. Refresh the task status before trying again.');message('Submitted to QA. Your saved site information and photos are preserved.');el('capture-submit-confirmation').scrollIntoView({behavior:'smooth',block:'center'});}
    catch(error){message((siteSaved?'Site information is saved. QA submission was not confirmed. ':'')+error.message,true);if(!siteSaved){showGeneral();el('capture-general-status').tabIndex=-1;el('capture-general-status').focus();}else try{await load();}catch{};}finally{submitBusy=false;controls();}
  });
  addEventListener('beforeunload',event=>{if(uploadBusy||mutationBusy||submitBusy||generalBusy||generalDirty.size||incomplete()){event.preventDefault();event.returnValue='';}});
  addEventListener('pagehide',()=>{if(uploadToken)fetch(root.dataset.sessionUrl,{method:'POST',credentials:'same-origin',keepalive:true,headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({action:'interrupt',token:uploadToken})}).catch(()=>{});});
  controls();load().then(()=>message('')).catch(error=>message(error.message,true));
})();
