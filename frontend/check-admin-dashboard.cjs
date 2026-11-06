// Browser unit/integration fixture for the real Admin dashboard controller and
// scoped styles. Authenticated Django records/actions are verified separately.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const read = relative => fs.existsSync(path.join(root, relative)) ? fs.readFileSync(path.join(root, relative), 'utf8') : '';
const css = read('backend/static/core/css/admin_dashboard.css');
const stylesBefore = ['style.css', 'platform_navigation.css'].map(name => read('backend/static/core/css/' + name)).join('\n');
const stylesAfter = ['task_create.css', 'governance.css', 'activity_workflow.css', 'people_tables.css', 'role_layout.css', 'enterprise.css', 'appearance.css', 'workspace_navigation.css', 'button_depth.css', 'release_notice.css'].map(name => read('backend/static/core/css/' + name)).join('\n');
const assets = stylesBefore + '\n' + css + '\n' + stylesAfter;
const controller = read('backend/static/core/js/admin_dashboard.js');
const fixture = (autoOpen = '') => `<!doctype html><html data-color-scheme="navy"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${assets}</style></head><body class="role-layout workspace-header-navigation governance-page admin-overview-page" data-role="ADMIN"><header class="app-header enterprise-header"><a class="enterprise-brand">iSurvix</a><div class="enterprise-header-actions">Synthetic Admin</div><div class="workspace-navigation-row"><nav class="platform-nav workspace-nav-tiles"><a aria-current="page">Dashboard</a><a>Tasks</a><a>Projects</a><a>Administration</a></nav></div></header><div class="role-page-content"><nav class="enterprise-breadcrumb">Workspace / Dashboard</nav><main class="ad-main" id="admin-dashboard" data-open-dialog="${autoOpen}"><header class="ad-heading"><div class="ad-identity"><span class="ad-company-symbol">Q</span><div><p class="ad-eyebrow">QA TEST DATA ? Long synthetic company name</p><h1>Company overview</h1><p class="ad-muted">Company summary and everyday administration in one place.</p></div></div><form class="ad-scope-form"><label>Project scope<select><option>All permitted projects</option></select></label><button>Apply</button></form></header><nav class="ad-actions" aria-label="Create company records"><button type="button" data-ad-open="project">+ New project</button><a href="#task">+ New task</a><button type="button" data-ad-open="client">+ New client</button><button type="button" data-ad-open="invite">+ Invite user</button></nav><section class="ad-metrics" aria-label="Company totals">${['Sites','Photos','Activities','Projects','Clients','People'].map((name, i) => `<div><strong>${i+1}</strong><span>${name}<small>Verified count definition</small></span></div>`).join('')}</section><div class="ad-content-grid"><section class="ad-panel ad-projects"><header class="ad-panel-head"><h2>Projects at a glance</h2><span>2 projects</span></header><form class="ad-search"><label>Find project<input name="admin_project_q"></label><button>Search</button></form><div class="ad-table-scroll" tabindex="0" role="region" aria-label="Projects"><table><thead><tr><th>Project / client</th><th>Sites</th><th>Activities</th><th>Photos</th><th>Waiting for review</th><th>Action</th></tr></thead><tbody>${Array.from({length: 30}, (_, i) => `<tr><td>Long synthetic project ${i}<small>Client organization</small></td><td>12</td><td>20</td><td>150</td><td>3 awaiting review</td><td><a href="#project">Open</a></td></tr>`).join('')}</tbody></table></div><footer class="ad-panel-foot">Page 1 of 2</footer></section><section class="ad-panel ad-review"><header class="ad-panel-head"><h2>Waiting for review</h2></header><div class="ad-review-rows">${['QA review','Team Lead approval','Client decision','Other / historical'].map(name=>`<div><span>${name}<small>Recorded workflow stage</small></span><strong>2</strong></div>`).join('')}</div><p class="ad-note">Counts monitor workflow; they do not grant review permission.</p></section><section class="ad-panel ad-recent"><header class="ad-panel-head"><h2>Recent activity</h2></header><div class="ad-table-scroll" tabindex="0" role="region" aria-label="Recent activity"><table><thead><tr><th>Time</th><th>Site</th><th>Latest action</th></tr></thead><tbody>${Array.from({length: 8}, (_, i)=>`<tr><td>10:4${i}</td><td>SYNTH-${i}</td><td>Saved activity<small>Project name</small></td></tr>`).join('')}</tbody></table></div></section><section class="ad-panel ad-people"><header class="ad-panel-head"><h2>People by role</h2></header><div class="ad-table-scroll" tabindex="0" role="region" aria-label="People by role"><table><tbody>${['Engineer','QA Engineer','Team Lead','Client'].map(name=>`<tr><td>${name}</td><td>2</td></tr>`).join('')}</tbody></table></div><footer class="ad-panel-foot">Distinct active people</footer></section></div><dialog id="admin-project-dialog" class="ad-dialog" aria-labelledby="admin-project-title"><header><h2 id="admin-project-title">New project</h2><button type="button" data-ad-close aria-label="Close new project">×</button></header><form class="ad-dialog-form" method="post" action="/test/project" data-ad-save><input name="csrfmiddlewaretoken" value="synthetic" type="hidden"><label for="project-name">Project name</label><input id="project-name" name="name" value="${autoOpen ? 'Retained project' : ''}" required><p class="ad-server-errors" role="alert">${autoOpen ? 'This project name already exists. Your input is retained.' : ''}</p><p data-ad-save-state role="status"></p><button type="submit">Create project</button></form></dialog><dialog id="admin-client-dialog" class="ad-dialog" aria-labelledby="admin-client-title"><header><h2 id="admin-client-title">New client</h2><button type="button" data-ad-close aria-label="Close new client">×</button></header><form><label>Client name<input required></label><button>Create client</button></form></dialog><dialog id="admin-invite-dialog" class="ad-dialog" aria-labelledby="admin-invite-title"><header><h2 id="admin-invite-title">Invite user</h2><button type="button" data-ad-close aria-label="Close invitation">×</button></header><form><label>Email<input type="email" required></label><button>Create invitation</button></form></dialog></main></div><script>${controller}</script></body></html>`;
const checks = [];
function check(name, run) { try { run(); checks.push({name, passed: true}); } catch (error) { checks.push({name, passed: false, error: error.message}); process.exitCode = 1; } }
(async () => {
  const browser = await chromium.launch(require('./browser-test-options.cjs')());
  try {
    const page = await browser.newPage({viewport: {width: 1366, height: 768}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent(fixture());
    await page.locator('[data-ad-open="project"]').click();
    const state = await page.evaluate(() => ({open: document.getElementById('admin-project-dialog').open, active: document.activeElement.id}));
    check('New project dialog opens and receives form focus', () => { assert.equal(state.open, true); assert.equal(state.active, 'project-name'); });
    await page.keyboard.press('Escape');
    const restored = await page.evaluate(() => ({open: document.getElementById('admin-project-dialog').open, trigger: document.activeElement.dataset.adOpen}));
    check('Escape closes dialog and restores trigger focus', () => { assert.equal(restored.open, false); assert.equal(restored.trigger, 'project'); });
    for (const key of ['client','invite']) {
      await page.locator(`[data-ad-open="${key}"]`).click();
      const opened = await page.evaluate(key => { const d=document.getElementById(`admin-${key}-dialog`); return {open:d.open, focused:document.activeElement===d.querySelector('input')}; }, key);
      check(`${key} action opens the correct form with field focus`, () => { assert.equal(opened.open,true); assert.equal(opened.focused,true); });
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');
      const trapped = await page.evaluate(key => document.activeElement.closest('dialog')?.id === `admin-${key}-dialog`, key);
      check(`${key} dialog keeps keyboard focus inside`, () => assert.equal(trapped,true));
      await page.locator(`#admin-${key}-dialog [data-ad-close]`).click();
      const returned = await page.evaluate(() => document.activeElement.dataset.adOpen);
      check(`${key} trigger is restored`, () => assert.equal(returned,key));
    }
    await page.locator('[data-ad-open="project"]').click();
    const invalid = await page.evaluate(() => { const form=document.querySelector('#admin-project-dialog form'); form.dispatchEvent(new SubmitEvent('submit',{bubbles:true,cancelable:true})); return {busy:form.getAttribute('aria-busy'),disabled:form.querySelector('[type=submit]').disabled,value:form.querySelector('[name=name]').value}; });
    check('Invalid input stays editable without false saving state', () => { assert.equal(invalid.busy,null); assert.equal(invalid.disabled,false); assert.equal(invalid.value,''); });
    await page.locator('#project-name').fill('Retained user input');
    const duplicate = await page.evaluate(() => {
      const form=document.querySelector('#admin-project-dialog form'), allowed=[];
      // Observe normal submit permission, then suppress fixture-only navigation.
      form.addEventListener('submit',event=>{allowed.push(!event.defaultPrevented);event.preventDefault();});
      form.dispatchEvent(new SubmitEvent('submit',{bubbles:true,cancelable:true}));
      form.dispatchEvent(new SubmitEvent('submit',{bubbles:true,cancelable:true}));
      return {allowed,busy:form.getAttribute('aria-busy'),disabled:form.querySelector('[type=submit]').disabled,state:form.querySelector('[data-ad-save-state]').textContent};
    });
    check('One valid submission is permitted and repeated submission is blocked', () => { assert.deepEqual(duplicate.allowed,[true,false]); assert.equal(duplicate.busy,'true'); assert.equal(duplicate.disabled,true); });
    check('Pending submit reports Saving and never claims server success', () => { assert.equal(duplicate.state,'Saving…'); assert.ok(!duplicate.state.includes('Saved')); });
    const back = await page.evaluate(() => { window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})); const form=document.querySelector('#admin-project-dialog form'); return {busy:form.getAttribute('aria-busy'),disabled:form.querySelector('[type=submit]').disabled,value:form.querySelector('[name=name]').value}; });
    check('Browser Back recovery restores a usable form and entered value', () => { assert.equal(back.busy,null); assert.equal(back.disabled,false); assert.equal(back.value,'Retained user input'); });
    await page.setContent(fixture('project'));
    const bound = await page.evaluate(() => ({open:document.getElementById('admin-project-dialog').open,value:document.getElementById('project-name').value,error:document.querySelector('.ad-server-errors').textContent}));
    check('Returned validation form reopens with bound data and error', () => { assert.equal(bound.open,true); assert.equal(bound.value,'Retained project'); assert.match(bound.error,/already exists/); });
    await page.setContent(fixture('__proto__'));
    const unknownOpen = await page.evaluate(() => [...document.querySelectorAll('dialog')].some(d=>d.open));
    check('An unknown automatic dialog key opens nothing', () => assert.equal(unknownOpen,false));
    for (const [width, height] of [[1366,768],[1920,1080],[390,844]]) {
      await page.setViewportSize({width,height});
      await page.setContent(fixture());
      const geometry = await page.evaluate(() => ({overflow: document.documentElement.scrollWidth > innerWidth, pageHeight: document.documentElement.scrollHeight, viewport: innerHeight, projects: (()=>{const e=document.querySelector('.ad-projects .ad-table-scroll');return {scrollable:e.scrollHeight>e.clientHeight, overflow:getComputedStyle(e).overflowY};})()}));
      check(`No page-wide horizontal overflow at ${width}`, () => assert.equal(geometry.overflow, false));
      if (width > 980) check(`Desktop dashboard fits viewport at ${width} with a working project pane`, () => { assert.ok(geometry.pageHeight <= geometry.viewport + 1, JSON.stringify(geometry)); assert.equal(geometry.projects.scrollable, true); assert.ok(['auto','scroll'].includes(geometry.projects.overflow)); });
      if (width <= 600) { const heading = await page.evaluate(() => {const r=document.querySelector('.ad-heading').getBoundingClientRect(),i=document.querySelector('.ad-identity').getBoundingClientRect();return {height:r.height,identityWidth:i.width};}); check('Mobile heading remains readable without character-by-character wrapping',()=>{assert.ok(heading.height<170,JSON.stringify(heading));assert.ok(heading.identityWidth>250,JSON.stringify(heading));}); }
      await page.locator('[data-ad-open="project"]').click();
      const dialogBounds = await page.evaluate(() => {const r=document.getElementById('admin-project-dialog').getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight};});
      check(`Project dialog remains within viewport at ${width}`, () => { assert.ok(dialogBounds.left>=0); assert.ok(dialogBounds.right<=dialogBounds.width); assert.ok(dialogBounds.top>=0); assert.ok(dialogBounds.bottom<=dialogBounds.height); });
    }
    check('Controller has no JavaScript exceptions', () => assert.deepEqual(errors, []));
  } finally { await browser.close(); }
  console.log(JSON.stringify({suite: 'Admin dashboard browser controller and geometry fixture', passed: checks.filter(item=>item.passed).length, total:checks.length, checks}, null, 2));
})().catch(error => { console.error(error); process.exitCode=1; });
