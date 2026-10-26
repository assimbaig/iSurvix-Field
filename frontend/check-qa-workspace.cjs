const assert=require('node:assert/strict'),controller=require('./qa-controller-test-harness.cjs');
const checks=[];
function verify(label,assertion){try{assertion();checks.push({label,passed:true});}catch(error){checks.push({label,passed:false,error:error.message});process.exitCode=1;}}
const data={revision_id:2,items:[{id:'review_point',type:'text',label:'Actual checklist point',reason:'No supported answer was extracted.'}],photos:[],links:[],unassigned_photo_ids:[],review_digest:'review',source_digest:'source',display_order:{},order_digest:'order',can_review:true};
function selected(){const c=controller();c.storage.set('qa-evidence-view:/local/photos/7/',JSON.stringify({revision_id:2,step:'evidence',category:'Civil',selectedID:'review_point',scroll:{}}));c.qa.applyState(data,true);c.flush();return c;}
const allText=node=>[node.textContent||'',...(node.children||[]).map(allText)].join(' ');
const findNode=(node,predicate)=>predicate(node)?node:(node.children||[]).map(child=>findNode(child,predicate)).find(Boolean);
(async()=>{
  const optional=selected();optional.element('qa-review-reason').value='';const optionalProbe=optional.qa.saveProbe();await optional.qa.saveAnswer(true);
  verify('Ordinary point save permits empty optional reviewer remarks',()=>assert.equal(optionalProbe.advances(),1));
  const live=selected(),livePhoto={id:91,filename:'original.png',display_name:'SITE_Breaker.png',original_filename:'camera-original.png',photo_match:{status:'unmatched',candidates:[]},observations:[{value:0,unit:'V'}]};live.qa.applyState({...data,photos:[livePhoto]});live.qa.openPreview(91);
  verify('Opening the real viewer renders immediate analysis and original-file provenance',()=>{assert.match(allText(live.element('qa-preview-analysis')),/0 V/);assert.match(allText(live.element('qa-preview-original-filename')),/camera-original/);assert.equal(live.element('qa-preview-title').textContent,'SITE_Breaker.png');});
  live.element('qa-preview-image').hidden=true;live.element('qa-preview-error').hidden=false;live.qa.renderPreview();
  verify('Refreshing analysis preserves a failed source-image error until its image URL changes',()=>{assert.equal(live.element('qa-preview-image').hidden,true);assert.equal(live.element('qa-preview-error').hidden,false);});
  const matching=selected(),rankedPhoto={id:17,filename:'original-surveyor-017.png',group:'Civil',photo_match:{status:'proposed',display_name:'SITE_000017_Breaker.png',candidates:[{field_id:'review_point',label:'Breaker condition',section:'Distribution board',category:'Electrical',rank:1,reason:'The recorded breaker and its label support this approved point.',score:1.12,score_kind:'relative_support'}]}};
  matching.qa.applyState({...data,photos:[rankedPhoto],items:[{...data.items[0],category:'Electrical'}]});
  verify('A QA display name never hides or changes the uploaded original filename',()=>{
    assert.equal(typeof matching.qa.photoDisplayName,'function');assert.equal(matching.qa.photoDisplayName(rankedPhoto),'SITE_000017_Breaker.png');assert.equal(matching.qa.photoDisplayName({filename:'original.png'}),'original.png');assert.equal(rankedPhoto.filename,'original-surveyor-017.png');
  });
  verify('The photo details show actual ranked support, its reason and original filename without probability percentages',()=>{
    assert.equal(typeof matching.qa.renderPhotoMatch,'function');matching.qa.renderPhotoMatch(rankedPhoto);const text=allText(matching.element('qa-preview-match-candidates'))+' '+allText(matching.element('qa-preview-match-summary'));
    assert.match(text,/Breaker condition/);assert.match(text,/recorded breaker/);assert.match(text,/1\.120/);assert.doesNotMatch(text,/%/);assert.match(allText(matching.element('qa-preview-original-filename')),/original-surveyor-017\.png/);
  });
  verify('An unmatched photo stays honestly unmatched rather than receiving an invented checklist candidate',()=>{
    assert.equal(typeof matching.qa.renderPhotoMatch,'function');matching.qa.renderPhotoMatch({...rankedPhoto,photo_match:{status:'unmatched',display_name:'SITE_000017_Unmatched.png',candidates:[]}});assert.match(allText(matching.element('qa-preview-match-summary')),/No supported checklist match/i);assert.equal(matching.element('qa-preview-match-candidates').children.length,0);
  });
  verify('Extracted zero values, measurement units and source quotes remain beside the selected photo',()=>{
    assert.equal(typeof matching.qa.renderPhotoObservations,'function');matching.qa.renderPhotoObservations(rankedPhoto,[{component:'Breaker reading',value:0,unit:'V',evidence_quote:'Meter display 0 V',confidence:'high'}]);const text=allText(matching.element('qa-preview-analysis'));assert.match(text,/0 V/);assert.match(text,/Meter display 0 V/);
  });
  verify('Pending and failed matching remain distinct from a supported match',()=>{
    assert.equal(typeof matching.qa.renderPhotoMatch,'function');matching.qa.renderPhotoMatch({...rankedPhoto,photo_match:{status:'pending',candidates:[]}});assert.match(allText(matching.element('qa-preview-match-summary')),/pending/i);
    matching.qa.renderPhotoMatch({...rankedPhoto,photo_match:{status:'failed',candidates:[]}});assert.match(allText(matching.element('qa-preview-match-summary')),/did not finish|failed/i);
  });
  verify('The real viewer keeps QA-only matching and extracted analysis hidden from Team Lead',()=>{const lead=controller({role:'TEAM_LEAD'});lead.qa.applyState({...data,can_review:false,photos:[livePhoto]});lead.qa.openPreview(91);assert.equal(lead.element('qa-preview-match-panel').hidden,true);assert.equal(lead.element('qa-preview-analysis').parentElement.hidden,true);});
  verify('Lightweight photo progress refreshes ranked matches and names only for its source revision',()=>{const progress=selected();progress.qa.applyState({...data,progress_token:'token',photos:[livePhoto]});assert.equal(progress.qa.applyProgressTick({revision_id:2,progress_token:'token',ai:{status:'running',completed:1,total:2},photo:{id:91,observations:[],display_name:'Updated.png',original_filename:'retained.png',photo_match:{status:'failed',candidates:[]}}}),true);assert.equal(progress.qa.snapshot().photos[0].display_name,'Updated.png');assert.equal(progress.qa.snapshot().photos[0].photo_match.status,'failed');assert.equal(progress.qa.applyProgressTick({revision_id:3,progress_token:'token',photo:{id:91,display_name:'wrong.png'}}),false);assert.equal(progress.qa.snapshot().photos[0].display_name,'Updated.png');});
  if(typeof matching.qa.renderPhotoMatch==='function'){
    const prior={photo_id:17,field_id:'other_point',state:'qa_confirmed'},reviewData={...data,photos:[rankedPhoto],items:[{...data.items[0],accepted:false},{id:'other_point',type:'photo',accepted:false}],links:[prior]},requests=[];
    matching.qa.applyState(reviewData);matching.qa.prepareModeTest();matching.context.fetch=async(url,options)=>{requests.push(JSON.parse(options.body));return{ok:true,json:async()=>({...reviewData,links:[prior,{photo_id:17,field_id:'review_point',state:'qa_confirmed'}]})};};matching.qa.renderPhotoMatch(rankedPhoto);
    const button=findNode(matching.element('qa-preview-match-candidates'),node=>node.dataset?.confirmCandidate==='review_point');
    if(button?.listeners?.click)try{await button.listeners.click();}catch(error){verify('Candidate confirmation completes without throwing',()=>assert.fail(error.message));}
    verify('Confirming a candidate uses the existing guarded link action and preserves other links and engineering decisions',()=>{
      assert.equal(requests.length,1);assert.equal(requests[0].action,'confirm_link');assert.equal(requests[0].photo_id,17);assert.equal(requests[0].field_id,'review_point');assert.equal(requests[0].revision_id,2);assert.equal(requests[0].source_digest,'source');assert.equal(requests[0].expected_review_digest,'review');assert.equal(matching.qa.snapshot().links.length,2);assert.equal(matching.qa.snapshot().items[0].accepted,false);
    });
    matching.qa.applyState({...reviewData,items:[{...data.items[0],locked:true}]});matching.qa.renderPhotoMatch(rankedPhoto);
    verify('A candidate cannot confirm against an approved locked point',()=>assert.equal(findNode(matching.element('qa-preview-match-candidates'),node=>node.dataset?.confirmCandidate==='review_point')?.disabled,true));
  }else{
    verify('Confirming a candidate uses the existing guarded link action and preserves other links and engineering decisions',()=>assert.fail('Candidate matching UI is not implemented.'));
    verify('A candidate cannot confirm against an approved locked point',()=>assert.fail('Candidate matching UI is not implemented.'));
  }
  const locked=selected();locked.qa.prepareModeTest();locked.qa.applyState({...data,items:[{...data.items[0],locked:true},{id:'other',locked:false}],photos:[{id:1}],links:[{photo_id:1,field_id:'review_point',state:'qa_confirmed'}]});locked.element('qa-review-photos').querySelectorAll=()=>[{dataset:{evidencePhoto:'1'},closest:()=>null}];locked.qa.selectVisiblePhotos();locked.element('qa-assignment-target').value='other';
  verify('A locked source cannot open a bulk Move dialog or throw when another target is selected',()=>assert.doesNotThrow(()=>locked.qa.openBulkMove()));
  verify('Bulk Move stays disabled when the source checkpoint is approved',()=>{assert.equal(typeof locked.qa.canMoveSelection,'function');assert.equal(locked.qa.canMoveSelection(),false);});
  const focus=selected(),selectors=[];focus.element('qa-review-photos').querySelector=selector=>{selectors.push(selector);return focus.element('original-photo-button');};
  verify('After gallery rerender and viewer Next, closing returns to the original thumbnail and saved gallery position',()=>{
    assert.equal(typeof focus.qa.restorePreviewFocus,'function');focus.qa.prepareViewerReturn();focus.qa.restorePreviewFocus();assert.equal(selectors.at(-1),'[data-preview-photo="1"]');assert.equal(focus.element('original-photo-button').focused,true);assert.equal(focus.element('qa-photo-pane').querySelector('.qa-photo-pane-scroll').scrollTop,45);
  });
  const lead=controller({role:'TEAM_LEAD'});lead.qa.applyState({...data,can_review:false});lead.qa.renderReviewContext();
  verify('The read-only Team Lead view does not introduce the QA-only AI details panel',()=>assert.equal(lead.element('qa-point-ai-details').hidden,true));
  const preview=selected(),previewRequests=[];preview.context.fetch=async url=>{previewRequests.push(url);return{ok:true,headers:{get:name=> name==='content-type'?'image/png':name==='X-Document-Preview-Page'?'1':name==='X-Document-Preview-Pages'?'2':null},blob:async()=>new Blob(['synthetic preview'],{type:'image/png'})};};
  await preview.qa.openDocumentPreview({filename:'Synthetic report preview',preview_url:'http://localhost/source/preview/',raster_preview_url:'http://localhost/source/raster/?revision_id=2',original_url:'http://localhost/source/original/'});
  verify('PDF preview prefers its protected raster route while retaining the revision scope',()=>assert.equal(previewRequests[0],'http://localhost/source/raster/?revision_id=2'));
  verify('A downloaded document is not reported as rendered before its image load succeeds',()=>{
    assert.doesNotMatch(preview.element('qa-document-preview-status').textContent,/source loaded|preview ready/i);
  });
  verify('A successfully decoded document image explicitly reports its preview as ready',()=>{
    assert.equal(typeof preview.qa.documentPreviewLoaded,'function');preview.element('qa-document-preview-image').naturalWidth=800;preview.qa.documentPreviewLoaded();assert.match(preview.element('qa-document-preview-status').textContent,/preview ready/i);
  });
  const filters=selected();
  const unknown=selected();unknown.qa.applyState({...data,ai:{status:'analysing_evidence',completed:null,total:null}});unknown.qa.renderStatus();
  verify('Unknown AI counts are unavailable rather than fabricated zero counts',()=>{
    assert.match(unknown.element('qa-analysis-numbers').textContent,/— \/ —/);assert.doesNotMatch(unknown.element('qa-analysis-numbers').textContent,/0%|100%/);
  });
  const zero=selected();zero.qa.applyState({...data,ai:{status:'ready_for_review',completed:0,total:0}});zero.qa.renderStatus();
  verify('Ready state does not invent a percentage when the denominator is zero',()=>assert.doesNotMatch(zero.element('qa-analysis-numbers').textContent,/100%/));
  verify('Analysis details start collapsed on evidence and preserve the reviewer opening them',()=>{
    const details=filters.element('qa-analysis-explanation');details.open=true;filters.qa.analysisDetailsLayout();assert.equal(details.open,false);
    details.open=true;filters.qa.analysisDetailsLayout();assert.equal(details.open,true);
  });
  verify('Secondary photo tools start collapsed on mobile without resetting a user opening them',()=>{
    assert.equal(typeof filters.qa.photoToolsLayout,'function');filters.context.innerWidth=390;const details=filters.element('qa-photo-tools');details.open=true;filters.qa.photoToolsLayout();assert.equal(details.open,false);
    details.open=true;filters.qa.photoToolsLayout();assert.equal(details.open,true);filters.context.innerWidth=1440;
  });
  verify('Zoomed photo pan is bounded to the visible image and resets at fit',()=>{
    assert.equal(typeof filters.qa.boundedPan,'function');
    assert.deepEqual({...filters.qa.boundedPan(900,-900,2,800,600,700,500)},{x:300,y:-200});
    assert.deepEqual({...filters.qa.boundedPan(40,-40,1,800,600,700,500)},{x:0,y:0});
  });
  verify('Missing photo capture metadata remains explicit and zero GPS is retained',()=>{
    assert.match(filters.qa.photoMetadataText({metadata:{gps:{latitude:0,longitude:0}}},true),/GPS 0\.00000, 0\.00000/);
    assert.match(filters.qa.photoMetadataText({},true),/Capture time not recorded/);
  });
  const hierarchy=selected();hierarchy.qa.applyState({...data,items:[{id:'data',category:'',category_known:true},{id:'excavation',category:'',category_known:false,group:'Excavation'}],general_information:{fields:[{id:'data',scope:'general'}]}});
  verify('Custom unclassified approved groups remain evidence while General Info stays data',()=>{
    assert.deepEqual(Array.from(hierarchy.qa.dataItems(),item=>item.id),['data']);assert.deepEqual(Array.from(hierarchy.qa.evidenceItems(),item=>item.id),['excavation']);
  });
  verify('Selecting a document-only or missing-photo point shows its linked evidence rather than unrelated category photos',()=>{
    const documentOnly=selected();documentOnly.qa.chooseItem('review_point');assert.equal(documentOnly.element('qa-photo-view').value,'linked');
  });
  verify('Point filters use existing inspection dispositions rather than acceptance alone',()=>{
    assert.equal(typeof filters.qa.pointMatchesFilter,'function');
    assert.equal(filters.qa.pointMatchesFilter({id:'p',type:'inspection',accepted:true,value:{result:'Checked'}},'pass'),true);
    assert.equal(filters.qa.pointMatchesFilter({id:'p',type:'inspection',accepted:false,value:{result:'Checked'}},'pass'),false);
    assert.equal(filters.qa.pointMatchesFilter({id:'p',type:'text',accepted:true,value:'approved'},'pass'),false);
    assert.equal(filters.qa.pointMatchesFilter({id:'p',type:'inspection',accepted:true,value:{result:'Defect found'}},'fail'),true);
    assert.equal(filters.qa.pointMatchesFilter({id:'p',type:'inspection',accepted:true,value:{result:'Not applicable'}},'not_applicable'),true);
  });
  const minimum=selected();minimum.qa.applyState({...data,links:[{field_id:'review_point',photo_id:1,state:'qa_confirmed'}]});
  verify('Missing-evidence filtering respects the approved minimum distinct photo requirement',()=>{
    assert.equal(minimum.qa.pointMatchesFilter({id:'review_point',type:'inspection',evidence_rules:{min_photos:2}},'missing_evidence'),true);
    assert.equal(minimum.qa.pointMatchesFilter({id:'report_only',type:'inspection',sources:[{source_id:'document:1:page:1'}]},'missing_evidence'),false);
  });
  const gallery=selected(),photos=Array.from({length:460},(_,index)=>({id:index+1,group:'Civil'}));
  gallery.qa.applyState({...data,photos,links:[{photo_id:1,field_id:'a',state:'qa_confirmed'},{photo_id:1,field_id:'b',state:'ai_suggested'}]});
  verify('Submission-wide photo totals remain unique when a source has multiple links',()=>{
    assert.equal(typeof gallery.qa.submissionCounts,'function');const counts=gallery.qa.submissionCounts();
    assert.equal(counts.total,460);assert.equal(counts.assigned,1);assert.equal(counts.unassigned,459);assert.equal(counts.confirmed,1);assert.equal(counts.suggested,1);
  });
  gallery.qa.prepareModeTest();gallery.element('qa-review-photos').querySelectorAll=()=>[1,2,3].map(id=>({dataset:{evidencePhoto:String(id)},disabled:false,hidden:false,closest:()=>({checkVisibility:()=>true})}));
  verify('Select all visible selects loaded cards only, not the hidden 460-photo collection',()=>{
    assert.equal(typeof gallery.qa.selectVisiblePhotos,'function');gallery.qa.selectVisiblePhotos();
    assert.deepEqual(Array.from(gallery.qa.selectionIds()),['1','2','3']);
  });
  verify('Selection summary distinguishes earlier-page selections from the currently rendered page',()=>{
    assert.equal(typeof gallery.qa.photoSelectionSummary,'function');gallery.element('qa-review-photos').querySelectorAll=()=>[37,38,39].map(id=>({dataset:{evidencePhoto:String(id)}}));
    assert.match(gallery.qa.photoSelectionSummary(),/3 selected total.*0 on this page/);
  });
  const stale=selected();stale.qa.prepareModeTest();stale.element('qa-review-reason').value='Unsaved human correction for revision two.';stale.qa.changed();
  stale.qa.applyState({...data,revision_id:3,source_digest:'new-source',review_digest:'new-review'});
  verify('A full refresh cannot rebase dirty input onto another submitted revision',()=>{
    assert.equal(stale.qa.canEditValue(),false);assert.equal(stale.element('qa-review-reason').value,'Unsaved human correction for revision two.');
  });
  const conflict=selected();conflict.qa.prepareModeTest();conflict.element('qa-review-reason').value='Retained correction';conflict.qa.changed();conflict.qa.applyState({...data,review_digest:'concurrent-review'});
  verify('Automatic same-source refresh never silently rebases a dirty review guard',()=>assert.equal(conflict.qa.canEditValue(),false));
  verify('Explicit refresh needs reviewer acknowledgement before reusing a newer review guard',()=>{
    assert.equal(typeof conflict.qa.reconcileDraftAfterRefresh,'function');conflict.context.confirm=()=>false;conflict.qa.reconcileDraftAfterRefresh();assert.equal(conflict.qa.canEditValue(),false);
    conflict.context.confirm=()=>true;conflict.qa.reconcileDraftAfterRefresh();assert.equal(conflict.qa.canEditValue(),true);assert.equal(conflict.element('qa-review-reason').value,'Retained correction');
    stale.context.confirm=()=>true;stale.qa.reconcileDraftAfterRefresh();assert.equal(stale.qa.canEditValue(),false);
  });
  const c=selected();c.qa.renderAnswer();
  verify('AI placeholder observations never prefill the human review reason',()=>assert.equal(c.element('qa-review-reason').value,''));
  const human=selected();human.qa.applyState({...data,items:[{...data.items[0],reason:'QA checked the recorded source.',qa_by:42}]});human.qa.renderAnswer();
  verify('An existing human QA reason is retained',()=>assert.equal(human.element('qa-review-reason').value,'QA checked the recorded source.'));
  c.element('qa-review-reason').value='Reviewer checked this source.';const probe=c.qa.saveProbe();
  await c.qa.saveAnswer(false);
  verify('Explicit Save stays on the same checklist point',()=>assert.equal(probe.advances(),0));
  const next=selected();next.element('qa-review-reason').value='A separate confirmed review.';const nextProbe=next.qa.saveProbe();
  await next.qa.saveAnswer(true);
  verify('Save and next advances only after confirmed success',()=>assert.equal(nextProbe.advances(),1));
  nextProbe.setResult(false);await next.qa.saveAnswer(true);
  verify('A failed Save and next never advances',()=>assert.equal(nextProbe.advances(),1));
  console.log(JSON.stringify({suite:'QA workspace behaviour',passed:checks.filter(check=>check.passed).length,total:checks.length,checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
