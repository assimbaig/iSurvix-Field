(() => {
  'use strict';
  const root = document.getElementById('engineer-capture');
  if (!root) return;
  const el = id => document.getElementById(id);
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const categories = [{value:'',label:'General Info'},{value:'Civil',label:'Civil'},{value:'Electrical',label:'Electrical'},{value:'Tower',label:'Tower'}];
  const label = value => categories.find(c => c.value === value)?.label || 'General Info';
  let saved = null, stale = true, category = '', pending = [], serial = 0;
  let uploadBusy = false, mutationBusy = false, submitBusy = false, uploadToken = null, heartbeat = null;
  let viewerItems = [], viewerIndex = 0, viewerKind = 'saved', focusedBeforeViewer = null, bulkTarget = '__choose__';
  const selectionKey = `capture-selected-photos:${location.pathname}`;
  let selection = new Set();
  try {const stored=JSON.parse(sessionStorage.getItem(selectionKey)||'[]');if(Array.isArray(stored)&&stored.length<=1000)selection=new Set(stored.map(String));}catch{}
  const limits = new Map(), openGroups = new Set(['']);
  const node = (tag, text, className) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;};
  const message = (text, error=false) => {el('capture-message').textContent=text;el('capture-message').classList.toggle('capture-error',error);const viewerMessage=el('capture-preview-message');if(viewerMessage&&el('capture-preview').open){viewerMessage.textContent=text;viewerMessage.classList.toggle('capture-error',error);}};
  function rememberSelection(){try{sessionStorage.setItem(selectionKey,JSON.stringify(Array.from(selection)));}catch{}}
  function reconcileSelection(){const present=new Set((saved?.photos||[]).map(p=>String(p.id)));selection=saved?.can_edit?new Set(Array.from(selection).filter(id=>present.has(id))):new Set();rememberSelection();}
  function selectPhoto(id,checked){if(!saved?.can_edit||stale||uploadBusy||mutationBusy||submitBusy)return;const key=String(id);if(!saved.photos.some(p=>String(p.id)===key))return;if(checked)selection.add(key);else selection.delete(key);rememberSelection();selectionControls();}
  function selectionControls(){
    const editable=!!saved?.can_edit,blocked=stale||uploadBusy||mutationBusy||submitBusy;
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
    const busy=uploadBusy||mutationBusy||submitBusy;
    const editable=!!saved?.can_edit&&!stale;
    el('capture-upload-panel').hidden=!!saved&&!saved.can_edit;
    el('capture-submit-panel').hidden=!!saved?.submitted;
    el('capture-submit-confirmation').hidden=!saved?.submitted;
    el('capture-upload').disabled=!editable||busy||!pending.some(p=>p.status==='ready');
    el('capture-retry-failed').hidden=!pending.some(p=>p.status==='failed'&&p.valid);
    el('capture-retry-failed').disabled=!editable||busy;
    el('capture-files').disabled=el('capture-camera').disabled=!editable||busy;
    el('capture-refresh').disabled=busy;
    el('capture-uploads-finished').disabled=busy||!saved?.can_submit||stale||incomplete();
    el('capture-submit-qa').disabled=busy||!saved?.can_submit||stale||incomplete()||!el('capture-uploads-finished').checked;
    root.querySelectorAll('[data-category]').forEach(b=>{b.disabled=busy||!editable;b.setAttribute('aria-pressed',String(b.dataset.category===category));});
    root.querySelectorAll('[data-move-photo],[data-remove-photo],[data-pending-category],[data-remove-pending]').forEach(b=>b.disabled=busy||!editable);
    el('capture-upload-category').textContent=`Add photos to ${label(category)}`;
    let guidance='Finish uploading and review the uploaded photos below before submitting.';
    if(stale)guidance='Refresh the saved site before submitting.';
    else if(incomplete())guidance='Upload or remove all selected photos before submitting. Retry any failed uploads.';
    else if(saved?.config_error)guidance=saved.config_error;
    else if(saved&&!saved.can_submit&&!saved.submitted)guidance='Submission is unavailable for the current task stage or your assignment.';
    el('capture-submit-guidance').textContent=guidance;
    selectionControls();
  }
  function categorySelect(value,onChange,attribute){
    const select=node('select');select.setAttribute('aria-label','Photo category');select.setAttribute(attribute,'');
    categories.forEach(c=>{const option=node('option',c.label);option.value=c.value;select.append(option);});select.value=value||'';select.addEventListener('change',()=>onChange(select.value));return select;
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
    categories.forEach(c=>{
      const groupPhotos=photos.filter(p=>(p.group||'')===c.value);
      root.querySelector(`[data-category-count="${c.value}"]`).textContent=groupPhotos.length;
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
  function acceptState(value){if(!Array.isArray(value.photos)||typeof value.digest!=='string')throw new Error('The saved site response is incomplete. Please refresh.');const current=viewerKind==='saved'?viewerItems[viewerIndex]?.id:null;saved=value;stale=false;reconcileSelection();renderSite();renderPhotos();renderRecovery();if(viewerKind==='saved'&&viewerItems.length){viewerItems=saved.photos.map(viewerPhoto);const index=viewerItems.findIndex(photo=>photo.id===current);viewerIndex=index>=0?index:Math.min(viewerIndex,viewerItems.length-1);if(el('capture-preview').open){if(viewerIndex>=0)renderPreview();else el('capture-preview').close();}}controls();return value;}
  async function load(){
    try{return acceptState(await request(root.dataset.stateUrl));}
    catch(error){stale=true;controls();throw error;}
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
  root.querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>{category=button.dataset.category;openGroups.add(category);renderPhotos();controls();}));
  ['capture-files','capture-camera'].forEach(id=>el(id).addEventListener('change',event=>{addFiles(event.target.files);event.target.value='';}));
  const drop=el('capture-drop-zone');['dragenter','dragover'].forEach(type=>drop.addEventListener(type,event=>{event.preventDefault();drop.classList.add('is-dragging');}));['dragleave','drop'].forEach(type=>drop.addEventListener(type,event=>{event.preventDefault();drop.classList.remove('is-dragging');if(type==='drop')addFiles(event.dataTransfer.files);}));
  el('capture-upload-form').addEventListener('submit',event=>{event.preventDefault();upload();});el('capture-retry-failed').addEventListener('click',()=>upload(true));
  el('capture-refresh').addEventListener('click',()=>load().then(()=>message('Saved site refreshed.')).catch(error=>message(error.message,true)));
  el('capture-uploads-finished').addEventListener('change',controls);
  el('capture-submit-form').addEventListener('submit',async event=>{
    event.preventDefault();if(el('capture-submit-qa').disabled||!el('capture-uploads-finished').checked)return;
    submitBusy=true;controls();try{await request(root.dataset.submitUrl,{uploads_finished:true,expected_digest:saved.digest});await load();if(!saved.submitted)throw new Error('Submission was not confirmed by the server. Refresh the task status before trying again.');message('Submitted to QA. Your saved photos are preserved.');el('capture-submit-confirmation').scrollIntoView({behavior:'smooth',block:'center'});}
    catch(error){message(error.message,true);try{await load();}catch{};}finally{submitBusy=false;controls();}
  });
  addEventListener('beforeunload',event=>{if(uploadBusy||mutationBusy||submitBusy||incomplete()){event.preventDefault();event.returnValue='';}});
  addEventListener('pagehide',()=>{if(uploadToken)fetch(root.dataset.sessionUrl,{method:'POST',credentials:'same-origin',keepalive:true,headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({action:'interrupt',token:uploadToken})}).catch(()=>{});});
  controls();load().then(()=>message('')).catch(error=>message(error.message,true));
})();
