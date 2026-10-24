/* Actual QA controller unit regressions; integration is verified separately. */
const assert=require('node:assert/strict');
const controller=require('./qa-controller-test-harness.cjs');
const data={revision_id:2,items:[],photos:[],links:[],unassigned_photo_ids:[],review_digest:'review',source_digest:'source',display_order:{},order_digest:'order'};
let checks=0;
{
  const c=controller(),rows=[
    {key:'general:required_blank',id:'required_blank',field_id:'required_blank',scope:'general',label:'Required blank',value:'',submitted_value:'',required:true,can_edit:true,status:'Missing'},
    {key:'context:zero',id:'zero',field_id:null,scope:'context',label:'Recorded zero',value:0,submitted_value:0},
    {key:'context:false',id:'false',field_id:null,scope:'context',label:'Recorded false',value:false,submitted_value:false}];
  c.qa.applyState({...data,can_review:true,items:[{id:'required_blank',type:'text'}],site_information_table:{rows}},true);c.flush();
  const before=JSON.stringify(c.qa.snapshot()),table=c.qa.siteInformationTable(),head=table.children[1].children[0],body=table.children[2];
  assert.equal(head.children.filter(column=>!column.hidden).length,3,'Compact default has three useful columns while source comparison remains secondary');checks++;
  assert.equal(body.children.length,rows.length,'Every required and source-only field remains in the initial table');checks++;
  assert.equal(body.children[0].dataset.siteRequired,'true','Missing required fields remain explicitly identifiable');checks++;
  assert.equal(body.children[0].dataset.siteMissing,'true','A blank required value is not disguised as complete');checks++;
  assert.equal(body.children[1].children.find(cell=>cell.dataset.siteColumn==='value').children[0].textContent,'0','Source-only zero remains visible in the compact value column');checks++;
  assert.equal(body.children[2].children.find(cell=>cell.dataset.siteColumn==='value').children[0].textContent,'false','Source-only false remains visible in the compact value column');checks++;
  assert.equal(typeof c.qa.toggleSiteComparison,'function','Source comparison is a working control');
  c.qa.toggleSiteComparison();const compared=c.qa.siteInformationTable();
  assert.equal(compared.children[1].children[0].children.filter(column=>!column.hidden).length,4,'Compare reveals the original-value column');checks++;
  assert.equal(JSON.stringify(c.qa.snapshot()),before,'Comparison never edits submitted values, review answers or evidence');checks++;
  assert.equal(JSON.parse(c.storage.get('qa-evidence-view:/local/photos/7/')).compareSources,true,'The comparison preference is saved without changing the review');checks++;
}
{
  const c=controller();
  assert.match(c.qa.photoAdvisory({analysis_reused:{revision_id:99,revision_number:2,source_id:'photo:1'}}),/Reused analysis · revision 2;/,'Reused-analysis labels use the user revision number rather than the database ID');checks++;
  assert.match(c.qa.photoAdvisory({analysis_reused:{revision_id:99,source_id:'photo:1'}}),/revision record #99/,'Older reuse metadata identifies its database record explicitly');checks++;
  c.context.innerWidth=390;c.storage.set('qa-evidence-view:/local/photos/7/',JSON.stringify({revision_id:2,step:'site',category:'',scroll:{}}));
  c.qa.applyState({...data,can_review:true,ai:{status:'failed',completed:1,total:3,error:'Complete retained failure explanation.'}},true);c.flush();
  c.element('qa-analysis-explanation').open=true;c.qa.renderStatus();
  assert.equal(c.element('qa-analysis-explanation').open,false,'The mobile site step initially keeps the full failure explanation in accessible expandable details');checks++;
  c.element('qa-analysis-explanation').open=true;c.qa.renderStatus();
  assert.equal(c.element('qa-analysis-explanation').open,true,'A later progress update does not collapse details the reviewer opened');checks++;
  assert.match(c.element('qa-analysis-detail').textContent,/Complete retained failure explanation/,'The complete failure reason remains available');checks++;
}
{
  const c=controller(),key='qa-evidence-view:/local/photos/7/';
  c.storage.set(key,JSON.stringify({revision_id:2,step:'evidence',category:'Civil',scroll:{items:240,photos:380,site:95}}));
  c.qa.applyState(data,true);
  assert.equal(JSON.parse(c.storage.get(key)).scroll.items,240,'Saved checklist scroll survives until the browser restores the pane');checks++;
  assert.equal(JSON.parse(c.storage.get(key)).scroll.photos,380,'Saved photo scroll survives until the browser restores the pane');checks++;
  c.qa.remember();
  assert.equal(JSON.parse(c.storage.get(key)).scroll.items,240,'A queued tree-toggle event cannot overwrite scroll before restoration');checks++;
  c.flush();
  assert.equal(c.element('qa-review-items').scrollTop,240,'Checklist position restores after rendering');checks++;
  assert.equal(c.element('qa-photo-pane').querySelector('.qa-photo-pane-scroll').scrollTop,380,'Photo position restores after rendering');checks++;
  assert.equal(JSON.parse(c.storage.get(key)).scroll.photos,380,'Restored position is persisted after the animation frame');checks++;
}
{
  const c=controller(),key='qa-evidence-view:/local/photos/7/';
  c.storage.set(key,JSON.stringify({revision_id:2,step:'site',category:'',scroll:{items:0,photos:0,site:195}}));
  c.qa.applyState(data,true);c.flush();
  assert.equal(c.element('qa-site-source-content').scrollTop,195,'Submitted information scroll is restored too');checks++;
}
{
  const c=controller();
  c.qa.applyState({...data,can_review:true,ai:{status:'paused',completed:50,total:100,can_resume:true,pause_message:'Paused safely; saved analyses retained.'}},true);c.flush();c.qa.renderStatus();
  assert.match(c.element('qa-analysis-numbers').textContent,/50 \/ 100.*Paused/,'Paused progress keeps its real count and clearly shows that work stopped');checks++;
  assert.equal(c.element('qa-analysis-pause').hidden,false,'Authorized QA can see the resume action');checks++;
  assert.equal(c.element('qa-analysis-pause').textContent,'Resume AI','A paused job offers resume rather than retry');checks++;
}
{
  const c=controller(),key='qa-evidence-view:/local/photos/7/';
  c.storage.set(key,JSON.stringify({revision_id:2,step:'evidence',category:'Civil',selectedID:'civil',scroll:{}}));
  c.qa.applyState({...data,items:[{id:'civil'}],photos:[{id:1,group:'Civil',filename:'one.jpg',preview_url:'/one.jpg'},{id:2,group:'Civil',filename:'two.jpg',preview_url:'/two.jpg'}],links:[{field_id:'civil',photo_id:1}]},true);c.flush();
  c.qa.prepareModeTest();c.qa.renderInline();
  assert.equal(c.element('qa-inline-position').textContent,'1 / 1','Linked mode starts with the linked photo only');checks++;
  c.element('qa-photo-view').value='available';
  assert.equal(typeof c.qa.photoModeChanged,'function','Photo-mode handler supports the primary viewer');
  c.qa.photoModeChanged();
  assert.equal(c.element('qa-inline-position').textContent,'1 / 2','Available mode updates the inline viewer to all category photos');checks++;
  assert.equal(c.element('qa-inline-next').disabled,false,'Next photo becomes available immediately');checks++;
}
{
  const c=controller(),key='qa-evidence-view:/local/photos/7/';
  c.storage.set(key,JSON.stringify({revision_id:2,step:'evidence',category:'Civil',section:'civil',scroll:{}}));
  c.qa.applyState({...data,can_review:true,items:[{id:'civil_item',category:'Civil',section_id:'civil',section_title:'Civil section'}]},true);c.flush();c.qa.renderGuidedCategories();
  const descendants=node=>[node,...node.children.flatMap(descendants)];
  let buttons=descendants(c.element('qa-review-categories'));
  assert.equal(buttons.find(button=>button.dataset.category==='Civil').getAttribute('aria-current'),'true','The visually selected category is also identified to assistive technology');checks++;
  assert.equal(buttons.find(button=>button.dataset.category==='Electrical').getAttribute('aria-current'),'false','Other categories do not claim to be current');checks++;
  assert.ok(buttons.some(button=>button.dataset.reviewField==='civil_item'),'The category tree includes its checklist points within the same left pane');checks++;
  assert.equal(buttons.find(button=>button.dataset.dragPoint==='civil_item').children[1].hidden,true,'Rebuilding an expanded group keeps reorder controls secondary until explicitly enabled');checks++;
  c.qa.setStep('site');c.flush();c.qa.renderGuidedCategories();buttons=descendants(c.element('qa-review-categories'));
  assert.equal(buttons.find(button=>button.dataset.category==='__site__').getAttribute('aria-current'),'true','General Info becomes the current navigation choice in the site-information step');checks++;
  assert.equal(buttons.find(button=>button.dataset.category==='Civil').getAttribute('aria-current'),'false','The prior evidence category clears its current state when leaving evidence');checks++;
}
{
  const c=controller(),rows=[{id:'project',scope:'context',field_id:null,submitted_value:'Preserved project'},
    {id:'identity',scope:'general',field_id:'site_id',system:'site_id',submitted_value:'SYNTHETIC-123'},
    {id:'address',scope:'site',field_id:null,submitted_value:'Original address'},
    {id:'contact',scope:'general',field_id:'site_contact',can_edit:true,submitted_value:'Original contact'},
    {id:'locked',scope:'general',field_id:'approved_note',can_edit:false,submitted_value:'Approved source'}];
  c.qa.applyState({...data,site_information_table:{rows}},true);c.flush();
  assert.deepEqual(Array.from(c.qa.siteRows(),row=>row.id),['identity','contact','locked','project','address'],'The same table leads with stable QA fields in their original order, then all immutable facts');checks++;
  assert.equal(c.qa.siteRows()[1].submitted_value,'Original contact','Presentation ordering preserves frozen cell values');checks++;
  assert.deepEqual(Array.from(c.qa.snapshot().site_information_table.rows,row=>row.id),['project','identity','address','contact','locked'],'The server data and approved checklist ordering are never mutated');checks++;
}
{
  const c=controller();c.qa.applyState({...data,can_review:true,items:[{id:'site_contact',type:'text'},{id:'site_id',type:'text',system:'site_id'},{id:'approved_note',type:'text',locked:true}]},true);c.flush();
  assert.equal(typeof c.qa.siteCellEditable,'function','Per-cell edit guards are available');
  assert.equal(c.qa.siteCellEditable({field_id:'site_contact',can_edit:true}),true,'An unlocked derived QA field can be explicitly edited');checks++;
  assert.equal(c.qa.siteCellEditable({scope:'context',id:'project',can_edit:true}),false,'Source-only system facts cannot acquire an editor');checks++;
  assert.equal(c.qa.siteCellEditable({field_id:'site_id',can_edit:true}),false,'The immutable Site ID never becomes an editable value');checks++;
  assert.equal(c.qa.siteCellEditable({field_id:'approved_note',can_edit:true}),false,'Approved field locks remain effective even with a stale edit flag');checks++;
}
{
  const c=controller(),key='qa-evidence-view:/local/photos/7/';c.storage.set(key,JSON.stringify({revision_id:2,step:'evidence',category:'Civil',selectedID:'civil_point',scroll:{}}));
  c.qa.applyState({...data,items:[{id:'site_id',label:'Site ID',category:''},{id:'civil_point',label:'Civil condition',category:'Civil'},{id:'tower_point',label:'Tower condition',category:'Tower'}]},true);c.flush();
  c.element('qa-assignment-target').value='site_id';c.qa.renderAssignmentTargets();
  assert.equal(c.element('qa-assignment-target').value,'civil_point','The assignment destination defaults to the selected checklist point, not the first field');checks++;
  c.element('qa-assignment-target').value='site_id';c.qa.renderAssignmentTargets();
  assert.equal(c.element('qa-assignment-target').value,'site_id','An explicit destination is kept while reviewing the same selected point');checks++;
  c.qa.chooseItem('tower_point');c.qa.renderAssignmentTargets();
  assert.equal(c.element('qa-assignment-target').value,'tower_point','Selecting another checklist point resets the default destination safely');checks++;
}
{
  const c=controller();c.qa.applyState({...data,progress_token:'same-inputs',can_review:true,ai:{status:'analysing_evidence',completed:0,total:2},photos:[{id:1},{id:2}],items:[{id:'human_answer',value:'Human correction',accepted:true}],links:[{photo_id:1,field_id:'human_answer',state:'qa_confirmed'}]},true);c.flush();
  assert.equal(typeof c.qa.applyProgressTick,'function','Lightweight progress ticks are handled separately from the full evidence payload');
  const links=JSON.stringify(c.qa.snapshot().links),items=JSON.stringify(c.qa.snapshot().items);
  assert.equal(c.qa.applyProgressTick({revision_id:2,progress_token:'same-inputs',ai:{status:'analysing_evidence',completed:1,total:2},photo:{id:2,observations:[{value:0,unit:'V'}]}}),true,'A completed-photo tick can be merged without rebuilding checklist history');checks++;
  assert.equal(c.qa.snapshot().ai.completed,1,'Numerical AI progress advances from the actual saved count');checks++;
  assert.equal(JSON.stringify(c.qa.snapshot().links),links,'A progress tick never replaces human-confirmed evidence');checks++;
  assert.equal(JSON.stringify(c.qa.snapshot().items),items,'A progress tick never replaces accepted answers');checks++;
  assert.equal(c.qa.snapshot().photos[1].observations[0].value,0,'Selected-photo observations preserve real zero values');checks++;
  assert.equal(c.qa.applyProgressTick({revision_id:2,progress_token:'changed-review',ai:{completed:2,total:2}}),false,'Changed review tokens require the actual saved details to reload');checks++;
}
(async()=>{
  {
    const c=controller();c.qa.applyState({...data,progress_token:'stable',can_review:true,ai:{status:'queued',completed:0,total:2}},true);c.flush();c.qa.prepareModeTest();
    c.element('qa-evidence-review').dataset.progressUrl='/progress/';let attempts=0;
    c.context.fetch=async()=>{if(!attempts++)throw new Error('Temporary progress disconnection');return{ok:true,json:async()=>({revision_id:2,progress_token:'stable',ai:{status:'queued',completed:1,total:2}})};};
    await assert.rejects(c.qa.fetchProgress(),/Temporary progress disconnection/);
    assert.match(c.element('qa-review-message').textContent,/Temporary progress disconnection/,'A failed progress request shows an honest connection error');checks++;
    await c.qa.fetchProgress();
    assert.doesNotMatch(c.element('qa-review-message').textContent,/Temporary progress disconnection/,'Recovered progress does not leave a misleading old connection failure');checks++;
  }
  const c=controller();c.qa.prepareModeTest();
  let requested;
  c.context.FormData=class{set(){}};
  c.context.fetch=async(url)=>{requested=url;return{ok:false,json:async()=>({ok:false,error:'Controlled save failure; note retained.'})};};
  // Browser forms expose same-name controls as properties. The action buttons
  // deliberately shadow form.action, as a real RadioNodeList does in Chromium.
  const form={action:{length:2},getAttribute:name=>name==='action'?'/work/review-routes/7/action/':null,matches:()=>true,checkValidity:()=>true,querySelectorAll:()=>[]};
  await c.qa.submitDecision({target:form,preventDefault(){},submitter:{name:'action',value:'approve'}});
  assert.equal(requested,'/work/review-routes/7/action/','Decision POST uses the form URL even when action buttons shadow its property');checks++;
  assert.match(c.element('qa-decision-error').textContent,/Controlled save failure/,'The backend error remains visible without discarding the note');checks++;
  console.log(JSON.stringify({suite:'QA guided-state unit regressions',checks,passed:checks}));
})().catch(error=>{console.error(error);process.exitCode=1;});
