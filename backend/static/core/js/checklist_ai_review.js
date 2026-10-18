(() => {
  'use strict';
  let sources = {};
  try { sources = JSON.parse(document.getElementById('critical-review-sources').textContent) || {}; } catch {}
  document.querySelectorAll('[data-review-source]').forEach(link => {
    const url = sources[link.dataset.reviewSource];
    if (typeof url === 'string' && url.startsWith('/') && !url.startsWith('//')) { link.href = url; link.target = '_blank'; link.rel = 'noopener'; }
  });
  document.querySelectorAll('[data-review-date]').forEach(time => { const date = new Date(time.dateTime); if (!Number.isNaN(date.getTime())) time.textContent = date.toLocaleString(); });
  const request = document.getElementById('critical-review-request');
  if (request) request.addEventListener('submit', async event => {
    event.preventDefault(); const button = request.querySelector('button'), status = document.getElementById('critical-review-progress'); button.disabled = true; status.hidden = false;
    status.textContent = 'Reviewing evidence with the local model. This may take several minutes.';
    try {
      const response = await fetch(request.action, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':request.querySelector('[name=csrfmiddlewaretoken]').value},body:'{}'});
      if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error || 'Local review did not complete. Check the connection and retry.'); }
      window.location.reload();
    } catch (error) { status.textContent = error.message; button.disabled = false; }
  });
  document.querySelectorAll('[data-review-share]').forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault(); const button = form.querySelector('button'), status = form.querySelector('.cr-share-status'); button.disabled = true;
    try {
      const response = await fetch(form.action, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({shared:form.querySelector('[type=checkbox]').checked,expected_digest:form.querySelector('[name=expected_digest]').value})});
      if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error || 'The report changed or sharing is unavailable. Reload and review the current report.'); }
      window.location.reload();
    } catch (error) { status.textContent = error.message; button.disabled = false; }
  }));
})();
