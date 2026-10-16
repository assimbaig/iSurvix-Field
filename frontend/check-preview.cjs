const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
const element=id=>{if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',style:{},classList:{add(){},remove(){},toggle(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false},click(){},focus(){},setSelectionRange(){}});return elements.get(id)};
const storage=new Map();
const context={console,Blob,URL,Date,crypto:require('node:crypto').webcrypto,FileReader:class{},setTimeout,clearTimeout,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},document:{getElementById:element,addEventListener(){},querySelector:()=>null,activeElement:null,createElement:()=>({click(){}})},window:{scrollTo(){},open(){return null}}};
vm.createContext(context);for(const p of ['dist/assets/checklist-defaults.js','dist/assets/app.js','dist/assets/builder-preview.js'])vm.runInContext(fs.readFileSync(p,'utf8'),context);
const run=s=>vm.runInContext(s,context);let screens=0;
for(const role of ['Team leader','Engineer','Admin'])for(const view of ['overview','sites','map','review','photos','reports','projects','team','settings','workspace','website','builder']){run(`role=${JSON.stringify(role)};view=${JSON.stringify(view)};render()`);assert.ok(element('app').innerHTML.length>600);assert.ok(!element('app').innerHTML.includes('undefined'));screens++}
for(const section of ['general','civil','electrical','power','equipment','evidence','submission']){run(`view='workspace';section=${JSON.stringify(section)};render()`);assert.ok(element('app').innerHTML.includes('SITE CHECKLIST'));screens++}
run("role='Engineer';selected=data.sites[0].id;saveField('generalNotes','First field');saveField('civilNotes','Second field')");
let stored=JSON.parse(storage.get('isurvix-redesign-v1'));
assert.equal(stored.sites[0].answers.generalNotes,'First field');assert.equal(stored.sites[0].answers.civilNotes,'Second field');
run("addEquipment();saveEquipment(site().equipment.length-1,'model','Temporary test equipment');removeEquipment(site().equipment.length-1)");
assert.ok(!storage.get('isurvix-redesign-v1').includes('Temporary test equipment'));
run("selected=data.sites.find(s=>s.status==='Approved').id");let before=run("JSON.stringify(site().answers)");run("saveField('generalNotes','Forbidden edit')");assert.equal(run("JSON.stringify(site().answers)"),before);
run("selected=data.sites[0].id;Object.keys(site().checks).forEach(k=>site().checks[k]=true);site().photos.push({name:'fixture.png',src:'data:image/png;base64,fixture',category:'General'});submitSite()");assert.equal(run('site().status'),'Awaiting review');
run("role='Team leader';reviewSite(selected,'approve')");element('review-comment').value='Fixture approval';element('review-action').value='approve';run('commitReview()');assert.equal(run('site().status'),'Approved');
for(const p of ['dist/assets/builder-preview.js','dist/assets/checklist-defaults.js','dist/index.html','dist/assets/style.css','dist/assets/app.js','dist/assets/logo.png','dist/assets/towers.jpg'])assert.ok(fs.statSync(p).size>0);
// Test admin design changes against a live survey revision.
assert.equal(run('fixedCount(data.templates[0])'),172);
run("role='Admin';view='builder';newChecklistTemplate(false)");
assert.equal(run('fixedCount(currentTemplate())'),172);
run('confirmRemoveBuilderField(1)');
assert.equal(run('fixedCount(currentTemplate())'),171);
element('section-title').value='Custom client section';element('section-group').value='Custom group';run('commitBuilderSection(true)');
element('field-label').value='Custom cable type';element('field-type').value='select';element('field-unit').value='';element('field-required').checked=true;element('field-options').value='Copper\nAluminium';element('field-columns').value='';run('commitBuilderField(-1)');
assert.equal(run('currentTemplate().definition.sections.at(-1).fields[0].type'),'select');
run("changeClientName(0,'Custom client A');publishTemplate();assignChecklistTemplate('Telecom survey');tryTemplate()");
const originalSurvey=run('JSON.stringify(site().templateSnapshot)');
assert.ok(originalSurvey.includes('Custom client A'));
assert.ok(run('customMissing(site()).length')>0);
const customRecordId=run('site().id');
run("view='builder';duplicateChecklistTemplate();changeClientName(0,'Changed future client');builderSection=0;confirmRemoveBuilderField(1);publishTemplate();assignChecklistTemplate('Telecom survey')");
assert.equal(run('JSON.stringify(data.sites.find(s=>s.id==='+JSON.stringify(customRecordId)+').templateSnapshot)'),originalSurvey);
run('tryTemplate()');assert.equal(run('site().templateSnapshot.clients[0].name'),'Changed future client');
const templateSectionCount=run('site().templateSnapshot.definition.sections.length');
for(let i=0;i<=templateSectionCount;i++){run('customSection='+i+";view='workspace';render()");assert.ok(element('app').innerHTML.includes('Checklist')||element('app').innerHTML.includes('CHECKLIST'));screens++}
const draftName=run('currentTemplate().name');run("role='Engineer';changeTemplateName('Unauthorized change')");assert.equal(run('currentTemplate().name'),draftName);

const css=fs.readFileSync('dist/assets/style.css','utf8');assert.ok(css.includes('@media(max-width:760px)'));assert.ok(css.includes('@media print'));assert.ok(css.includes('prefers-reduced-motion'));
console.log(JSON.stringify({rendered_screens:screens,checks:['all roles and views render','all checklist sections render','rapid field changes both persist','equipment removal persists','approved answers stay locked','required submission transitions','review comment and approval transition','asset presence','mobile and print stylesheet rules','full 172-row FDED copy','add and remove fields and sections','custom dropdown and required field','editable client branding','publish and assign revision','existing survey schema and logos frozen','future survey uses new revision','admin-only template changes'],browser_layout_QA:false},null,2));
