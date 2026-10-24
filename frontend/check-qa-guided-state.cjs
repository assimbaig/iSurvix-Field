/* Behavioural regression checks for the real saved-task QA controller.
 * DOM rendering is stubbed; requestAnimationFrame is deliberately deferred so
 * a zeroed/new pane cannot overwrite the saved review position before restore.
 */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const filename=path.resolve(__dirname,'../backend/static/core/js/qa_evidence_review.js');
function controller(){
  const elements=new Map(),storage=new Map(),frames=[];
  const element=id=>{if(!elements.has(id))elements.set(id,{dataset:{},attributes:{},children:[],scrollTop:0,value:'linked',open:false,
    getAttribute(name){return name==='href'?'/checklist/1/':this.attributes[name]??null;},querySelector(){return element(id+':child');},querySelectorAll(){return [];},addEventListener(){},removeAttribute(){},setAttribute(name,value){this.attributes[name]=String(value);},append(...children){this.children.push(...children);},replaceChildren(...children){this.children=children;},scrollIntoView(){},
    classList:{toggle(){}},textContent:''});return elements.get(id);};
  const app=element('qa-evidence-review');app.dataset={quickReview:'true',reviewUser:'42',reviewRole:'QUALITY_ENGINEER'};
  const script=fs.readFileSync(filename,'utf8').replace('  function controls(){',`
    renderAll=()=>{el('qa-review-items').scrollTop=0;el('qa-photo-pane').querySelector('.qa-photo-pane-scroll').scrollTop=0;};
    renderSiteInformation=()=>{};copySiteSource=()=>{};initialiseGuided=()=>{};schedule=()=>{};
    globalThis.qa={applyState,setStep,remember,restorePaneScroll,renderStatus,renderInline,submitDecision,renderGuidedCategories,
      photoModeChanged:typeof photoModeChanged==='function'?photoModeChanged:null,
      prepareModeTest(){renderPhotos=()=>{};renderPointHeader=()=>{};controls=()=>{};}};return;
  function controls(){`);
  const context={document:{getElementById:element,createElement:tag=>element('created:'+tag+':'+elements.size)},location:{href:'http://localhost/local/photos/7/',pathname:'/local/photos/7/'},
    history:{replaceState(){}},URL,sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
    requestAnimationFrame:callback=>frames.push(callback),confirm:()=>true};
  vm.createContext(context);vm.runInContext(script,context,{filename});
  return{qa:context.qa,element,storage,context,flush(){while(frames.length)frames.shift()();}};
}
const data={revision_id:2,items:[],photos:[],links:[],unassigned_photo_ids:[],review_digest:'review',source_digest:'source',display_order:{},order_digest:'order'};
let checks=0;
{
  const c=controller(),key='qa-evidence-view:/local/photos/7/';
  c.storage.set(key,JSON.stringify({revision_id:2,step:'evidence',category:'Civil',scroll:{items:240,photos:380,site:95}}));
  c.qa.applyState(data,true);
  assert.equal(JSON.parse(c.storage.get(key)).scroll.items,240,'Saved checklist scroll survives until the browser restores the pane');checks++;
  assert.equal(JSON.parse(c.storage.get(key)).scroll.photos,380,'Saved photo scroll survives until the browser restores the pane');checks++;
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
  c.qa.applyState({...data,items:[{id:'civil_item',category:'Civil',section_id:'civil',section_title:'Civil section'}]},true);c.flush();c.qa.renderGuidedCategories();
  const descendants=node=>[node,...node.children.flatMap(descendants)];
  let buttons=descendants(c.element('qa-review-categories'));
  assert.equal(buttons.find(button=>button.dataset.category==='Civil').getAttribute('aria-current'),'true','The visually selected category is also identified to assistive technology');checks++;
  assert.equal(buttons.find(button=>button.dataset.category==='Electrical').getAttribute('aria-current'),'false','Other categories do not claim to be current');checks++;
  c.qa.setStep('site');c.flush();c.qa.renderGuidedCategories();buttons=descendants(c.element('qa-review-categories'));
  assert.equal(buttons.find(button=>button.dataset.category==='__site__').getAttribute('aria-current'),'true','General Info becomes the current navigation choice in the site-information step');checks++;
  assert.equal(buttons.find(button=>button.dataset.category==='Civil').getAttribute('aria-current'),'false','The prior evidence category clears its current state when leaving evidence');checks++;
}
(async()=>{
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
