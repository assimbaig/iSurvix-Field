/* Behaviour tests for bounded history in the real photo workspace controller. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
function harness(){
  const elements=new Map();
  const el=id=>{if(!elements.has(id))elements.set(id,{id,dataset:{},value:'',textContent:'',hidden:false,disabled:false,children:[],append(...rows){this.children.push(...rows);},replaceChildren(...rows){this.children=rows;}});return elements.get(id);};
  el('photo-app').querySelector=()=>({value:'synthetic-csrf'});
  const filename=path.resolve(__dirname,'../backend/static/core/js/photo_workspace.js');
  const script=fs.readFileSync(filename,'utf8').replace("  el('photo-upload').onsubmit = async event => {",`
    render=()=>{if(typeof renderHistoryControls==='function')renderHistoryControls();};
    globalThis.probe={
      loadHistory:typeof loadHistory==='function'?loadHistory:null,
      refresh,snapshot:()=>state,
      seed(value){state=value;render();},
      visiblePhoto:()=>current,
      selectPhoto(id){current=id;},
      published:()=>typeof publishedState==='function'?publishedState():state,
      renderProcessingStage:typeof renderProcessingStage==='function'?renderProcessingStage:null,
      shouldPoll:typeof shouldPoll==='function'?shouldPoll:null,
    };return;
  el('photo-upload').onsubmit = async event => {`);
  const context={document:{getElementById:el,hidden:false,createElement:tag=>el(tag+elements.size)},
    window:{location:{pathname:'/local/photos/7/'}},URL,console};
  vm.createContext(context);vm.runInContext(script,context,{filename});
  return {el,context,probe:context.probe};
}
const first=()=>({photos:[{id:9}],analysis:{active_job_count:1},jobs:[{id:3,status:'running'}],drafts:[{id:8,status:'pending'}],
  history:{page_size:50,jobs:{total:3,has_more:true,next_cursor:'0:3'},drafts:{total:2,has_more:true,next_cursor:'0:8'}}});
const reply=data=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>data});
(async()=>{
  const h=harness();assert.equal(typeof h.probe.loadHistory,'function','The real workspace needs a working history loader');
  h.probe.seed(first());h.probe.selectPhoto(9);
  const requests=[];h.context.fetch=async(url,options)=>{requests.push({url,options});return reply({jobs:[{id:2,status:'completed'},{id:1,status:'completed'}],history:{jobs:{total:3,has_more:false,next_cursor:null}}});};
  await h.probe.loadHistory('jobs');
  assert.deepEqual(requests.map(r=>r.url),['/local/photos/7/state/?history=jobs&cursor=0%3A3']);
  assert.equal(requests[0].options.credentials,'same-origin');
  assert.deepEqual(Array.from(h.probe.snapshot().jobs,row=>row.id),[3,2,1]);
  assert.equal(h.probe.visiblePhoto(),9);
  assert.equal(h.el('photo-jobs-more').hidden,true);
  assert.match(h.el('photo-jobs-history-status').textContent,/3 of 3/);

  const failed=harness();failed.probe.seed(first());const before=JSON.stringify(failed.probe.snapshot());
  failed.context.fetch=async()=>{throw new Error('Synthetic disconnected request');};
  await failed.probe.loadHistory('drafts');
  assert.equal(JSON.stringify(failed.probe.snapshot()),before,'Failure must not advance the cursor or lose proposals');
  assert.equal(failed.el('photo-drafts-more').disabled,false);
  assert.equal(failed.el('photo-drafts-more').hidden,false);
  assert.match(failed.el('photo-drafts-history-status').textContent,/could not.*loaded.*retry/i);
  failed.context.fetch=async()=>reply({drafts:[{id:8,status:'accepted'},{id:7,status:'accepted'}],history:{drafts:{total:2,has_more:false,next_cursor:null}}});
  await failed.probe.loadHistory('drafts');
  assert.deepEqual(Array.from(failed.probe.snapshot().drafts,row=>row.id),[8,7],'Overlapping deliveries must not duplicate a proposal');
  assert.equal(failed.probe.snapshot().drafts[0].status,'accepted','A newer delivery must update the saved status rather than retaining an obsolete pending action');

  h.context.fetch=async()=>reply({...first(),jobs:[{id:3,status:'completed'}]});
  await h.probe.refresh({preserveHistory:true});
  assert.deepEqual(Array.from(h.probe.snapshot().jobs,row=>row.id),[3,2,1]);
  assert.equal(h.probe.snapshot().jobs[0].status,'completed');
  assert.equal(h.probe.visiblePhoto(),9);
  await h.probe.refresh();
  assert.deepEqual(Array.from(h.probe.snapshot().jobs,row=>row.id),[3],'Explicit refresh starts a fresh bounded history snapshot');
  const finished=harness();
  finished.probe.seed({...first(),jobs:[{id:1,status:'running',progress:{stage:'extracting_metadata'}}]});
  finished.probe.selectPhoto(9);
  finished.context.fetch=async()=>reply({jobs:[{id:3,status:'completed'},{id:2,status:'completed'}],
    history:{jobs:{total:3,has_more:false,next_cursor:null}}});
  await finished.probe.loadHistory('jobs');
  finished.context.fetch=async()=>reply({...first(),analysis:{active_job_count:0,active_job:null,review_ready:true},
    jobs:[{id:3,status:'completed'},{id:2,status:'completed'}]});
  await finished.probe.refresh({preserveHistory:true});
  assert.equal(finished.probe.snapshot().jobs.find(row=>row.id===1)._history_snapshot,true,
    'An older running row missing from the fresh page must be labelled a saved snapshot');
  assert.deepEqual(Array.from(finished.probe.published().jobs,row=>row.id),[3,2],
    'Other progress widgets must receive fresh jobs, not retained running snapshots');
  assert.equal(finished.probe.shouldPoll(),false,'A fresh zero active count must stop polling');
  finished.probe.renderProcessingStage();
  assert.equal(finished.el('photo-processing-stages').dataset.stage,'completed');
  assert.equal(finished.probe.visiblePhoto(),9);
  console.log('PASS: real history loader follows scoped cursors, retains data on failure, deduplicates and preserves background review context.');
})().catch(error=>{console.error(error);process.exitCode=1;});
