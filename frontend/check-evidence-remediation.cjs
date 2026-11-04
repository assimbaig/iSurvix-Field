/* Exercise the production viewer controller; absent raster URLs must not mask
 * an authorized image URL or turn an unavailable preview into a page fetch. */
const assert=require('node:assert/strict');
const controller=require('./qa-controller-test-harness.cjs');

async function imagePreview(raster){
  const c=controller(),requests=[];
  c.context.fetch=async url=>{
    requests.push(String(url));
    return {ok:true,headers:{get:name=>name==='content-type'?'image/png':null},
      blob:async()=>new Blob(['synthetic retained preview'],{type:'image/png'})};
  };
  await c.qa.openDocumentPreview({id:1,filename:'Synthetic sketch.png',
    preview_url:'http://localhost/submitted/1/?revision_id=3&preview=1',
    original_url:'http://localhost/submitted/1/?revision_id=3',
    ...(raster==='absent'?{}:{raster_preview_url:raster})});
  assert.deepEqual(requests,['http://localhost/submitted/1/?revision_id=3&preview=1']);
  assert.equal(c.element('qa-document-preview-image').hidden,false);
  assert.equal(c.element('qa-document-preview-frame').hidden,true);
}

(async()=>{
  for(const raster of ['absent',null,'','   ',false,0,'https://foreign.example.test/preview/']){
    await imagePreview(raster);
  }
  const c=controller(),requests=[];
  c.context.fetch=async url=>{requests.push(String(url));throw new Error('Must not fetch absent previews');};
  await c.qa.openDocumentPreview({id:2,filename:'Unavailable sketch.png'});
  assert.deepEqual(requests,[]);
  assert.match(c.element('qa-document-preview-status').textContent,/preview.*unavailable/i);
  console.log('PASS: real document controller uses the authorized image fallback and never fetches absent/foreign URLs.');
})().catch(error=>{console.error(error);process.exitCode=1;});
