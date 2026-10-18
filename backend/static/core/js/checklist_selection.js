(() => {
  'use strict';
  const form = document.getElementById('checklist-selection-form');
  if (!form) return;
  const catalog = document.getElementById('selection-catalog');
  const sections = Array.from(catalog.querySelectorAll('.cs-section')).map(element => ({
    element,
    title: element.dataset.sectionTitle,
    group: element.dataset.sectionGroup,
    check: element.querySelector('.cs-section-check'),
    count: element.querySelector('.cs-section-count'),
    fieldsElement: element.querySelector('.cs-fields'),
    collapse: element.querySelector('.cs-collapse'),
    fields: Array.from(element.querySelectorAll('.cs-field')).map(row => ({row, label: row.dataset.fieldLabel, check: row.querySelector('[name=field_ids]')})),
  }));
  const fields = sections.flatMap(section => section.fields);
  const preview = document.getElementById('selection-preview');
  const status = document.getElementById('selection-count');
  const validation = document.getElementById('selection-validation');
  const search = document.getElementById('selection-search');
  const normalize = text => text.normalize('NFKC').toLocaleLowerCase().trim();
  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function setExpanded(section, open) {
    section.fieldsElement.hidden = !open;
    section.collapse.setAttribute('aria-expanded', String(open));
    section.collapse.textContent = open ? 'Collapse' : 'Expand';
  }
  function update() {
    preview.replaceChildren();
    let itemCount = 0, sectionCount = 0;
    for (const section of sections) {
      const selected = section.fields.filter(field => field.check.checked);
      itemCount += selected.length;
      if (selected.length) sectionCount++;
      section.check.checked = selected.length > 0 && selected.length === section.fields.length;
      section.check.indeterminate = selected.length > 0 && selected.length < section.fields.length;
      section.check.disabled = !section.fields.length;
      section.check.setAttribute('aria-checked', section.check.indeterminate ? 'mixed' : String(section.check.checked));
      section.count.textContent = `${selected.length} / ${section.fields.length} items selected`;
      if (!selected.length) continue;
      const group = node('section', undefined, 'cs-preview-section');
      group.append(node('h3', `${section.title} (${selected.length})`));
      const list = node('ul');
      for (const field of selected) {
        const row = node('li'), remove = node('button', '×');
        remove.type = 'button'; remove.setAttribute('aria-label', `Remove ${field.label}`);
        remove.addEventListener('click', () => { field.check.checked = false; update(); });
        row.append(node('span', field.label), remove); list.append(row);
      }
      group.append(list); preview.append(group);
    }
    if (!itemCount) preview.append(node('p', 'Select source items to preview your new checklist.', 'gw-empty'));
    status.textContent = `${sectionCount} ${sectionCount === 1 ? 'section' : 'sections'} · ${itemCount} of ${fields.length} items selected`;
    document.getElementById('selection-mobile-review').textContent = itemCount + ' selected · Review & create draft';
    status.dataset.sections = sectionCount; status.dataset.items = itemCount;
    if (itemCount) validation.hidden = true;
  }
  for (const section of sections) {
    section.check.addEventListener('change', () => { section.fields.forEach(field => { field.check.checked = section.check.checked; }); update(); });
    section.fields.forEach(field => field.check.addEventListener('change', update));
    section.collapse.addEventListener('click', () => setExpanded(section, section.fieldsElement.hidden));
  }
  document.getElementById('selection-all').addEventListener('click', () => { fields.forEach(field => { field.check.checked = true; }); update(); });
  document.getElementById('selection-clear').addEventListener('click', () => { fields.forEach(field => { field.check.checked = false; }); update(); });
  search.addEventListener('input', () => {
    const query = normalize(search.value);
    let matches = 0;
    for (const section of sections) {
      const sectionMatch = normalize(`${section.title} ${section.group}`).includes(query);
      let sectionMatches = 0;
      for (const field of section.fields) {
        const show = !query || sectionMatch || normalize(field.label).includes(query);
        field.row.hidden = !show;
        if (show) sectionMatches++;
      }
      section.element.hidden = !sectionMatches;
      if (query && sectionMatches) setExpanded(section, true);
      matches += sectionMatches;
    }
    document.getElementById('selection-search-status').textContent = query ? `${matches} of ${fields.length} source items match · selection preserved` : `${fields.length} items in this source`;
    document.getElementById('selection-no-results').hidden = matches > 0;
  });
  form.addEventListener('submit', event => {
    if (!fields.some(field => field.check.checked)) {
      event.preventDefault(); validation.hidden = false; validation.scrollIntoView({block: 'center', behavior: 'smooth'});
    }
  });
  const sourceForm = document.getElementById('selection-source-form');
  const initialSource = document.getElementById('selection-source').value;
  sourceForm.addEventListener('submit', event => {
    if (fields.some(field => field.check.checked) && document.getElementById('selection-source').value !== initialSource && !window.confirm('Loading another source clears this unsaved selection. Continue?')) event.preventDefault();
  });
  update();
})();
