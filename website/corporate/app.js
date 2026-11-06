'use strict';
const menuButton = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#navigation');
function closeMenu() {
  navigation.classList.remove('is-open');
  menuButton.setAttribute('aria-expanded', 'false');
  menuButton.setAttribute('aria-label', 'Open navigation');
}
menuButton.addEventListener('click', () => {
  const open = menuButton.getAttribute('aria-expanded') !== 'true';
  menuButton.setAttribute('aria-expanded', String(open));
  menuButton.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  navigation.classList.toggle('is-open', open);
});
navigation.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
document.addEventListener('click', event => { if (!event.target.closest('.header')) closeMenu(); });
window.matchMedia('(min-width: 801px)').addEventListener('change', closeMenu);
document.querySelector('#year').textContent = String(new Date().getFullYear());

const challenges = [...document.querySelectorAll('.challenge')];
challenges.forEach(challenge => challenge.addEventListener('toggle', () => {
  if (challenge.open) challenges.forEach(other => { if (other !== challenge) other.open = false; });
}));
if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
    });
  }, { threshold: 0.06 });
  document.querySelectorAll('.capability-card, .product-card, .feature-item, .scope-section, .challenge-intro, .premium-cost .container, .premium-next, .custom-build-panel').forEach(element => {
    element.classList.add('motion-target'); observer.observe(element);
  });
}

const enquiryForm = document.querySelector('#enquiry-form');
if (enquiryForm) {
  const interest = document.querySelector('#interest');
  const requestedInterest = new URLSearchParams(window.location.search).get('interest');
  if ([...interest.options].some(option => option.value === requestedInterest)) interest.value = requestedInterest;
  const preview = document.querySelector('#enquiry-preview');
  const result = document.querySelector('#enquiry-result');
  const copyStatus = document.querySelector('#copy-status');
  enquiryForm.addEventListener('submit', event => {
    event.preventDefault();
    if (!enquiryForm.reportValidity()) return;
    const values = new FormData(enquiryForm);
    const topic = interest.selectedOptions[0].textContent;
    const subject = 'iSurvix enquiry — ' + topic;
    const body = [
      'Hello iSurvix team,', '',
      'I would like to discuss ' + topic + '.', '',
      'Name: ' + String(values.get('name')).trim(),
      'Email: ' + String(values.get('email')).trim(),
      ...(String(values.get('company')).trim() ? ['Company: ' + String(values.get('company')).trim()] : []),
      ...(String(values.get('location')).trim() ? ['Project location: ' + String(values.get('location')).trim()] : []),
      ...(values.get('stage') ? ['Current stage: ' + values.get('stage')] : []),
      '', 'Requirements:', String(values.get('brief')).trim(), '',
      'Please let me know the next step and any additional information you need.', '',
      'Regards,', String(values.get('name')).trim()
    ].join('\n');
    preview.value = 'Subject: ' + subject + '\n\n' + body;
    document.querySelector('#open-enquiry-email').href = 'mailto:info@isurvix.com?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
    copyStatus.textContent = '';
    result.hidden = false;
    result.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest' });
    preview.focus({ preventScroll: true });
  });
  document.querySelector('#copy-enquiry').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(preview.value);
      copyStatus.textContent = 'Enquiry copied. Paste it into your email app to send it.';
    } catch {
      preview.focus(); preview.select();
      copyStatus.textContent = 'The draft is selected. Use Copy to place it on your clipboard.';
    }
  });
}

// iField workflow illustrations: mouse, touch and keyboard tabs.
const iFieldTabs = [...document.querySelectorAll('.sp-tab[role="tab"]')];
function selectiFieldTab(tab, moveFocus = false) {
  iFieldTabs.forEach(item => {
    const selected = item === tab;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
    document.getElementById(item.getAttribute('aria-controls')).hidden = !selected;
  });
  if (moveFocus) tab.focus();
}
iFieldTabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectiFieldTab(tab));
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % iFieldTabs.length;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + iFieldTabs.length) % iFieldTabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = iFieldTabs.length - 1;
    if (next !== undefined) { event.preventDefault(); selectiFieldTab(iFieldTabs[next], true); }
  });
});

// Open the intended workflow when a homepage slide links directly to it.
function synciFieldWorkflowHash() {
  const selected=iFieldTabs.find(tab=>'#'+tab.getAttribute('aria-controls')===window.location.hash);
  if(selected)selectiFieldTab(selected);
}
synciFieldWorkflowHash();window.addEventListener('hashchange',synciFieldWorkflowHash);
