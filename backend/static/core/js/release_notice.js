/* Per-account/current-release notice. Django owns acknowledgement and release identity. */
(() => {
  'use strict';
  const dialog = document.getElementById('ifield-release-notice');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const form = dialog.querySelector('#release-notice-form');
  const remember = dialog.querySelector('#release-notice-remember');
  const submit = dialog.querySelector('[data-release-submit]');
  const sessionButton = dialog.querySelector('[data-release-session]');
  const status = dialog.querySelector('[data-release-status]');
  const error = dialog.querySelector('[data-release-error]');
  if (!form || !remember || !submit || !sessionButton || !status || !error) return;
  const releaseId = dialog.dataset.releaseId || '';
  const actorKey = dialog.dataset.actorKey || '';
  const nonce = dialog.dataset.cacheNonce || '';
  const scopeValid = [releaseId, actorKey, nonce].every(value => value.length > 0 && value.length <= 256);
  const cacheKey = scopeValid ? 'ifield.release-notice.session.' + [actorKey, nonce, releaseId].map(encodeURIComponent).join('.') : null;
  try { if (cacheKey && sessionStorage.getItem(cacheKey) === 'dismissed') return; } catch (_) { /* Server session remains authoritative. */ }
  const previouslyFocused = document.activeElement;
  let busy = false;

  function rememberForLogin() {
    if (!cacheKey) return;
    try { sessionStorage.setItem(cacheKey, 'dismissed'); } catch (_) { /* Closing still permits manual work. */ }
  }
  function safeEndpoint() {
    if (!scopeValid) throw {code: 'invalid_context'};
    const raw = dialog.dataset.ackUrl || '';
    if (!raw) throw {code: 'invalid_context'};
    const url = new URL(raw, window.location.href);
    if (!['http:', 'https:'].includes(url.protocol) || url.origin !== window.location.origin || url.username || url.password || url.hash || url.search || !url.pathname.endsWith('/release-notices/ack/')) throw {code: 'invalid_context'};
    return url.href;
  }
  async function responseJson(response) {
    const maximum = 16 * 1024;
    const length = response.headers.get('Content-Length');
    if (length && Number(length) > maximum) throw {code: 'invalid_response'};
    if (!response.body || typeof response.body.getReader !== 'function') throw {code: 'invalid_response'};
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    while (true) {
      const item = await reader.read();
      if (item.done) break;
      size += item.value.byteLength;
      if (size > maximum) { await reader.cancel(); throw {code: 'invalid_response'}; }
      chunks.push(item.value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    try { return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes)); }
    catch (_) { throw {code: 'invalid_response'}; }
  }
  async function acknowledge(suppressCurrent) {
    const endpoint = safeEndpoint();
    const csrf = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    if (!csrf) throw {code: 'invalid_context'};
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(endpoint, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRFToken': csrf},
        body: JSON.stringify({release_id: releaseId, session_nonce: nonce, suppress_current: suppressCurrent}),
        signal: controller.signal,
      });
      if (response.status === 403 || response.status === 401) throw {code: 'session_changed'};
      const payload = await responseJson(response);
      if (!response.ok) throw {code: payload?.code === 'release_changed' ? 'release_changed' : payload?.code === 'session_changed' ? 'session_changed' : 'save_unavailable'};
      const validDismissal = suppressCurrent ? payload?.dismissal === 'remembered' : ['session_only', 'remembered'].includes(payload?.dismissal);
      if (!payload || payload.ok !== true || payload.release_id !== releaseId || !validDismissal) throw {code: 'invalid_response'};
      return payload;
    } catch (failure) {
      controller.abort();
      throw failure;
    } finally { clearTimeout(timer); }
  }
  function closeForLogin() {
    if (!dialog.open) return;
    rememberForLogin();
    dialog.close();
    // If a checked save was already requested, closing does not issue a second,
    // contradictory request. Its idempotent server result remains authoritative.
    if (!busy) {
      busy = true;
      acknowledge(false).catch(() => {}).finally(() => { busy = false; });
    }
  }
  function messageFor(failure) {
    if (failure?.code === 'release_changed') return 'A newer update is available. Continue working and reopen this page when ready to see it.';
    if (failure?.code === 'session_changed') return 'Your login session changed. Reopen this page when ready; no preference was confirmed here.';
    if (failure?.code === 'invalid_context') return 'This preference could not be saved from this page. Continue for this login, or reopen the page when ready.';
    return 'Your preference could not be confirmed. Try again, or continue for this login.';
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    if (!remember.checked) { closeForLogin(); return; }
    busy = true;
    remember.disabled = true;
    submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
    error.hidden = true;
    error.textContent = '';
    status.textContent = 'Saving…';
    try {
      await acknowledge(true);
      rememberForLogin();
      status.textContent = 'Saved for this update.';
      if (dialog.open) dialog.close();
    } catch (failure) {
      status.textContent = 'Not saved.';
      error.textContent = messageFor(failure);
      error.hidden = false;
      submit.textContent = 'Try again';
    } finally {
      busy = false;
      remember.disabled = false;
      submit.disabled = false;
      form.removeAttribute('aria-busy');
    }
  });
  dialog.querySelector('[data-release-close]')?.addEventListener('click', closeForLogin);
  sessionButton.addEventListener('click', closeForLogin);
  dialog.addEventListener('cancel', event => { event.preventDefault(); closeForLogin(); });
  dialog.addEventListener('close', () => {
    if (previouslyFocused && previouslyFocused !== document.body && previouslyFocused.isConnected) previouslyFocused.focus();
    else {
      const target = document.querySelector('main h1, .role-page-content h1, .workspace-nav-tiles [aria-current="page"]');
      if (target) { if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1'); target.focus(); }
    }
  });
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const items = [...dialog.querySelectorAll('button:not([disabled]),input:not([type="hidden"]):not([disabled]),a[href],[tabindex]:not([tabindex="-1"])')].filter(element => element.getClientRects().length);
    const first = items[0], last = items[items.length - 1];
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  dialog.showModal();
  dialog.querySelector('#release-notice-title')?.focus();
})();
