'use strict';
// Native details/summary and the fixed anchor also work without JavaScript.
(() => {
  const disclosure = document.querySelector('.page-index .platform-login');
  if (!disclosure) return;
  const summary = disclosure.querySelector('summary');
  const menuButton = document.querySelector('.menu-toggle');
  const navigation = document.querySelector('#navigation');
  disclosure.addEventListener('toggle', () => {
    if (disclosure.open && menuButton && menuButton.getAttribute('aria-expanded') === 'true') {
      if (navigation) navigation.classList.remove('is-open');
      menuButton.setAttribute('aria-expanded', 'false');
      menuButton.setAttribute('aria-label', 'Open navigation');
    }
  });
  document.addEventListener('click', event => {
    if (!disclosure.contains(event.target)) disclosure.open = false;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && disclosure.open) {
      disclosure.open = false;
      summary.focus({preventScroll: true});
    }
  });
  disclosure.addEventListener('focusout', () => {
    // Wait until the browser has completed the keyboard focus transition.
    setTimeout(() => {
      if (!disclosure.contains(document.activeElement)) disclosure.open = false;
    }, 0);
  });
  if (menuButton) menuButton.addEventListener('click', () => { disclosure.open = false; });
})();
