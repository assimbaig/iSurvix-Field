const assert=require('node:assert/strict'),controller=require('./qa-controller-test-harness.cjs');
const state={revision_id:2,template_id:4,items:[{id:'a',label:'Concrete foundation',type:'photo'},{id:'b',label:'Other valid point',type:'photo'}],photos:[{id:1},{id:2},{id:3}],links:[{photo_id:1,field_id:'a',state:'qa_confirmed'},{photo_id:1,field_id:'b',state:'qa_confirmed'},{photo_id:2,field_id:'a',state:'ai_suggested'}],unassigned_photo_ids:[3],review_digest:'review1',source_digest:'source',display_order:{},order_digest:'order',can_review:true};
function make({permission=true,locked=false}={}){const c=controller();c.qa.applyState({...structuredClone(state),can_review:permission,items:state.items.map(item=>({...item,locked:locked&&item.id==='a'}))},true);c.flush();c.element('qa-assignment-target').value='a';c.qa.setSelection([1,2,3]);return c;}
function patch(links,ids=[1,2],digest='review2'){return{response_mode:'link_patch',revision_id:2,source_digest:'source',template_id:4,review_digest:digest,links_patch:{photo_ids:ids,field_ids:['a'],links},items:[],unassigned_photo_ids:[2,3],can_complete:false};}
(async()=>{
 const c=make(),sent=[],confirmations=[];
 assert.equal(typeof c.qa.unlinkSelected,'function','Selected photos need a direct unlink action');
 c.context.confirm=text=>{confirmations.push(text);return true;};
 c.qa.prepareBatchTest(async data=>{sent.push(data);return patch([{photo_id:1,field_id:'b',state:'qa_confirmed'}]);});
 c.qa.changed();
 assert.equal(await c.qa.unlinkSelected(),true);
 assert.equal(sent.length,1);assert.equal(sent[0].operation,'unlink');assert.deepEqual(Array.from(sent[0].photo_ids),[1,2]);assert.deepEqual(Array.from(sent[0].field_ids),['a']);
 assert.match(confirmations[0],/2.*"Concrete foundation"\?/);assert.match(confirmations[0],/other.*links.*original/i);
 assert.deepEqual(Array.from(c.qa.snapshot().links,l=>l.field_id),['b'],'Another valid link is preserved');
 assert.deepEqual(Array.from(c.qa.selectionIds()),['1','2','3'],'Unlink retains selections and does not touch unlinked photos');
 assert.equal(await c.qa.unlinkSelected(),false);assert.equal(sent.length,1,'Repeated unlink must not post an already absent association');
 const single=make();single.qa.setSelection([1]);const one=[];single.qa.prepareBatchTest(async data=>{one.push(data);return patch([{photo_id:1,field_id:'b',state:'qa_confirmed'}],[1]);});await single.qa.unlinkSelected();assert.deepEqual(Array.from(one[0].photo_ids),[1]);
 const cancel=make(),cancelSent=[];cancel.context.confirm=()=>false;cancel.qa.prepareBatchTest(async data=>cancelSent.push(data));assert.equal(await cancel.qa.unlinkSelected(),false);assert.equal(cancelSent.length,0);
 for(const options of [{permission:false},{locked:true}]){const denied=make(options);denied.qa.prepareBatchTest(async()=>{throw Error('Must not send');});assert.equal(await denied.qa.unlinkSelected(),false);}
 const failure=make(),before=JSON.stringify(failure.qa.snapshot());failure.qa.prepareBatchTest(async()=>{throw new Error('Temporary save failure');});assert.equal(await failure.qa.unlinkSelected(),false);assert.equal(JSON.stringify(failure.qa.snapshot()),before);assert.deepEqual(Array.from(failure.qa.selectionIds()),['1','2','3']);
 const duplicate=make(),linkSent=[];duplicate.qa.prepareBatchTest(async data=>{linkSent.push(data);return patch([{photo_id:1,field_id:'a',state:'qa_confirmed'},{photo_id:1,field_id:'b',state:'qa_confirmed'},{photo_id:2,field_id:'a',state:'qa_confirmed'}],[1,2]);});
 assert.equal(await duplicate.qa.confirmLinks([1,2],'a'),true);assert.deepEqual(Array.from(linkSent[0].photo_ids),[2],'Already confirmed pairs are excluded, while AI-suggested pairs still require confirmation');
 assert.equal(await duplicate.qa.confirmLinks([1,2],'a'),false);assert.equal(linkSent.length,1,'Repeated linking is a no-op, not another POST');assert.match(duplicate.element('qa-review-message').textContent,/Already linked/);
 assert.ok(duplicate.qa.snapshot().links.some(l=>l.photo_id===1&&l.field_id==='b'),'Duplicate suppression never removes other valid links');
 const current=make(),currentSent=[];current.qa.prepareBatchTest(async data=>{currentSent.push(data);return patch([{photo_id:1,field_id:'a',state:'qa_confirmed'}],[1]);});current.qa.chooseItem('b');current.element('qa-assignment-target').value='a';current.qa.setSelection([1]);await current.qa.unlinkSelected();assert.deepEqual(Array.from(currentSent[0].field_ids),['b'],'A selected checklist point is the explicit unlink source even if a different link destination is chosen');
 const concurrent=make(),concurrentSent=[];let finish;concurrent.qa.prepareBatchTest(data=>{concurrentSent.push(data);return new Promise(resolve=>finish=resolve);});const first=concurrent.qa.confirmLinks([3],'a');assert.equal(await concurrent.qa.confirmLinks([3],'a'),false,'A second click while saving cannot create another request');finish(patch([{photo_id:3,field_id:'a',state:'qa_confirmed'}],[3]));assert.equal(await first,true);assert.equal(concurrentSent.length,1);
 console.log('QA bulk unlink and duplicate-link behavior:12 scenarios passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
