/* Company Admin dashboard interactions. Forms remain authenticated Django POSTs. */
(() => {
  'use strict';
  const root = document.getElementById('admin-dashboard');
  if (!root) return;
  const dialogs = {
    project: document.getElementById('admin-project-dialog'),
    client: document.getElementById('admin-client-dialog'),
    invite: document.getElementById('admin-invite-dialog'),
  };
  const triggers = new Map();
  function openDialog(key, trigger) {
    if (!Object.prototype.hasOwnProperty.call(dialogs, key)) return;
    const dialog = dialogs[key];
    if (!dialog || typeof dialog.showModal !== 'function') return;
    triggers.set(dialog, trigger || root.querySelector(`[data-ad-open="${key}"]`));
    if (!dialog.open) dialog.showModal();
    const field = dialog.querySelector('[aria-invalid="true"], input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])');
    if (field) field.focus();
  }
  root.querySelectorAll('[data-ad-open]').forEach(button => {
    button.addEventListener('click', () => openDialog(button.dataset.adOpen, button));
  });
  Object.values(dialogs).filter(Boolean).forEach(dialog => {
    dialog.querySelectorAll('[data-ad-close]').forEach(button => button.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const focusable = [...dialog.querySelectorAll('a[href],button:not([disabled]),input:not([type="hidden"]):not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
        .filter(element => element.getClientRects().length);
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    dialog.addEventListener('close', () => {
      const trigger = triggers.get(dialog);
      if (trigger && trigger.isConnected) trigger.focus();
    });
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
  });
  root.querySelectorAll('form[data-ad-save]').forEach(form => {
    let submitting = false;
    const controls = [...form.querySelectorAll('button[type="submit"], input[type="submit"]')];
    const originalDisabled = controls.map(control => control.disabled);
    function resetSubmission() {
      submitting = false;
      form.removeAttribute('aria-busy');
      controls.forEach((control, index) => { control.disabled = originalDisabled[index]; });
      const state = form.querySelector('[data-ad-save-state]');
      if (state) state.textContent = '';
    }
    form.addEventListener('submit', event => {
      if (submitting) { event.preventDefault(); return; }
      if (!form.checkValidity()) { event.preventDefault(); form.reportValidity(); return; }
      submitting = true;
      form.setAttribute('aria-busy', 'true');
      controls.forEach(control => { control.disabled = true; });
      const state = form.querySelector('[data-ad-save-state]');
      if (state) state.textContent = 'Saving…';
    });
    // Browser Back restores entered values; it must also restore a usable form.
    window.addEventListener('pageshow', resetSubmission);
  });
  openDialog(root.dataset.openDialog);
})();
