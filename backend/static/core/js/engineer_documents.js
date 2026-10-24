/* Engineer source documents share the existing saved submission and upload
 * session. The component never exposes processing or checklist matching. */
(function(global,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else global.iSurvixEngineerDocuments=api;
})(typeof window==='undefined'?globalThis:window,function(){
  'use strict';
  const supported={pdf:['application/pdf'],xlsx:['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
    jpg:['image/jpeg'],jpeg:['image/jpeg'],png:['image/png'],webp:['image/webp']};
  function validationError(file,limits={}){
    const extension=String(file.name||'').split('.').pop().toLowerCase();
    if(!supported[extension])return 'Choose a PDF, XLSX, JPEG, PNG or WebP file.';
    if(!file.size)return 'This file is empty.';
    if(file.size>(limits.max_bytes||30*1024*1024))return 'This file exceeds the document size limit.';
    if(file.type&&!supported[extension].includes(file.type)&&file.type!=='application/octet-stream')return 'The file type does not match its extension.';
    return '';
  }
  function batches(queue,maximum=5){
    const result=[],size=Math.max(1,Math.min(5,Math.trunc(maximum)||5));
    for(const kind of ['hand_sketch','report']){
      const files=queue.filter(item=>item.kind===kind&&item.valid&&item.status==='ready');
      for(let i=0;i<files.length;i+=size)result.push(files.slice(i,i+size));
    }
    return result;
  }
  function confirmedReceipt(receipt,count){return !!receipt&&Array.isArray(receipt.documents)&&receipt.documents.length===count&&
    receipt.documents.every(item=>Number.isInteger(item.id))&&typeof receipt.state?.digest==='string'&&
    Array.isArray(receipt.state.photos)&&Array.isArray(receipt.state.documents);}
  function create(hooks){
    const root=hooks.root,el=id=>document.getElementById(id),node=(tag,text,className)=>{
      const result=document.createElement(tag);if(text!==undefined)result.textContent=text;if(className)result.className=className;return result;
    };
    let pending=[],serial=0;
    const state=()=>hooks.getState(),limits=()=>state()?.document_upload||{};
    const kinds={hand_sketch:'Hand sketch',report:'Report'};
    const supportedState=()=>Array.isArray(state()?.documents)&&!!root.dataset.documentUploadUrl&&!!root.dataset.documentRemoveUrl;
    const safeURL=value=>{if(typeof value!=='string'||!value)return '';try{const url=new URL(value,location.href);return url.origin===location.origin?url.href:'';}catch{return '';}};
    const canChange=()=>!!state()?.can_edit&&!hooks.blocked()&&supportedState();
    const fileSize=value=>value>=1024*1024?(value/(1024*1024)).toFixed(1)+' MB':Math.max(1,Math.round(value/1024))+' KB';
    function controls(){
      const ready=canChange();
      el('capture-documents-tab').disabled=hooks.busy();
      el('capture-document-upload-panel').hidden=!!state()&&!state().can_edit||!supportedState();
      el('capture-document-kind').disabled=el('capture-document-files').disabled=el('capture-document-camera').disabled=!ready;
      el('capture-document-upload').disabled=!ready||!pending.some(item=>item.status==='ready');
      el('capture-document-retry').hidden=!pending.some(item=>item.valid&&item.status==='failed');
      el('capture-document-retry').disabled=!ready;
      el('capture-document-pending').querySelectorAll('button').forEach(button=>button.disabled=!ready);
      el('capture-document-list').querySelectorAll('[data-remove-document]').forEach(button=>button.disabled=!ready);
      el('capture-documents-count').textContent=String(state()?.documents?.length||0);
    }
    function renderPending(){
      const host=el('capture-document-pending');host.replaceChildren();host.hidden=!pending.length;
      for(const item of pending){
        const row=node('div',undefined,'capture-document-pending-row');row.dataset.pendingDocument=item.key;
        const copy=node('div');copy.append(node('strong',item.file.name),node('small',kinds[item.kind]+' · '+fileSize(item.file.size)));
        copy.append(node('span',item.status==='failed'?item.error:item.status==='uploading'?'Uploading…':'Ready to upload',item.status==='failed'?'capture-error':''));
        const remove=node('button','Remove');remove.type='button';remove.dataset.removePendingDocument=item.key;
        remove.setAttribute('aria-label','Remove selected document '+item.file.name);
        remove.addEventListener('click',()=>{if(!canChange())return;pending=pending.filter(value=>value.key!==item.key);renderPending();if(!pending.length){el('capture-document-progress-area').hidden=true;el('capture-document-progress').value=0;el('capture-document-progress-label').textContent='';hooks.message('Selected document removed. Your saved documents are unchanged.');}hooks.changed();});
        row.append(copy,remove);host.append(row);
      }
      controls();
    }
    function render(){
      const host=el('capture-document-list');host.replaceChildren();
      el('capture-document-status').textContent=supportedState()?(state()?.can_edit?'Add supporting sketches and reports before submitting.':'Submitted supporting documents are read-only.'):'Supporting documents could not be loaded. Refresh the saved site.';
      const config=limits();el('capture-document-guidance').textContent=`PDF, XLSX, JPEG, PNG or WebP · up to ${Math.round((config.max_bytes||30*1024*1024)/(1024*1024))} MB per file · ${config.max_batch||5} files per batch. Word files are not supported.`;
      for(const source of state()?.documents||[]){
        const row=node('article',undefined,'capture-document-card');row.dataset.documentId=source.id;
        const preview=safeURL(source.preview_url),original=safeURL(source.original_url||source.download_url);
        if(source.is_image&&preview){const link=node('a');link.href=preview;link.target='_blank';link.rel='noopener';link.setAttribute('aria-label','Preview '+source.filename);const image=node('img');image.src=preview;image.alt=source.filename;image.loading='lazy';link.append(image);row.append(link);}
        const copy=node('div',undefined,'capture-document-copy');copy.append(node('strong',source.filename),node('small',(source.kind_label||kinds[source.kind]||'Supporting document')+' · '+fileSize(source.size||0)));
        const actions=node('div',undefined,'capture-photo-actions');
        if(source.can_preview&&preview){const link=node('a','Preview');link.href=preview;link.target='_blank';link.rel='noopener';actions.append(link);}
        if(original){const link=node('a','Download');link.href=original;link.target='_blank';link.rel='noopener';actions.append(link);}
        if(state().can_edit){const remove=node('button','Remove');remove.type='button';remove.dataset.removeDocument=source.id;remove.setAttribute('aria-label','Remove document '+source.filename);
          remove.addEventListener('click',async()=>{if(!canChange()||!confirm(`Remove “${source.filename}” from this submission? The original and earlier submitted revisions will be retained.`))return;
            hooks.setBusy(true);hooks.uncheck();try{const result=await hooks.request(root.dataset.documentRemoveUrl,{document_id:source.id,expected_digest:state().digest});hooks.acceptState(result);hooks.message('Document removed from this submission. Earlier revisions are preserved.');}
            catch(error){try{await hooks.load();}catch{}hooks.message('Removal was not confirmed. '+error.message,true);}finally{hooks.setBusy(false);}});actions.append(remove);}
        copy.append(actions);row.append(copy);host.append(row);
      }
      if(!host.children.length)host.append(node('p','No sketches or reports have been uploaded.','capture-empty'));
      renderPending();controls();
    }
    function add(files,kind=el('capture-document-kind').value){
      if(!canChange())return;hooks.uncheck();
      for(const file of files){const error=validationError(file,limits());pending.push({key:String(++serial),file,kind,valid:!error,status:error?'failed':'ready',error});}
      renderPending();hooks.changed();hooks.message('Selected documents are ready. Upload them to save them with this site.');
    }
    function send(batch,token,onProgress){return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest(),data=new FormData();data.append('kind',batch[0].kind);data.append('expected_digest',state().digest);data.append('processing_upload_token',token);
      batch.forEach(item=>data.append('files',item.file));xhr.open('POST',root.dataset.documentUploadUrl);xhr.withCredentials=true;xhr.setRequestHeader('X-CSRFToken',hooks.csrf);xhr.setRequestHeader('Accept','application/json');
      xhr.upload.addEventListener('progress',event=>{if(event.lengthComputable)onProgress(event.loaded/event.total);});
      xhr.addEventListener('load',()=>{let body;try{body=JSON.parse(xhr.responseText);}catch{reject(new Error('The upload response is unreadable. Retry the files; saved duplicates will be reused.'));return;}
        if(xhr.status>=200&&xhr.status<300)resolve(body);else{const error=new Error(body.error||body.message||`Upload failed (${xhr.status}).`);error.status=xhr.status;reject(error);}});
      xhr.addEventListener('error',()=>reject(new Error('Connection interrupted. Retry the failed files; saved originals are preserved.')));
      xhr.addEventListener('abort',()=>reject(new Error('Upload interrupted. Retry the selected documents.')));xhr.send(data);
    });}
    async function upload(retry=false){
      if(!canChange())return;if(retry)pending.filter(item=>item.valid&&item.status==='failed').forEach(item=>{item.status='ready';item.error='';});
      const selected=pending.filter(item=>item.status==='ready'&&item.valid);if(!selected.length)return;
      hooks.setBusy(true);hooks.uncheck();let token=null,heartbeat=null,completed=0,failed=false,bytesDone=0;const totalBytes=selected.reduce((sum,item)=>sum+item.file.size,0)||1;
      el('capture-document-progress-area').hidden=false;el('capture-document-progress').value=0;
      try{
        token=(await hooks.request(root.dataset.sessionUrl,{action:'start'})).token;
        if(!token)throw new Error('An upload session could not be started. Refresh and retry.');hooks.setSession(token);
        heartbeat=setInterval(()=>hooks.request(root.dataset.sessionUrl,{action:'heartbeat',token}).catch(error=>hooks.message(error.message,true)),30000);
        for(const batch of batches(selected,limits().max_batch)){
          batch.forEach(item=>item.status='uploading');renderPending();const bytes=batch.reduce((sum,item)=>sum+item.file.size,0);
          try{const result=await send(batch,token,fraction=>{el('capture-document-progress').value=Math.min(99,100*(bytesDone+bytes*fraction)/totalBytes);el('capture-document-progress-label').textContent=`${completed} / ${selected.length} documents saved · ${Math.round(el('capture-document-progress').value)}% uploaded`;});
            if(!confirmedReceipt(result,batch.length))throw new Error('The server did not confirm every document. Retry these files; saved duplicates will be reused.');
            hooks.acceptState(result.state);batch.forEach(item=>item.status='uploaded');completed+=batch.length;
          }catch(error){failed=true;batch.forEach(item=>{item.status='failed';item.error=error.message;});hooks.message(error.message,true);if(!error.status||[401,403,409].includes(error.status))break;}
          bytesDone+=bytes;renderPending();
        }
      }catch(error){failed=true;selected.filter(item=>item.status!=='uploaded').forEach(item=>{item.status='failed';item.error=error.message;});hooks.message(error.message,true);}
      finally{
        clearInterval(heartbeat);
        if(token){try{await hooks.request(root.dataset.sessionUrl,{action:'finish',token});}catch(error){failed=true;try{await hooks.request(root.dataset.sessionUrl,{action:'interrupt',token});}catch{}hooks.message(error.message,true);}}
        hooks.setSession(null);
        selected.filter(item=>item.status==='uploading').forEach(item=>{item.status='failed';item.error='Upload interrupted. Retry this document.';});
        try{await hooks.load();}catch(error){failed=true;hooks.message(error.message,true);}
        pending=pending.filter(item=>item.status!=='uploaded');hooks.setBusy(false);renderPending();hooks.changed();
        el('capture-document-progress').value=100*completed/selected.length;el('capture-document-progress-label').textContent=`${completed} / ${selected.length} documents saved${failed?' · retry remaining files':''}`;
        if(!failed)hooks.message(`${completed} supporting document${completed===1?'':'s'} saved with this site.`);
      }
    }
    el('capture-document-files').addEventListener('change',event=>{add(event.target.files);event.target.value='';});
    el('capture-document-camera').addEventListener('change',event=>{add(event.target.files,'hand_sketch');event.target.value='';});
    el('capture-document-form').addEventListener('submit',event=>{event.preventDefault();upload();});
    el('capture-document-retry').addEventListener('click',()=>upload(true));
    return{render,controls,incomplete:()=>pending.some(item=>item.status!=='uploaded')};
  }
  return{validationError,batches,confirmedReceipt,create};
});
