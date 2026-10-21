(() => {
  'use strict';
  const root = document.getElementById('survey-processing');
  if (!root) return;
  const byId = id => document.getElementById(id);
  const canReview = root.dataset.canReview === 'true';
  const isClient = root.dataset.isClient === 'true';
  const selected = new Set();
  const activeStatuses = new Set(['queued', 'analysing_evidence', 'preparing_checklist', 'preparing_drawings']);
  const stageCodes = ['queued', 'analysing_evidence', 'preparing_checklist', 'preparing_drawings', 'ready_for_review'];
  let state = {}, selectedRevisionId = '', page = 0, busy = false, polling = false, stateStale = false, renderedSignature = '', correctionItem = null, correctionMode = 'checklist';
  let geometryRecords = [], geometryDirty = false, geometryEditIndex = -1, geometryRevisionId = '';
  let pollTimer, refreshPending = null;
  const pageSize = 30;
  const display = value => {
    if (value === undefined || value === null || value === '') return 'Not recorded';
    return typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
  };
  const node = (tag, text, className) => {
    const result = document.createElement(tag);
    if (text !== undefined && text !== null) result.textContent = String(text);
    if (className) result.className = className;
    if (tag === 'button' && text) result.title = String(text);
    return result;
  };
  const array = value => Array.isArray(value) ? value : [];
  const statusKey = value => String(value || '').toLowerCase().replaceAll(' ', '_').replaceAll('—', '_');
  const normalStatus = value => ({confirmed_from_evidence: 'confirmed', 'n/a': 'not_applicable'}[statusKey(value)] || statusKey(value));
  const verificationLabel = value => ({confirmed: 'Confirmed from evidence', needs_review: 'Needs review', reported: 'Reported', missing: 'Missing', not_applicable: 'Not applicable'}[normalStatus(value)] || display(value));
  const sourceUrl = value => {
    if (!value) return '';
    try {
      const url = new URL(value, window.location.origin);
      return ['http:', 'https:'].includes(url.protocol) && url.origin === window.location.origin ? url.href : '';
    } catch (_) { return ''; }
  };
  const csrf = () => root.querySelector('[name=csrfmiddlewaretoken]')?.value || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  const currentRevision = () => array(state.revisions).find(revision => String(revision.id) === String(selectedRevisionId)) || null;
  const ready = revision => revision && !activeStatuses.has(statusKey(revision.status)) && statusKey(revision.status) !== 'failed' && array(revision.checklist_items).length > 0;
  const editable = revision => !stateStale && canReview && ready(revision) && revision.current !== false && !revision.released && statusKey(revision.status) !== 'released';
  const feedback = (message, error = false) => {
    const target = byId('sp-feedback');
    target.textContent = message;
    target.classList.toggle('sp-error', error);
    if (byId('sp-correction-dialog')?.open) {
      byId('sp-correction-feedback').textContent = error ? message : '';
      byId('sp-correction-feedback').hidden = !error;
    }
  };
  function errorMessage(payload) {
    if (!payload) return 'The request could not be completed.';
    if (typeof payload === 'string') return payload;
    return display(payload.error || payload.message || payload.detail || payload.errors || 'The request could not be completed.');
  }
  async function request(form) {
    const response = await fetch(root.dataset.actionUrl, {
      method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf(), 'Accept': 'application/json'}, body: form
    });
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) throw new Error(`The server did not confirm this action (${response.status}). Refresh the page and sign in again if your session has expired.`);
    const payload = await response.json();
    if (!response.ok) { const error = new Error(errorMessage(payload)); error.status = response.status; throw error; }
    return payload;
  }
  async function action(name, fields = {}, success = 'Saved.') {
    if (busy) return null;
    if (stateStale) { feedback('Refresh the saved processing state before making another change.', true); return null; }
    busy = true;
    root.setAttribute('aria-busy', 'true');
    updateControls();
    const form = new FormData();
    form.set('action', name);
    for (const [key, value] of Object.entries(fields)) form.set(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
    try {
      const payload = await request(form);
      const refreshed = await refresh(true);
      feedback(refreshed ? payload.message || success : 'The server saved this action, but its updated state could not be loaded. Use Refresh before continuing. Do not repeat the action.', !refreshed);
      return payload;
    } catch (error) {
      if (!error.status) stateStale = true;
      feedback(error.status ? error.message : `${error.message} The save outcome is unconfirmed. Use Refresh to check the saved state before retrying.`, true);
      return null;
    } finally {
      busy = false;
      root.removeAttribute('aria-busy');
      updateControls();
    }
  }
  function confidence(value) {
    if (value === undefined || value === null || value === '') return 'Not assessed';
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return String(value).charAt(0).toUpperCase() + String(value).slice(1);
    return `${Math.round(numeric <= 1 ? numeric * 100 : numeric)}%`;
  }
  function sourceLinks(sources) {
    const wrapper = node('div', null, 'sp-source-list');
    const available = array(sources);
    if (!available.length) return node('small', 'No supporting source');
    for (const source of available.slice(0, 8)) {
      const label = source.reference || source.label || source.filename || `Source ${source.source_id || source.id || ''}`;
      const url = sourceUrl(source.url || source.source_url);
      const thumb = sourceUrl(source.thumbnail_url || source.preview_url);
      const link = url ? node('a') : node('span');
      if (url) { link.href = url; link.target = '_blank'; link.rel = 'noopener'; }
      if (thumb) {
        const image = node('img'); image.src = thumb; image.alt = `Evidence: ${label}`; image.loading = 'lazy';
        link.append(image);
      }
      link.append(node('span', label));
      wrapper.append(link);
    }
    if (available.length > 8) wrapper.append(node('small', `+${available.length - 8} further references in source records`));
    return wrapper;
  }
  function renderStatus() {
    const active = state.active;
    const label = isClient && array(active?.drawings).some(drawing => drawing.released) ? 'Released outputs available' : active?.label || active?.status || 'Not submitted';
    byId('sp-status').textContent = label;
    const total = Number(active?.total || 0), completed = Number(active?.completed || 0);
    const status = statusKey(active?.status), evidenceProgress = total ? Math.max(0, Math.min(1, completed / total)) : 0;
    const stageProgress = {queued: 0, analysing_evidence: 5 + evidenceProgress * 75, preparing_checklist: 85, preparing_drawings: 95, ready_for_review: 100, released: 100, failed: evidenceProgress * 80};
    const percentage = Number(active?.progress ?? stageProgress[status] ?? 0);
    byId('sp-progress').value = Number.isFinite(percentage) ? Math.max(0, Math.min(100, percentage)) : 0;
    byId('sp-counts').textContent = active ? `Revision ${active.revision} · ${completed} of ${total} evidence units processed${state.upload_state?.inflight ? ' · Uploads are still in progress' : ''}` : 'Complete saved survey inputs and finish uploads before submitting.';
    const error = byId('sp-error');
    error.hidden = !active?.error;
    error.textContent = active?.error || '';
    const stageIndex = stageCodes.indexOf(status);
    byId('sp-stages').querySelectorAll('li').forEach((item, index) => {
      item.classList.toggle('is-current', index === stageIndex);
      item.classList.toggle('is-complete', stageIndex > index || status === 'released');
      if (index === stageIndex) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
    });
    const retry = byId('sp-retry');
    retry.hidden = !(root.dataset.canSubmit === 'true' && status === 'failed');
    retry.disabled = busy || stateStale;
  }
  function renderRevisions() {
    const revisions = array(state.revisions);
    const picker = byId('sp-revision');
    if (!revisions.some(revision => String(revision.id) === String(selectedRevisionId))) {
      selectedRevisionId = String(revisions.find(revision => revision.current)?.id || revisions[0]?.id || '');
      selected.clear(); page = 0; geometryDirty = false;
    }
    const optionSignature = JSON.stringify(revisions.map(revision => [revision.id, revision.revision, revision.label, revision.current]));
    if (picker.dataset.signature !== optionSignature) {
      picker.replaceChildren();
      if (!revisions.length) picker.append(node('option', 'No submitted revisions'));
      for (const revision of revisions) {
        const option = node('option', `Revision ${revision.revision} · ${revision.label || revision.status}${revision.current ? ' · current' : ''}`);
        option.value = String(revision.id); picker.append(option);
      }
      picker.dataset.signature = optionSignature;
    }
    picker.value = selectedRevisionId;
    const revision = currentRevision();
    byId('sp-revision-note').textContent = revision ? `Revision ${revision.revision}${revision.current ? ' · Current survey snapshot' : ' · Previous immutable survey snapshot'}${revision.created_at ? ` · ${revision.created_at}` : ''}` : 'Submitting saves an immutable copy of the survey and its evidence.';
  }
  function itemLabel(item) { return item.label || item.field_label || item.field_id || item.id || 'Checklist item'; }
  function itemId(item) { return String(item.id || item.field_id || ''); }
  function renderChecklist() {
    const revision = currentRevision(), items = array(revision?.checklist_items), filter = byId('sp-filter').value;
    const query = byId('sp-search').value.toLowerCase().trim();
    const filtered = items.filter(item => {
      const status = normalStatus(item.status);
      if (filter === 'uncertain' && !['needs_review', 'missing', 'conflicting'].includes(status)) return false;
      if (!['all', 'uncertain'].includes(filter) && status !== filter) return false;
      return !query || `${itemLabel(item)} ${item.section || ''} ${display(item.value ?? item.proposed_answer)}`.toLowerCase().includes(query);
    });
    page = Math.max(0, Math.min(page, Math.ceil(filtered.length / pageSize) - 1));
    const shown = filtered.slice(page * pageSize, (page + 1) * pageSize);
    const tbody = byId('sp-checklist-body'); tbody.replaceChildren();
    if (!shown.length) {
      const tr = node('tr'), td = node('td', items.length ? 'No checklist items match these filters.' : 'No generated checklist is available for this revision yet. Processing progress appears above.');
      td.colSpan = canReview ? 6 : 5; tr.append(td); tbody.append(tr);
    }
    for (const item of shown) {
      const tr = node('tr');
      if (canReview) {
        const cell = node('td'), check = node('input'); check.type = 'checkbox'; check.value = itemId(item); check.dataset.itemSelect = itemId(item);
        check.setAttribute('aria-label', `Select ${itemLabel(item)}`); check.checked = selected.has(itemId(item)); check.disabled = !editable(revision) || item.accepted || item.locked || busy;
        cell.append(check); tr.append(cell);
      }
      const label = node('td'); label.append(node('strong', itemLabel(item)), node('small', item.section || 'Checklist'));
      if (item.proposed_addition) label.append(node('small', 'Proposed addition — not part of published template'));
      tr.append(label);
      const proposedValue = item.accepted ? item.value : item.proposed_answer ?? item.value;
      const answerText = display(proposedValue) + (item.unit && normalStatus(item.status) !== 'not_applicable' && proposedValue !== null && proposedValue !== undefined && proposedValue !== '' ? ` ${item.unit}` : '');
      const answer = node('td'); answer.append(node('span', answerText), document.createElement('br'));
      const badge = node('span', item.status || 'Needs review', 'sp-status-pill'); badge.dataset.state = normalStatus(item.status); answer.append(badge);
      if (item.reason) answer.append(node('small', item.reason));
      tr.append(answer);
      const evidence = node('td'); evidence.append(sourceLinks(item.sources)); tr.append(evidence);
      tr.append(node('td', confidence(item.confidence)));
      const controls = node('td');
      if (item.locked) controls.append(node('strong', 'Approved section - preserved'));
      else if (item.accepted) controls.append(node('strong', 'Reviewed'));
      else controls.append(node('small', 'Unreviewed proposal'));
      if (editable(revision) && !item.locked) {
        const actions = node('div', null, 'sp-item-actions');
        if (!item.accepted && !item.locked) { const accept = node('button', normalStatus(item.status) === 'missing' ? 'Acknowledge missing' : 'Accept'); accept.type = 'button'; accept.dataset.acceptItem = itemId(item); accept.disabled = busy; actions.append(accept); }
        const correct = node('button', 'Correct'); correct.type = 'button'; correct.dataset.correctItem = itemId(item); correct.disabled = busy; actions.append(correct); controls.append(actions);
      }
      tr.append(controls); tbody.append(tr);
    }
    byId('sp-checklist-count').textContent = items.length ? `(${items.length})` : '';
    byId('sp-items-page').textContent = filtered.length ? `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, filtered.length)} of ${filtered.length}` : '0 items';
    byId('sp-items-prev').disabled = page <= 0;
    byId('sp-items-next').disabled = (page + 1) * pageSize >= filtered.length;
    syncSelection();
  }
  function syncSelection() {
    const accept = byId('sp-accept-selected');
    if (accept) { accept.textContent = `Accept selected (${selected.size})`; accept.disabled = !selected.size || busy || !editable(currentRevision()); }
    const checks = Array.from(root.querySelectorAll('[data-item-select]:not(:disabled)'));
    const all = byId('sp-select-visible');
    if (all) {
      all.disabled = !checks.length || busy;
      all.checked = checks.length > 0 && checks.every(check => check.checked);
      all.indeterminate = checks.some(check => check.checked) && !all.checked;
    }
  }
  function renderRecords(revision) {
    const wrapper = byId('sp-records'); wrapper.replaceChildren();
    const findings = array(revision?.findings);
    if (!findings.length) { wrapper.append(node('p', 'No extracted records are available yet.', 'sp-empty')); return; }
    for (const finding of findings) {
      const card = node('article', null, 'sp-record');
      const heading = node('div', null, 'sp-record-heading');
      heading.append(node('h3', finding.label || finding.field_hint || finding.kind || finding.type || finding.equipment_type || 'Evidence observation'));
      const findingKey = finding.finding_key || finding.key;
      if (editable(revision) && findingKey) {
        const correct = node('button', 'Correct extracted record'); correct.type = 'button'; correct.dataset.correctRecord = String(findingKey); correct.disabled = busy; heading.append(correct);
      }
      card.append(heading);
      card.append(node('p', `Current value: ${display(finding.value ?? finding.description ?? finding.text ?? finding.record ?? finding)}${finding.unit ? ` ${finding.unit}` : ''}`));
      if (Object.prototype.hasOwnProperty.call(finding, 'original_value')) {
        card.append(node('p', `Original extraction: ${display(finding.original_value)}${finding.original_unit ? ` ${finding.original_unit}` : ''}`, 'sp-muted'));
      }
      const details = node('dl');
      for (const [label, value] of [['Verification', verificationLabel(finding.verification_status || finding.status || 'Needs review')], ['Confidence', confidence(finding.confidence)], ['Source', finding.reference || finding.source_id || 'Not recorded']]) {
        details.append(node('dt', label), node('dd', value));
      }
      card.append(details, sourceLinks(finding.sources || (finding.source ? [finding.source] : [])));
      wrapper.append(card);
    }
  }
  function renderGaps(revision) {
    const wrapper = byId('sp-gaps'); wrapper.replaceChildren();
    let count = 0;
    for (const [label, list] of [['Conflict', revision?.conflicts], ['Missing', revision?.missing]]) {
      for (const gap of array(list)) {
        const card = node('article', null, 'sp-gap');
        card.append(node('h3', `${label}: ${typeof gap === 'object' ? gap.label || gap.field || gap.kind || 'Evidence' : gap}`));
        if (typeof gap === 'object') { card.append(node('p', gap.message || gap.reason || gap.description || display(gap)), sourceLinks(gap.sources)); }
        wrapper.append(card); count++;
      }
    }
    byId('sp-gap-count').textContent = count ? `(${count})` : '';
    if (!count) wrapper.append(node('p', revision ? 'No missing or conflicting information has been recorded in this revision. This does not certify completeness or engineering compliance.' : 'Submit a survey to identify missing and conflicting information.', 'sp-empty'));
  }
  function renderDrawings(revision) {
    const wrapper = byId('sp-drawings'); wrapper.replaceChildren();
    const drawings = array(revision?.drawings);
    byId('sp-drawing-count').textContent = drawings.length ? `(${drawings.length})` : '';
    if (!drawings.length) { wrapper.append(node('p', 'No drawings have been prepared for this revision yet.', 'sp-empty')); return; }
    for (const drawing of drawings) {
      const card = node('article', null, 'sp-drawing');
      card.append(node('h3', drawing.title || drawing.name || 'Drawing'));
      card.append(node('p', `${drawing.number || drawing.drawing_number || ''} · ${drawing.scale || 'Not to Scale'} · ${drawing.status || (drawing.released ? 'Released' : 'Draft — For Review')}${drawing.edition ? ` · Edition ${drawing.edition}` : ''}${drawing.current === false ? ' · Superseded package' : ''}`, 'sp-muted'));
      const preview = sourceUrl(drawing.preview_url), pdf = sourceUrl(drawing.pdf_url), dxf = sourceUrl(drawing.dxf_url);
      if (preview) {
        const link = node('a', null, 'sp-drawing-preview'); link.href = pdf || preview; link.target = '_blank'; link.rel = 'noopener'; link.title = `Open ${drawing.title || 'drawing'} preview`;
        const image = node('img'); image.src = preview; image.alt = `${drawing.title || 'Drawing'} sheet preview`; image.loading = 'lazy'; link.append(image); card.append(link);
      } else card.append(node('p', 'Preview is not available.', 'sp-muted'));
      const downloads = node('div', null, 'sp-drawing-downloads');
      for (const [label, url] of [['PDF', pdf], ['Editable DXF', dxf], ['drawing bundle', sourceUrl(drawing.bundle_url)]]) if (url) {
        const link = node('a', `Download ${label}`); link.href = url; downloads.append(link);
      }
      card.append(downloads);
      for (const note of array(drawing.notes || drawing.missing)) card.append(node('p', display(note), 'sp-muted'));
      wrapper.append(card);
    }
  }
  function renderHistory(revision) {
    const wrapper = byId('sp-history'); wrapper.replaceChildren();
    const events = array(revision?.events);
    if (!events.length) { wrapper.append(node('li', 'No human review decisions recorded.', 'sp-muted')); return; }
    for (const event of events) {
      const item = node('li');
      const labels = {accept: 'Checklist findings accepted', correct: 'Checklist findings corrected', record: 'Extracted record corrected', geometry: 'Measured drawing records updated', accept_additional: 'Additional checklist proposals accepted', applied: 'Accepted checklist applied to survey', engineer_complete: 'Engineer review completed', technical_approve: 'QA technical review approved', technical_reject: 'QA returned for correction', release: 'Approved outputs released', reject: 'Checklist findings rejected'};
      item.dataset.reviewAction = event.action || event.decision || '';
      item.append(node('strong', event.label || labels[event.action || event.decision] || event.decision || event.action || 'Review event'));
      item.append(node('small', [event.actor_name || event.actor || event.user || event.reviewer || 'User not recorded', event.created_at || event.at || event.time].filter(Boolean).join(' · ')));
      if (event.reason || event.comment) item.append(node('p', event.reason || event.comment));
      wrapper.append(item);
    }
  }
  function renderAdditional(revision) {
    const panel = byId('sp-additional-proposals'), wrapper = byId('sp-additional-items');
    const proposals = array(revision?.suggested_items);
    const accepted = new Set(array(revision?.accepted_additional_items).map(item => JSON.stringify(item)));
    panel.hidden = !proposals.length; wrapper.replaceChildren();
    proposals.forEach((proposal, index) => {
      const row = node('div', null, 'sp-record');
      const reviewed = accepted.has(JSON.stringify(proposal));
      if (editable(revision)) {
        const label = node('label', null, 'sp-check'), check = node('input'); check.type = 'checkbox'; check.dataset.additionalIndex = String(index);
        check.dataset.reviewed = String(reviewed); check.disabled = reviewed || busy;
        label.append(check, node('span', proposal.label || proposal.title || display(proposal))); row.append(label);
      } else row.append(node('strong', proposal.label || proposal.title || display(proposal)));
      if (reviewed) row.append(node('strong', 'Reviewed addition - accepted into this package', 'sp-status-pill'));
      if (proposal.reason || proposal.description) row.append(node('p', proposal.reason || proposal.description));
      row.append(sourceLinks(proposal.sources)); wrapper.append(row);
    });
    if (byId('sp-additional-accept')) byId('sp-additional-accept').disabled = true;
  }
  function renderDocuments() {
    const wrapper = byId('sp-document-list'); if (!wrapper) return;
    wrapper.replaceChildren();
    for (const document of array(state.documents)) {
      const item = node('li'), url = sourceUrl(document.url);
      const name = document.filename || document.name || `Document ${document.id}`;
      if (url) { const link = node('a', name); link.href = url; link.target = '_blank'; link.rel = 'noopener'; item.append(link); } else item.append(node('span', name));
      if (document.created_at || document.status) item.append(node('small', [document.status, document.created_at].filter(Boolean).join(' · ')));
      wrapper.append(item);
    }
    let sessions = byId('sp-upload-sessions');
    if (!sessions) { sessions = node('div'); sessions.id = 'sp-upload-sessions'; wrapper.after(sessions); }
    sessions.replaceChildren();
    const tokens = array(state.upload_state?.own_tokens);
    if (tokens.length) {
      sessions.append(node('h3', 'Your open upload sessions'), node('p', 'Only close a session after its upload has stopped. Active uploads in other windows must finish first.', 'sp-muted'));
      tokens.forEach((token, index) => {
        const form = node('form'), label = node('label', null, 'sp-check'), check = node('input'); check.type = 'checkbox'; check.required = true;
        label.append(check, node('span', `Upload session ${index + 1} has stopped or was cancelled`));
        const button = node('button', 'Close my interrupted upload'); button.type = 'submit'; button.title = 'Close this stopped upload session; saved files are preserved'; button.disabled = busy;
        form.append(label, button);
        form.addEventListener('submit', event => { event.preventDefault(); if (form.reportValidity()) action('finish_upload', {token}, 'Interrupted upload session closed. Saved files are preserved.'); });
        sessions.append(form);
      });
    }
  }
  function renderGeometry(revision) {
    const wrapper = byId('sp-geometry-records'); if (!wrapper) return;
    if (geometryRevisionId !== String(revision?.id || '') || !geometryDirty) {
      geometryRecords = JSON.parse(JSON.stringify(array(revision?.drawing_records)));
      geometryRevisionId = String(revision?.id || '');
    }
    wrapper.replaceChildren();
    if (!geometryRecords.length) { const row = node('tr'), cell = node('td', 'No human-verified drawing records. Add a measured record from submitted evidence.'); cell.colSpan = 4; row.append(cell); wrapper.append(row); }
    geometryRecords.forEach((record, index) => {
      const row = node('tr');
      row.append(node('td', `${record.sheet || 'Site layout'} · ${record.label || record.equipment_type || record.kind || 'Measured record'}`));
      row.append(node('td', `X ${record.x ?? 0}, Y ${record.y ?? 0}; ${record.width ?? 0} × ${record.height ?? 0} ${record.unit || 'm'}`));
      row.append(node('td', record.source_id || 'No source'));
      const cell = node('td');
      for (const [actionName, label] of [['edit', 'Edit'], ['remove', 'Remove']]) {
        const button = node('button', label); button.type = 'button'; button.dataset.geometryAction = actionName; button.dataset.geometryIndex = String(index); button.disabled = !editable(revision) || busy; cell.append(button);
      }
      row.append(cell); wrapper.append(row);
    });
    const sourcePicker = byId('sp-geometry-source'), previous = sourcePicker.value;
    sourcePicker.replaceChildren(); const blank = node('option', 'Select submitted source'); blank.value = ''; sourcePicker.append(blank);
    for (const source of array(revision?.sources || state.sources)) {
      const option = node('option', source.label || source.filename || source.reference || source.source_id || source.id);
      option.value = String(source.source_id || source.id || ''); sourcePicker.append(option);
    }
    if (Array.from(sourcePicker.options).some(option => option.value === previous)) sourcePicker.value = previous;
    byId('sp-geometry-save').disabled = busy || !geometryDirty || !editable(revision);
    byId('sp-geometry-add').disabled = busy || !editable(revision);
  }
  function updateControls() {
    const revision = currentRevision(), isReady = ready(revision);
    const permissions = revision?.permissions || {};
    for (const [id, allowed] of [
      ['sp-engineer-complete', root.dataset.canComplete === 'true' && isReady && revision?.current !== false && !revision?.released && !revision?.engineer_complete && array(revision?.checklist_items).every(item => item.accepted || item.locked) && permissions.can_complete !== false],
      ['sp-technical-approve', root.dataset.canTechnicalReview === 'true' && isReady && revision?.current !== false && !revision?.released && revision?.engineer_complete && !revision?.technical_approved && permissions.can_technical_review !== false],
      ['sp-technical-reject', root.dataset.canTechnicalReview === 'true' && isReady && revision?.current !== false && !revision?.released],
      ['sp-release', root.dataset.canRelease === 'true' && isReady && !array(revision?.drawings).some(drawing => drawing.released && drawing.current !== false) && (revision?.can_release === true || state.can_release === true || permissions.can_release === true)]
    ]) if (byId(id)) byId(id).disabled = busy || stateStale || !allowed;
    const active = activeStatuses.has(statusKey(state.active?.status));
    const submit = byId('sp-submit-form')?.querySelector('button'); if (submit) submit.disabled = busy || stateStale || active || Boolean(state.upload_state?.inflight);
    const upload = byId('sp-document-form')?.querySelector('button'); if (upload) upload.disabled = busy || stateStale;
    root.querySelectorAll('#sp-upload-sessions button').forEach(button => { button.disabled = busy || stateStale; });
    byId('sp-refresh').disabled = polling || busy;
    byId('sp-retry').disabled = busy || stateStale;
    byId('sp-revision').disabled = busy;
    const correctionSave = byId('sp-correction-form').querySelector('button[type=submit]');
    if (correctionSave) correctionSave.disabled = busy || stateStale;
    root.querySelectorAll('[data-additional-index]').forEach(check => { check.disabled = busy || !editable(revision) || check.dataset.reviewed === 'true'; });
    if (byId('sp-additional-accept')) byId('sp-additional-accept').disabled = busy || !editable(revision) || !root.querySelector('[data-additional-index]:checked:not(:disabled)');
    const summary = byId('sp-review-summary');
    if (summary) summary.textContent = revision?.release_blocker || state.release_blocker || revision?.review_summary || 'Accept or correct checklist proposals, complete engineer review, then obtain QA technical review. Release also requires the existing survey approval workflow to close.';
    root.querySelectorAll('[data-accept-item],[data-correct-item],[data-correct-record]').forEach(button => { button.disabled = busy || !editable(revision); });
    root.querySelectorAll('[data-item-select]').forEach(check => {
      const item = array(revision?.checklist_items).find(candidate => itemId(candidate) === check.value);
      check.disabled = busy || !editable(revision) || Boolean(item?.accepted || item?.locked);
    });
    root.querySelectorAll('[data-geometry-action]').forEach(button => { button.disabled = busy || !editable(revision); });
    if (byId('sp-geometry-add')) byId('sp-geometry-add').disabled = busy || !editable(revision);
    if (byId('sp-geometry-save')) byId('sp-geometry-save').disabled = busy || !geometryDirty || !editable(revision);
    syncSelection();
  }
  function render(force = false) {
    renderStatus(); renderRevisions(); renderDocuments();
    const revision = currentRevision();
    const signature = JSON.stringify(revision);
    if (force || signature !== renderedSignature) {
      const scroller = root.querySelector('#sp-checklist-panel .sp-table-scroll'), top = scroller.scrollTop, left = scroller.scrollLeft;
      const validIds = new Set(array(revision?.checklist_items).filter(item => !item.accepted && !item.locked).map(itemId));
      for (const id of selected) if (!validIds.has(id)) selected.delete(id);
      renderChecklist(); renderRecords(revision); renderGaps(revision); renderDrawings(revision); renderHistory(revision); renderAdditional(revision); renderGeometry(revision);
      scroller.scrollTop = top; scroller.scrollLeft = left;
      renderedSignature = signature;
    }
    updateControls();
  }
  function schedule() {
    clearTimeout(pollTimer);
    if (!document.hidden && activeStatuses.has(statusKey(state.active?.status))) pollTimer = setTimeout(() => refresh(), 3000);
  }
  async function refresh(force = false) {
    if (refreshPending) {
      if (!force) return refreshPending;
      await refreshPending;
      return refresh(true);
    }
    const pending = readState(force);
    refreshPending = pending;
    try { return await pending; }
    finally { if (refreshPending === pending) refreshPending = null; }
  }
  async function readState(force) {
    polling = true; updateControls();
    try {
      const response = await fetch(root.dataset.stateUrl, {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}});
      if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('The server returned an unexpected page. Sign in again if your session has expired.');
      const payload = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload));
      const recovered = stateStale;
      stateStale = false;
      state = payload.state || payload;
      render(force);
      if (recovered && !busy) feedback('Saved processing state refreshed. Review the current results before continuing.');
      return true;
    } catch (error) { stateStale = true; feedback(`Could not refresh processing state. ${error.message} Use Refresh to retry; changes are paused until the saved state is available.`, true); return false; }
    finally { polling = false; updateControls(); schedule(); }
  }
  function switchTab(name, focus = false) {
    root.querySelectorAll('[data-tab]').forEach(tab => {
      const active = tab.dataset.tab === name;
      tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
      byId(`sp-${tab.dataset.tab}-panel`).hidden = !active;
      if (active && focus) tab.focus();
    });
    history.replaceState(null, '', `#${name}`);
  }
  root.querySelector('.sp-tabs').addEventListener('click', event => { const tab = event.target.closest('[data-tab]'); if (tab) switchTab(tab.dataset.tab); });
  root.querySelector('.sp-tabs').addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tabs = Array.from(root.querySelectorAll('[data-tab]')).filter(tab => !tab.hidden), current = tabs.indexOf(event.target.closest('[data-tab]'));
    if (current < 0) return;
    event.preventDefault();
    const target = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    switchTab(tabs[target].dataset.tab, true);
  });
  byId('sp-refresh').addEventListener('click', () => refresh(true));
  byId('sp-sidebar-toggle')?.addEventListener('click', event => {
    const open = event.currentTarget.getAttribute('aria-expanded') !== 'true';
    event.currentTarget.setAttribute('aria-expanded', String(open));
    byId('sp-sidebar').classList.toggle('is-open', open);
  });
  byId('sp-retry').addEventListener('click', () => action('retry', {revision_id: state.active?.id || selectedRevisionId}, 'Processing retry queued.'));
  byId('sp-revision').addEventListener('change', event => {
    if (busy) { event.target.value = selectedRevisionId; return; }
    if (geometryDirty && !window.confirm('Discard unsaved measured drawing edits and open another saved revision?')) { event.target.value = selectedRevisionId; return; }
    selectedRevisionId = event.target.value; selected.clear(); page = 0; geometryDirty = false; geometryEditIndex = -1;
    render(true);
  });
  byId('sp-search').addEventListener('input', () => { page = 0; renderChecklist(); });
  byId('sp-filter').addEventListener('change', () => { page = 0; renderChecklist(); });
  byId('sp-items-prev').addEventListener('click', () => { page--; renderChecklist(); });
  byId('sp-items-next').addEventListener('click', () => { page++; renderChecklist(); });
  byId('sp-select-visible')?.addEventListener('change', event => {
    root.querySelectorAll('[data-item-select]:not(:disabled)').forEach(check => {
      check.checked = event.target.checked;
      if (check.checked) selected.add(check.value); else selected.delete(check.value);
    }); syncSelection();
  });
  byId('sp-checklist-body').addEventListener('change', event => {
    if (!event.target.matches('[data-item-select]')) return;
    if (event.target.checked) selected.add(event.target.value); else selected.delete(event.target.value);
    syncSelection();
  });
  async function acceptItems(ids) {
    const result = await action('review', {revision_id: selectedRevisionId, decision: 'accept', finding_ids: ids, reason: 'Engineer reviewed the selected proposed checklist findings against their evidence.'}, 'Selected checklist proposals accepted.');
    if (result) { ids.forEach(id => selected.delete(id)); renderChecklist(); }
  }
  byId('sp-accept-selected')?.addEventListener('click', () => acceptItems(Array.from(selected)));
  byId('sp-checklist-body').addEventListener('click', event => {
    const accept = event.target.closest('[data-accept-item]');
    if (accept) { acceptItems([accept.dataset.acceptItem]); return; }
    const correct = event.target.closest('[data-correct-item]');
    if (!correct) return;
    correctionItem = array(currentRevision()?.checklist_items).find(item => itemId(item) === correct.dataset.correctItem);
    if (!correctionItem) return;
    correctionMode = 'checklist';
    byId('sp-correction-title').textContent = 'Correct checklist answer';
    byId('sp-correction-label').textContent = itemLabel(correctionItem) + (correctionItem.unit ? ` (${correctionItem.unit})` : '');
    byId('sp-correction-answer').value = display(correctionItem.value ?? correctionItem.proposed_answer).replace(/^Not recorded$/, '');
    byId('sp-correction-status').value = ['missing', 'not_applicable'].includes(normalStatus(correctionItem.status)) ? normalStatus(correctionItem.status) : 'recorded';
    byId('sp-correction-reason').value = '';
    byId('sp-correction-feedback').hidden = true;
    byId('sp-correction-unit-label').hidden = true;
    byId('sp-correction-type-label').hidden = true;
    byId('sp-correction-status-label').hidden = false;
    byId('sp-correction-dialog').showModal();
  });
  byId('sp-records').addEventListener('click', event => {
    const correct = event.target.closest('[data-correct-record]');
    if (!correct) return;
    correctionItem = array(currentRevision()?.findings).find(finding => String(finding.finding_key || finding.key) === correct.dataset.correctRecord);
    if (!correctionItem) return;
    correctionMode = 'record';
    byId('sp-correction-title').textContent = 'Correct extracted record';
    byId('sp-correction-label').textContent = correctionItem.label || correctionItem.field_hint || correctionItem.reference || 'Extracted evidence record';
    byId('sp-correction-answer').value = display(correctionItem.value).replace(/^Not recorded$/, '');
    byId('sp-correction-unit').value = correctionItem.unit || '';
    byId('sp-correction-type').value = typeof correctionItem.value === 'number' ? 'number' : typeof correctionItem.value === 'boolean' ? 'boolean' : typeof correctionItem.value === 'object' && correctionItem.value !== null ? 'json' : 'text';
    byId('sp-correction-reason').value = '';
    byId('sp-correction-feedback').hidden = true;
    byId('sp-correction-unit-label').hidden = false;
    byId('sp-correction-type-label').hidden = false;
    byId('sp-correction-status-label').hidden = true;
    byId('sp-correction-dialog').showModal();
  });
  byId('sp-correction-close').addEventListener('click', () => byId('sp-correction-dialog').close());
  byId('sp-correction-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!correctionItem) return;
    let value = byId('sp-correction-answer').value.trim();
    if (correctionMode === 'record') {
      const type = byId('sp-correction-type').value;
      if (type === 'number') {
        if (!value || !Number.isFinite(Number(value))) { feedback('Enter a finite numeric value for this extracted record.', true); return; }
        value = Number(value);
      } else if (type === 'boolean') {
        if (!['true', 'false'].includes(value.toLowerCase())) { feedback('Enter true or false for this extracted record.', true); return; }
        value = value.toLowerCase() === 'true';
      } else if (type === 'json') {
        try { value = JSON.parse(value); } catch (_) { feedback('Enter valid JSON for the structured extracted record.', true); return; }
      }
      const key = String(correctionItem.finding_key || correctionItem.key);
      const result = await action('review', {revision_id: selectedRevisionId, decision: 'record', finding_ids: [key], corrections: {[key]: {value, unit: byId('sp-correction-unit').value.trim()}}, reason: byId('sp-correction-reason').value.trim()}, 'Extracted record correction saved. Review its associated checklist proposals again.');
      if (result) byId('sp-correction-dialog').close();
      return;
    }
    const original = correctionItem.value ?? correctionItem.proposed_answer;
    const disposition = byId('sp-correction-status').value;
    if (disposition === 'missing') value = null;
    else if (disposition === 'not_applicable') value = 'Not applicable';
    else if (typeof original === 'object' && original !== null) {
      try { value = JSON.parse(value); } catch (_) { feedback('This answer contains a structured table. Keep valid JSON when correcting its rows.', true); return; }
    }
    else if (typeof original === 'number') {
      if (!value || !Number.isFinite(Number(value))) { feedback('Enter a valid numeric correction, or choose a missing / not-applicable disposition.', true); return; }
      value = Number(value);
    }
    else if (typeof original === 'boolean') {
      if (!['true', 'false'].includes(value.toLowerCase())) { feedback('Enter true or false for this recorded value.', true); return; }
      value = value.toLowerCase() === 'true';
    }
    const result = await action('review', {revision_id: selectedRevisionId, decision: 'correct', finding_ids: [itemId(correctionItem)], corrections: {[itemId(correctionItem)]: value}, reason: byId('sp-correction-reason').value.trim()}, 'Checklist correction saved.');
    if (result) byId('sp-correction-dialog').close();
  });
  byId('sp-submit-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    if (!event.target.reportValidity()) return;
    const result = await action('submit', {uploads_finished: '1'}, 'Survey snapshot saved and AI processing queued.');
    if (result) { selectedRevisionId = String(result.revision_id || result.revision?.id || state.active?.id || ''); geometryDirty = false; render(true); }
  });
  byId('sp-decision-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const decision = event.submitter?.value; if (!decision) return;
    const reason = byId('sp-decision-reason').value.trim();
    if (decision === 'technical_reject' && !reason) { byId('sp-decision-reason').setCustomValidity('Explain the correction required before returning this revision.'); byId('sp-decision-reason').reportValidity(); return; }
    byId('sp-decision-reason').setCustomValidity('');
    await action(decision === 'release' ? 'release' : 'review', {revision_id: selectedRevisionId, decision, reason}, decision === 'release' ? 'Approved outputs released.' : 'Review decision recorded.');
  });
  byId('sp-decision-reason')?.addEventListener('input', event => event.target.setCustomValidity(''));
  function uploadRequest(form, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); xhr.open('POST', root.dataset.actionUrl); xhr.setRequestHeader('X-CSRFToken', csrf()); xhr.setRequestHeader('Accept', 'application/json');
      xhr.upload.addEventListener('progress', event => { if (event.lengthComputable) onProgress(event.loaded / event.total * 100); });
      xhr.addEventListener('load', () => {
        let payload; try { payload = JSON.parse(xhr.responseText); } catch (_) { reject(new Error(`Document upload failed (${xhr.status}). Refresh if your session expired.`)); return; }
        if (xhr.status < 200 || xhr.status >= 300) reject(new Error(errorMessage(payload))); else resolve(payload);
      });
      xhr.addEventListener('error', () => reject(new Error('Document upload connection failed. Retry once the connection is available.')));
      xhr.addEventListener('abort', () => reject(new Error('Document upload was interrupted.')));
      xhr.send(form);
    });
  }
  byId('sp-document-form')?.addEventListener('submit', async event => {
    event.preventDefault(); if (busy || stateStale || !event.target.reportValidity()) return;
    if (byId('sp-documents').files.length > 5) { feedback('Choose up to five supporting documents per upload. You can upload another batch afterwards.', true); return; }
    busy = true; updateControls(); let token = '';
    const progress = byId('sp-upload-progress'), status = byId('sp-upload-status'); progress.hidden = false; progress.value = 0;
    try {
      const start = new FormData(); start.set('action', 'start_upload'); const started = await request(start); token = started.token || started.upload_token || '';
      const form = new FormData(event.target); form.set('action', 'upload_document'); if (token) form.set('token', token);
      status.textContent = 'Uploading supporting documents…';
      const result = await uploadRequest(form, value => { progress.value = value; status.textContent = `Uploading supporting documents · ${Math.round(value)}%`; });
      status.textContent = result.message || 'Supporting documents saved. Submit the survey when all uploads are complete.';
      event.target.reset(); feedback('Supporting documents uploaded. Originals are preserved.');
    } catch (error) { status.textContent = error.message; feedback(error.message, true); }
    finally {
      if (token) {
        try { const finish = new FormData(); finish.set('action', 'finish_upload'); finish.set('token', token); await request(finish); }
        catch (error) { feedback(`Upload completion could not be recorded. ${error.message}`, true); }
      }
      busy = false; progress.hidden = true; await refresh(true); updateControls();
    }
  });
  byId('sp-additional-items').addEventListener('change', () => {
    if (byId('sp-additional-accept')) byId('sp-additional-accept').disabled = busy || !editable(currentRevision()) || !root.querySelector('[data-additional-index]:checked:not(:disabled)');
  });
  byId('sp-additional-accept')?.addEventListener('click', async () => {
    const reason = byId('sp-additional-reason').value.trim();
    if (!reason) { byId('sp-additional-reason').setCustomValidity('Explain why the selected additional checklist proposals are applicable.'); byId('sp-additional-reason').reportValidity(); return; }
    const ids = Array.from(root.querySelectorAll('[data-additional-index]:checked:not(:disabled)')).map(check => Number(check.dataset.additionalIndex));
    await action('review', {revision_id: selectedRevisionId, decision: 'accept_additional', finding_ids: ids, reason}, 'Selected additions accepted into this generated package. The published template is unchanged.');
  });
  byId('sp-additional-reason')?.addEventListener('input', event => event.target.setCustomValidity(''));
  const geometryIds = ['sheet', 'kind', 'label', 'equipment', 'x', 'y', 'width', 'height', 'unit', 'source', 'value'];
  function syncGeometryKind() {
    const dimension = byId('sp-geometry-kind')?.value === 'dimension';
    const equipment = byId('sp-geometry-kind')?.value === 'equipment';
    if (byId('sp-geometry-value-label')) byId('sp-geometry-value-label').hidden = !dimension;
    if (byId('sp-geometry-value')) byId('sp-geometry-value').required = dimension;
    for (const key of ['width', 'height']) {
      const input = byId(`sp-geometry-${key}`);
      if (input) { if (equipment) input.min = '0'; else input.removeAttribute('min'); }
    }
  }
  byId('sp-geometry-kind')?.addEventListener('change', syncGeometryKind);
  function resetGeometryForm() {
    byId('sp-geometry-form')?.reset(); geometryEditIndex = -1;
    if (byId('sp-geometry-add')) byId('sp-geometry-add').textContent = 'Add measured record to this draft';
    if (byId('sp-geometry-cancel')) byId('sp-geometry-cancel').hidden = true;
    syncGeometryKind();
  }
  byId('sp-geometry-form')?.addEventListener('submit', event => {
    event.preventDefault(); if (busy || !editable(currentRevision()) || !event.target.reportValidity()) return;
    const values = Object.fromEntries(geometryIds.map(key => [key, byId(`sp-geometry-${key}`).value]));
    const record = {sheet: values.sheet, kind: values.kind, label: values.label.trim(), tag: values.label.trim(), equipment_type: values.equipment.trim(), x: Number(values.x), y: Number(values.y), width: Number(values.width), height: Number(values.height), unit: values.unit, source_id: values.source, verified: true};
    if (record.kind === 'equipment' && (record.width <= 0 || record.height <= 0)) { feedback('Equipment envelopes require positive measured width and height.', true); return; }
    if (record.kind !== 'equipment' && Math.hypot(record.width, record.height) === 0) { feedback('A measured line must have two distinct coordinates.', true); return; }
    if (values.kind !== 'equipment') record.points = [[record.x, record.y], [record.x + record.width, record.y + record.height]];
    if (values.kind === 'dimension') {
      record.value = Number(values.value);
      const factor = {mm: 1, cm: 10, m: 1000}[record.unit];
      if (record.value <= 0 || Math.abs(Math.hypot(record.width, record.height) - record.value) > Math.max(1 / factor, record.value * .01)) { feedback('The recorded dimension conflicts with its measured coordinates. Check both against the source before adding this record.', true); return; }
    }
    if (geometryEditIndex < 0) geometryRecords.push(record); else geometryRecords[geometryEditIndex] = {...geometryRecords[geometryEditIndex], ...record};
    geometryDirty = true; resetGeometryForm(); renderGeometry(currentRevision());
    byId('sp-geometry-status').textContent = 'Measured record staged locally. Save records to prepare the revised drawing edition.';
  });
  byId('sp-geometry-cancel')?.addEventListener('click', resetGeometryForm);
  byId('sp-geometry-records')?.addEventListener('click', event => {
    const button = event.target.closest('[data-geometry-action]'); if (!button || busy || !editable(currentRevision())) return;
    const index = Number(button.dataset.geometryIndex), record = geometryRecords[index]; if (!record) return;
    if (button.dataset.geometryAction === 'remove') { geometryRecords.splice(index, 1); geometryDirty = true; resetGeometryForm(); renderGeometry(currentRevision()); return; }
    geometryEditIndex = index;
    const values = {...record, source: record.source_id, equipment: record.equipment_type};
    for (const key of geometryIds) byId(`sp-geometry-${key}`).value = values[key] ?? '';
    byId('sp-geometry-confirmed').checked = false;
    byId('sp-geometry-add').textContent = 'Update measured record in this draft'; byId('sp-geometry-cancel').hidden = false; syncGeometryKind(); byId('sp-geometry-label').focus();
  });
  byId('sp-geometry-save')?.addEventListener('click', async () => {
    const reason = byId('sp-geometry-reason').value.trim();
    if (!reason) { byId('sp-geometry-reason').setCustomValidity('Record why these measured drawing records are being added or changed.'); byId('sp-geometry-reason').reportValidity(); return; }
    const result = await action('review', {revision_id: selectedRevisionId, decision: 'geometry', drawing_records: geometryRecords, reason}, 'Measured drawing records saved. Revised drawings are being prepared.');
    if (result) { geometryDirty = false; resetGeometryForm(); renderGeometry(currentRevision()); byId('sp-geometry-status').textContent = 'Measured records saved; the revised draft requires fresh engineer and QA review.'; }
  });
  byId('sp-geometry-reason')?.addEventListener('input', event => event.target.setCustomValidity(''));
  document.addEventListener('visibilitychange', () => { if (document.hidden) clearTimeout(pollTimer); else refresh(); });
  window.addEventListener('beforeunload', event => { if (geometryDirty) { event.preventDefault(); event.returnValue = ''; } });
  try { state = JSON.parse(byId('survey-processing-state')?.textContent || '{}'); } catch (_) { state = {}; }
  const initialTab = window.location.hash.slice(1);
  root.querySelectorAll('button').forEach(button => { if (!button.title) button.title = button.textContent.trim(); });
  if (isClient) {
    root.querySelectorAll('[data-tab]').forEach(tab => { tab.hidden = tab.dataset.tab !== 'drawings'; });
    byId('sp-stages').hidden = true;
    switchTab('drawings');
  } else if (['checklist', 'records', 'gaps', 'drawings', 'history'].includes(initialTab)) switchTab(initialTab);
  render(true); refresh();
})();
