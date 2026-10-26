const assert=require('node:assert/strict'),controller=require('./qa-controller-test-harness.cjs');
const state={revision_id:2,source_digest:'source',review_digest:'review',order_digest:'order',can_review:true,
 items:[{id:'civil',label:'Foundation',category:'Civil',section_id:'c'}],
 photos:[{id:1,group:'Civil',filename:'confirmed.jpg'},{id:2,group:'Civil',filename:'unassigned.jpg'},{id:3,group:'Civil',filename:'suggested.jpg'}],
 links:[{photo_id:1,field_id:'civil',state:'qa_confirmed'},{photo_id:3,field_id:'civil',state:'ai_suggested'}],
 unassigned_photo_ids:[2],general_information:{fields:[]},site_information_table:{rows:[]},display_order:{}};
const checks=[];
function check(label,run){try{run();checks.push({label,passed:true});}catch(e){checks.push({label,passed:false,error:e.message});process.exitCode=1;}}
function reload(c){const restored=controller();for(const [key,value] of c.storage)restored.storage.set(key,value);restored.qa.applyState(state,true);restored.qa.initialiseGuidedForTest();return restored;}
for(const collection of ['unassigned','suggestions'])check(`${collection} collection survives refresh without selecting a checkpoint`,()=>{
 const c=controller();c.qa.applyState(state);c.qa.chooseCategory('Civil');c.qa.chooseCollection(collection);
 const before=Array.from(c.qa.visiblePhotos(),p=>p.id),restored=reload(c);
 assert.deepEqual(Array.from(restored.qa.visiblePhotos(),p=>p.id),before);
 assert.equal(restored.qa.navigationSnapshot().selectedID,null);
});
check('A selected checkpoint remains selected after refresh',()=>{const c=controller();c.qa.applyState(state);c.qa.chooseCategory('Civil');c.qa.chooseItem('civil');assert.equal(reload(c).qa.navigationSnapshot().selectedID,'civil');});
check('Category overview still restores its complete evidence gallery',()=>{const c=controller();c.qa.applyState(state);c.qa.chooseCategory('Civil');assert.deepEqual(Array.from(reload(c).qa.visiblePhotos(),p=>p.id),Array.from(c.qa.visiblePhotos(),p=>p.id));});
console.log(JSON.stringify({suite:'QA collection refresh persistence',passed:checks.filter(c=>c.passed).length,total:checks.length,checks},null,2));
