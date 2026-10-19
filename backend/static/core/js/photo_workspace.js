(() => {
  'use strict';
  const app = document.getElementById('photo-app');
  if (!app) return;
  const el = id => document.getElementById(id);
  const readOnly = app.dataset.readonly === 'true';
  let photoLimit = Number(app.dataset.photoLimit) || 500;
  let cameraFiles = null, queueBusy=false;
  let visibleLimit=36, activeField=null;
  function visiblePhotos(){if(!activeField)return state.photos;const ids=new Set((state.mappings||[]).filter(m=>m.field_id===activeField&&["proposed","confirmed","manual"].includes(m.status)).map(m=>m.photo_id));return state.photos.filter(p=>ids.has(p.id));}
  const pendingAnalysis=new Set();
  const selection = new Set();
  let state = {photos: [], jobs: [], drafts: []}, current = null, refreshing = false;
  const token = app.querySelector('[name=csrfmiddlewaretoken]').value;
  const base = window.location.pathname.replace(/\/?$/, '/');
  const uiText = text => String(text ?? '').replace(/metadata/gi,'AI Analysis');
  const message = text => { el('photo-message').textContent = uiText(text); };
  function node(tag, text, cls) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = uiText(text);
    if (cls) item.className = cls;
    return item;
  }
  async function request(path, payload) {
    const options = {credentials: 'same-origin', headers: {'Accept': 'application/json'}};
    if (payload !== undefined) {
      if (readOnly) throw new Error('This evidence workspace is read-only.');
      options.method = 'POST'; options.headers['X-CSRFToken'] = token;
      if (payload instanceof FormData) options.body = payload;
      else { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(payload); }
    }
    const response = await fetch(base + path, options);
    const data = await response.json().catch(() => ({error: 'Session expired or unexpected server response. Reload and sign in again.'}));
    if (!response.ok) { const error=new Error(uiText(data.error || `Request failed (${response.status}).`));error.status=response.status;throw error; }
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error(data.error);
    return data;
  }
  function counts() { el('photo-selection').textContent = `${selection.size} selected · ${state.photos.length}/${photoLimit} uploaded`; }
  function renderVisualMetadata(photo){
    const panel=el('photo-visual-observations'),body=el('photo-visual-content');if(!panel||!body)return;
    body.replaceChildren();const metadata=photo?.visual_metadata;
    panel.hidden=photo?.metadata_ready!==true||!metadata||typeof metadata!=='object'||Array.isArray(metadata);if(panel.hidden)return;
    body.append(node('p',typeof metadata.caption==='string'&&metadata.caption?metadata.caption:'No caption recorded.','photo-visual-caption'));
    for(const[label,key]of[['Observed objects','objects'],['Visible text','visible_text'],['Suspected issues','issues'],['Uncertainties','uncertainties']]){
      const section=node('section'),heading=node('h4',label);section.append(heading);const values=Array.isArray(metadata[key])?metadata[key].filter(value=>typeof value==='string'&&value.trim()):[];
      if(values.length){const list=node('ul');values.forEach(value=>list.append(node('li',value)));section.append(list);}else section.append(node('p',key==='issues'?'No suspected issues recorded; this does not establish a pass.':'Not recorded or not clearly visible.','photo-muted'));
      body.append(section);
    }
  }
  function showPhoto(photo) {
    current = photo.id;
    if(el('photo-position'))el('photo-position').textContent=(visiblePhotos().findIndex(p=>p.id===current)+1)+' / '+visiblePhotos().length;
    renderVisualMetadata(photo);
    if(el('photo-metadata-status'))el('photo-metadata-status').textContent=photo.metadata_ready===true?'AI Analysis is ready. Review the suggested checklist links.':photo.metadata_ready===false?'AI Analysis is pending for this photo.':'';
    document.dispatchEvent(new CustomEvent('photo-selected', {detail:photo}));
    el('photo-selected').src = photo.preview_url;
    el('photo-selected').alt = photo.filename;
    el('photo-selected').hidden = false; el('photo-empty').hidden = true;
    el('photo-original').href = photo.original_url; el('photo-original').hidden = false;
    const m = photo.metadata || {};
    el('photo-caption').textContent = `${photo.filename} · ${m.width || '?'} × ${m.height || '?'} · Captured: ${m.captured_at || 'not recorded'} · GPS: ${m.gps ? `${m.gps.latitude}, ${m.gps.longitude}` : 'not recorded'}${photo.advisories?.length ? ' · ' + photo.advisories.join(' ') : ''}`;
    if(photo.uploaded_by)el('photo-caption').textContent += ' · Uploaded by: '+photo.uploaded_by;
    if(photo.uploaded_at)el('photo-caption').textContent += ' · Uploaded: '+photo.uploaded_at;
    document.querySelectorAll('.photo-thumb button').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.photo) === current)));
  }
  function render() {
    const thumbs = el('photo-thumbs'),scroll=thumbs.scrollLeft,scrollTop=thumbs.scrollTop; thumbs.replaceChildren();
    const filtered=visiblePhotos();
    for (const p of filtered.slice(0,visibleLimit)) {
      const card = node('div', undefined, 'photo-thumb'), button = node('button');
      button.type = 'button'; button.dataset.photo = p.id; button.setAttribute('aria-label', `View ${p.filename}`);
      button.setAttribute('aria-pressed', String(p.id === current));
      const image = node('img'); image.src = p.preview_url; image.alt = ''; image.loading = 'lazy'; button.append(image);
      button.onclick = () => showPhoto(p);
      const label = node('label'), check = node('input'); check.type = 'checkbox'; check.checked = selection.has(p.id);
      check.onchange = () => { check.checked ? selection.add(p.id) : selection.delete(p.id); counts(); };
      if (!readOnly) label.append(check); label.append(document.createTextNode((p.group ? p.group + ' · ' : '') + p.filename)); card.append(button, label); thumbs.append(card);
    }
    thumbs.scrollLeft=scroll;thumbs.scrollTop=scrollTop;
    if(filtered.length&&!filtered.some(p=>p.id===current))showPhoto(filtered[0]);
    if(!filtered.length){current=null;el('photo-selected').hidden=true;el('photo-empty').hidden=false;el('photo-empty').textContent=activeField?'No photo evidence is linked to this checklist item.':'No source photos are recorded for this checklist.';el('photo-original').hidden=true;el('photo-caption').textContent='';}
    if(el('photo-more'))el('photo-more').hidden=visibleLimit>=filtered.length;
    if(el('photo-thumbnail-count'))el('photo-thumbnail-count').textContent='Showing '+Math.min(visibleLimit,filtered.length)+' of '+filtered.length+' photos';
    if(el('photo-position'))el('photo-position').textContent=current?(filtered.findIndex(p=>p.id===current)+1)+' / '+filtered.length:'No photo selected';
    counts();
    const selected=state.photos.find(p=>p.id===current);renderVisualMetadata(selected);if(el('photo-metadata-status'))el('photo-metadata-status').textContent=selected?.metadata_ready===true?'AI Analysis is ready. Review the suggested checklist links.':selected?.metadata_ready===false?'AI Analysis is pending for this photo.':'';
    const active=state.jobs.find(j=>j.status==='running')||state.jobs.find(j=>j.status==='queued');if(el('photo-processing-stages'))el('photo-processing-stages').dataset.stage=active?.progress?.stage||(state.jobs[0]?.status==='failed'?'failed':state.analysis?.review_ready&&state.jobs[0]?.status==='completed'?'completed':'queued');
    const jobs = el('photo-jobs'); jobs.replaceChildren();
    if (!state.jobs.length) jobs.append(node('p', 'No processing jobs yet.'));
    const analyzedIds=new Set(state.analysis?.analyzed_photo_ids||[]);
    for (const j of state.jobs) {
      const superseded=j.status==='failed'&&Array.isArray(j.photo_ids)&&j.photo_ids.length>0&&j.photo_ids.every(id=>analyzedIds.has(id));
      const row=node('div',undefined,'photo-job');row.dataset.jobId=j.id;
      if(superseded){
        row.append(node('strong',`Job ${j.id} · Earlier failed attempt`),node('p','Earlier failed attempt · photos analyzed by a later job','photo-muted'));
        const history=node('details'),summary=node('summary','View original attempt');history.append(summary,node('p',`${j.completed}/${j.total} photos processed in this earlier attempt.`));if(j.error)history.append(node('p',j.error));row.append(history);jobs.append(row);continue;
      }
      row.append(node('strong',`Job ${j.id} · ${j.status} · ${j.completed}/${j.total}`));
      const stageLabels={extracting_metadata:'AI Analysis — examining photo',matching_checklist:'AI Analysis — matching checklist points',completed:'Processing complete — review drafts',failed:'Processing failed'};const stage=j.status==='queued'?'Queued — waiting for the local worker':stageLabels[j.progress?.stage]||j.status;row.append(node('p',stage,'photo-job-stage'));if(j.progress?.photo_id){const photo=state.photos.find(p=>p.id===j.progress.photo_id);row.append(node('small',(j.status==='completed'?'Last processed photo: ':'Current photo: ')+(photo?.filename||j.progress.photo_id)));}if(j.progress?.cache_reused)row.append(node('p','Saved AI Analysis reused for this photo.','photo-job-reuse'));
      const progress=node('progress');progress.max=j.total||1;progress.value=j.completed;progress.setAttribute('aria-label',`Job ${j.id} progress`);row.append(progress);
      if(j.error)row.append(node('p',j.error));
      if(!readOnly&&j.status==='failed'){const retry=node('button','Retry failed job');retry.type='button';retry.onclick=()=>act(retry,`jobs/${j.id}/retry/`,{});row.append(retry);}
      jobs.append(row);
    }
    const drafts = el('photo-drafts'); drafts.replaceChildren();
    if (!state.drafts.length) drafts.append(node('p', 'No proposals yet. Finished analysis may also find insufficient evidence.'));
    for (const d of state.drafts) {
      const card = node('article', undefined, 'photo-draft');
      card.append(node('h3', d.label || d.field_id), node('p', `Field ${d.field_id} · ${d.status} · Uncertainty: ${d.uncertainty}`));
      card.append(node('pre', d.value === null ? 'Insufficient evidence — no answer proposed.' : JSON.stringify(d.value, null, 2)), node('p', d.reason));
      if (d.missing_information) card.append(node('p', `Information needed: ${d.missing_information}`));
      for (const anomaly of d.anomalies || []) card.append(node('p', `Suspected anomaly: ${anomaly.description}${anomaly.bbox ? ' · Normalized bounds: ' + anomaly.bbox.join(', ') : ''}`));
      const photo = state.photos.find(p => p.id === d.photo_id);
      if (photo) { const source = node('button', `Inspect source: ${photo.filename}`); source.type = 'button'; source.onclick = () => { showPhoto(photo); el('photo-viewer').scrollIntoView({behavior: 'smooth', block: 'center'}); }; card.append(source); }
      if (!readOnly && d.status === 'pending' && d.value !== null) { const accept = node('button', 'Accept proposed answer'); accept.type = 'button'; accept.onclick = () => { if (window.confirm(`Apply this proposed answer to ${d.label || d.field_id}? This changes the saved answer and does not approve the section.`)) act(accept, `drafts/${d.id}/accept/`, {}); }; card.append(accept); }
      drafts.append(card);
    }
    document.dispatchEvent(new CustomEvent('photo-state', {detail:state}));
  }
  async function queueUploadedGroup(){
    if(readOnly||queueBusy||!pendingAnalysis.size)return;
    queueBusy=true;const ids=Array.from(pendingAnalysis);
    try{await request('enqueue/',{photo_ids:ids,queue_when_busy:true});ids.forEach(id=>pendingAnalysis.delete(id));message('Photo group uploaded and durably queued. Groups wait their turn for the local worker; review proposed links when analysis finishes.');await refresh();}
    catch(error){ids.forEach(id=>pendingAnalysis.delete(id));message('Originals uploaded, but analysis did not start: '+error.message+' Use Analyze unprocessed photos to retry.');}
    finally{queueBusy=false;}
  }
  async function refresh() {
    if (refreshing || document.hidden) return;
    refreshing = true;
    try { state = await request('state/');if(Number.isInteger(state.max_photos)&&state.max_photos>0)photoLimit=state.max_photos;render(); } catch (e) { message(e.message); }
    finally { refreshing = false; }
  }
  async function act(button, path, payload) {
    button.disabled = true;
    try { await request(path, payload); message('Saved.'); await refresh(); }
    catch (e) { message(e.message); } finally { button.disabled = false; }
  }
  el('photo-upload').onsubmit = async event => {
    event.preventDefault(); const files = cameraFiles || Array.from(el('photo-files').files);
    const group = el('photo-group')?.value || '';
    if (!group) { message('Choose Civil, Electrical or Tower before uploading.'); return; }
    if (!files.length || files.length > photoLimit || files.some(f => f.size > 5 * 1024 * 1024 || (!['image/jpeg','image/png','image/webp'].includes(f.type) && !/\.(jpe?g|png|webp)$/i.test(f.name)))) { message(`Choose at most ${photoLimit} JPEG, PNG or WebP files, each 5 MB or smaller.`); return; }
    const button = el('upload-button'), progress = el('upload-progress'); button.disabled = true; progress.hidden = false; progress.value = 0;
    let count = 0, duplicates = 0, uploadError='';
    try {
      for (let start = 0; start < files.length; start += 20) {
        const batch = new FormData(); batch.append('group', group); files.slice(start, start + 20).forEach(f => batch.append('files', f));
        const result = await request('upload/', batch); result.photos.filter(p=>!p.duplicate).forEach(p=>pendingAnalysis.add(p.id)); count += result.photos.length; duplicates += result.photos.filter(p => p.duplicate).length;
        progress.value = count / files.length * 100; message(`${count}/${files.length} processed · ${duplicates} exact duplicates.`);
      }
      el('photo-files').value = ''; if(el('photo-camera'))el('photo-camera').value=''; cameraFiles=null; if(el('photo-picked'))el('photo-picked').textContent='Photo group uploaded. Choose more photos when ready.';
    } catch (e) { uploadError=`${count} files processed before interruption. Existing uploads are preserved. ${e.message}`;message(uploadError); }
    finally { await queueUploadedGroup();button.disabled=false;await refresh();if(uploadError)message(uploadError+' Successfully uploaded originals remain available for analysis.'); }
  };
  if(el('photo-camera'))el('photo-camera').onchange=()=>{cameraFiles=Array.from(el('photo-camera').files);el('photo-picked').textContent=cameraFiles.length+' camera photo selected';};
  el('photo-files').onchange=()=>{cameraFiles=null;if(el('photo-picked'))el('photo-picked').textContent=el('photo-files').files.length+' gallery photos selected';};
  el('photo-enqueue').onclick = async () => {
    if (!selection.size) { message('Select at least one photo for analysis.'); return; }
    const button = el('photo-enqueue'); button.disabled = true;
    try {
      const ids = Array.from(selection);
      await request('enqueue/', {photo_ids: ids}); ids.forEach(id => selection.delete(id));
      message('Queued for the independent local worker. Drafts require engineer acceptance.');
    } catch (e) { message(e.message); } finally { button.disabled = false; await refresh(); }
  };
  el('photo-select-all').onclick = () => { const clear = selection.size === state.photos.length; selection.clear(); if (!clear) state.photos.forEach(p => selection.add(p.id)); render(); };
  el('photo-refresh').onclick = refresh;
  el('photo-fullscreen').onclick = async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else await el('photo-viewer').requestFullscreen(); } catch { message('Fullscreen is unavailable in this browser. Open the original photo instead.'); } };
  el('catalog-mode').onclick = () => { const ungrouped = el('photo-sites').classList.toggle('photo-ungrouped'); if (ungrouped) el('photo-sites').querySelectorAll('details').forEach(item => { item.open = true; }); el('catalog-mode').textContent = ungrouped ? 'Group projects' : 'Ungroup projects'; };
  // Appearance is controlled centrally by the bottom-left system menu.
  if(el('photo-more'))el('photo-more').onclick=()=>{visibleLimit+=36;render();};
  window.photoWorkspace={request,refresh,getState:()=>state,getCurrent:()=>current,message,readOnly,selectPhoto:id=>{const photo=state.photos.find(p=>p.id===id);if(photo){const index=visiblePhotos().findIndex(p=>p.id===id);if(index>=visibleLimit){visibleLimit=Math.ceil((index+1)/36)*36;render();}showPhoto(photo);}},getVisiblePhotos:visiblePhotos,filterField:id=>{activeField=id||null;visibleLimit=36;render();}};
  refresh(); setInterval(refresh, 6000); document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
