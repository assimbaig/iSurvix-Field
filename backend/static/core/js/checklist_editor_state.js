(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.ChecklistEditorState = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const copy = value => JSON.parse(JSON.stringify(value));
  const normal = value => String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
  const uid = prefix => prefix + '_' + crypto.randomUUID().replaceAll('-', '').slice(0, 20);
  class EditorState {
    constructor(definition, locked = false) {
      this.schema = copy(definition); this.locked = locked;
      const groups = [], canonical = new Map();
      for (const name of [...(this.schema.editor_groups || []), ...this.schema.sections.map(s => s.group || '')]) {
        const title = String(name).trim(); if (!title || canonical.has(normal(title))) continue;
        groups.push(title); canonical.set(normal(title), title);
      }
      this.schema.editor_groups = groups;
      for (const section of this.schema.sections) if (section.group) section.group = canonical.get(normal(section.group));
    }
    editable() { if (this.locked) throw Error('This revision is protected. Open an editable draft.'); }
    groups() { return this.schema.editor_groups; }
    section(id) { const section = this.schema.sections.find(s => s.id === id); if (!section) throw Error('Select an existing section.'); return section; }
    field(id) {
      for (const section of this.schema.sections) { const field = section.fields.find(f => f.id === id); if (field) return {section, field}; }
      throw Error('Select an existing checklist field.');
    }
    addGroup(name) {
      this.editable(); name = String(name || '').trim();
      if (!name || name.length > 160) throw Error('Enter a group name of at most 160 characters.');
      if (this.groups().some(g => normal(g) === normal(name))) throw Error('That group already exists.');
      if (this.groups().length >= 100) throw Error('A checklist supports at most 100 groups.');
      this.groups().push(name); return name;
    }
    renameGroup(old, name) {
      this.editable(); if (!this.groups().includes(old)) throw Error('Select a named group.');
      name = String(name).trim(); if (!name || name.length > 160) throw Error('Enter a group name of at most 160 characters.');
      if (this.groups().some(g => g !== old && normal(g) === normal(name))) throw Error('That group already exists.');
      this.schema.editor_groups = this.groups().map(g => g === old ? name : g);
      this.schema.sections.filter(s => s.group === old).forEach(s => s.group = name); return name;
    }
    orderSections() {
      const order = new Map([...this.groups(), ''].map((name, index) => [name, index]));
      this.schema.sections.sort((a, b) => order.get(a.group || '') - order.get(b.group || ''));
    }
    groupSections(ids, group) {
      this.editable(); if (!ids.length) throw Error('Select one or more section checkboxes.');
      const sections = ids.map(id => this.section(id));
      if (!this.groups().includes(group)) throw Error('Choose an existing group or add a new group first.');
      sections.forEach(section => section.group = group); this.orderSections();
    }
    ungroup(group) {
      this.editable(); if (!group || !this.groups().includes(group)) throw Error('Select a named group to ungroup.');
      this.schema.sections.filter(s => s.group === group).forEach(s => s.group = '');
      this.schema.editor_groups = this.groups().filter(name => name !== group);
    }
    moveSection(id, group) {
      this.editable(); if (group && !this.groups().includes(group)) throw Error('Sections can belong only to existing groups or Ungrouped.');
      this.section(id).group = group; this.orderSections();
    }
    addSection(group = '', title = 'New section') {
      this.editable(); if (group && !this.groups().includes(group)) throw Error('Invalid section parent.');
      if (this.schema.sections.length >= 100) throw Error('A checklist supports at most 100 sections.');
      const section = {id:uid('section'), title, group, fields:[{id:uid('field'), label:'New field', type:'text', required:false}]};
      this.schema.sections.push(section); this.orderSections(); return section;
    }
    addField(sectionId) {
      this.editable(); const section = this.section(sectionId);
      if (section.fields.length >= 300) throw Error('A section supports at most 300 fields.');
      const field = {id:uid('field'), label:'New field', type:'text', required:false}; section.fields.push(field); return field;
    }
    moveField(id, sectionId) {
      this.editable(); const found = this.field(id), target = this.section(sectionId);
      if (found.section === target) return;
      if (found.section.fields.length <= 1) throw Error('Keep one checkpoint in the original section. Rename that section, or add its replacement checkpoint before moving this one.');
      if (target.fields.length >= 300) throw Error('The target section already contains 300 fields.');
      found.section.fields = found.section.fields.filter(field => field.id !== id);
      target.fields.push(found.field);
    }
    remove(kind, id) {
      this.editable();
      if (kind === 'section') {
        this.section(id); if (this.schema.sections.length <= 1) throw Error('Keep at least one section.');
        this.schema.sections = this.schema.sections.filter(s => s.id !== id);
      } else if (kind === 'field') {
        const {section} = this.field(id); if (section.fields.length <= 1) throw Error('Keep at least one field in each section.');
        section.fields = section.fields.filter(f => f.id !== id);
      } else throw Error('Use Ungroup to retain the sections and fields of a group.');
    }
    reorder(kind, id, delta) {
      this.editable(); let list, value;
      if (kind === 'group') { list = this.groups(); value = id; }
      else if (kind === 'section') { const section = this.section(id); list = this.schema.sections.filter(s => (s.group || '') === (section.group || '')); value = section; }
      else { const found = this.field(id); list = found.section.fields; value = found.field; }
      const index = list.indexOf(value), target = index + delta; if (index < 0) throw Error('Select a valid hierarchy node.'); if (target < 0 || target >= list.length) return;
      const other = list[target];
      if (kind === 'section') { const a = this.schema.sections.indexOf(value), b = this.schema.sections.indexOf(other); [this.schema.sections[a], this.schema.sections[b]] = [other, value]; }
      else [list[index], list[target]] = [list[target], list[index]];
      if (kind === 'group') this.orderSections();
    }
    duplicateSection(id) {
      this.editable(); const original = this.section(id); if (original.room) throw Error('Create a separately named room through the standard checklist tools.');
      const section = copy(original); section.id = uid('section'); section.title = section.title.slice(0, 153) + ' (copy)';
      section.fields.forEach(field => field.id = uid('field'));
      this.schema.sections.splice(this.schema.sections.indexOf(original) + 1, 0, section); return section;
    }
    decision(id, value) {
      this.editable(); const decisions = this.schema.editor_recommendation_decisions ||= {};
      if (value) decisions[id] = value; else delete decisions[id];
    }
    apply(rec, values) {
      this.editable(); const decisions = this.schema.editor_recommendation_decisions || {};
      if (decisions[rec.id] === 'accepted') return {already:true};
      const field = copy(rec.field); Object.assign(field, values.field);
      if (field.system && field.type !== 'text') throw Error('The linked Site ID must remain a text field.');
      if (field.type === 'table' && !field.columns) field.columns = [{id:uid('column'),label:'Value'}];
      field.label = String(field.label || '').trim(); if (!field.label || field.label.length > 3000) throw Error('Enter a checkpoint label of at most 3000 characters.');
      let section = values.sectionId ? this.section(values.sectionId) : null;
      const title = String(values.sectionTitle || rec.section_title || '').trim();
      if (!section) {
        if (!title || title.length > 160) throw Error('Enter a section title of at most 160 characters.');
        section = this.schema.sections.find(s => normal(s.title) === normal(title) && (s.group || '') === (values.group || ''));
      }
      const existingId = 'rec_' + rec.id.replace(/^p_/, '');
      const duplicate = this.schema.sections.flatMap(s => s.fields.map(f => ({section:s,field:f}))).find(x => x.field.id === existingId || (x.section === section && normal(x.field.label) === normal(field.label)));
      if (duplicate) { this.decision(rec.id, 'accepted'); return {already:true,section:duplicate.section,field:duplicate.field}; }
      if (this.schema.sections.reduce((n,s) => n+s.fields.length, 0) >= 3000) throw Error('A checklist supports at most 3000 fields.');
      if (section && section.fields.length >= 300) throw Error('The target section already contains 300 fields.');
      if (!section) { section = this.addSection(values.group || '', title); section.fields = []; }
      field.id = existingId; field.recommendation_source = rec.source || '';
      section.fields.push(field); this.decision(rec.id, 'accepted'); return {section,field,already:false};
    }
  }
  return EditorState;
});
