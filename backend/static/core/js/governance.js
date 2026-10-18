(() => {
  'use strict';
  const theme = document.getElementById('workspace-theme');
  const applyTheme = value => { if (value === 'system') document.documentElement.removeAttribute('data-workspace-theme'); else document.documentElement.dataset.workspaceTheme = value; };
  if (theme) {
    try { const value = localStorage.getItem('workspace-theme'); theme.value = ['light','dark'].includes(value) ? value : 'system'; } catch {}
    applyTheme(theme.value);
    theme.addEventListener('change', () => { applyTheme(theme.value); try { localStorage.setItem('workspace-theme', theme.value); } catch {} });
  }
  const copy = document.getElementById('copy-invitation');
  if (copy) copy.addEventListener('click', async () => {
    const link = document.getElementById('workspace-invite-link');
    const status = document.getElementById('copy-invitation-status');
    try { await navigator.clipboard.writeText(link.href); status.textContent = ' Link copied.'; }
    catch { const range = document.createRange(); range.selectNodeContents(link); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range); status.textContent = ' Link selected. Copy it using your browser.'; }
  });
  const search = document.getElementById('workspace-search');
  if (search) search.addEventListener('input', () => {
    const query = search.value.toLowerCase().trim();
    document.querySelectorAll('[data-workspace-search]').forEach(row => { row.hidden = !row.dataset.workspaceSearch.toLowerCase().includes(query); });
  });
  document.querySelectorAll('[data-confirm-form]').forEach(form => {
    form.addEventListener('submit', event => { if (!window.confirm(form.dataset.confirmForm)) event.preventDefault(); });
  });
})();

 document.getElementById("workspace-industry-filter")?.addEventListener("change",()=>{document.getElementById("workspace-project-filter").value="all";});
