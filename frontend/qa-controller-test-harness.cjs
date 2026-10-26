/* Behavioural regression checks for the real saved-task QA controller.
 * DOM rendering is stubbed; requestAnimationFrame is deliberately deferred so
 * a zeroed/new pane cannot overwrite the saved review position before restore.
 */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const filename=path.resolve(__dirname,'../backend/static/core/js/qa_evidence_review.js');
function controller(options={}){
  const elements=new Map(),storage=new Map(),frames=[];
  const element=id=>{if(!elements.has(id))elements.set(id,{dataset:{},attributes:{},children:[],scrollTop:0,value:id==='qa-photo-view'?'linked':'',open:false,
    listeners:{},getAttribute(name){return name==='href'?'/checklist/1/':this.attributes[name]??null;},querySelector(){return element(id+':child');},querySelectorAll(){return [];},addEventListener(name,callback){this.listeners[name]=callback;},click(event={}){this.listeners.click?.({target:this,preventDefault(){},...event});},removeAttribute(){},setAttribute(name,value){this.attributes[name]=String(value);},append(...children){this.children.push(...children);},replaceChildren(...children){this.children=children;},scrollIntoView(){},showModal(){this.open=true;},focus(){this.focused=true;},
    parentElement:{},previousElementSibling:{},style:{},clientWidth:800,clientHeight:600,classList:{values:new Set(),toggle(name,force){if(force===true||force===undefined&&!this.values.has(name))this.values.add(name);else this.values.delete(name);},add(name){this.values.add(name);},remove(name){this.values.delete(name);},contains(name){return this.values.has(name);}},textContent:''});return elements.get(id);};
  const app=element('qa-evidence-review');app.dataset={quickReview:'true',reviewUser:'42',reviewRole:options.role||'QUALITY_ENGINEER'};
  const script=fs.readFileSync(filename,'utf8').replace('  function controls(){',`
    renderAll=()=>{el('qa-review-items').scrollTop=0;el('qa-photo-pane').querySelector('.qa-photo-pane-scroll').scrollTop=0;};
    const initialiseGuidedForTest=initialiseGuided;
    renderSiteInformation=()=>{};copySiteSource=()=>{};initialiseGuided=()=>{};schedule=()=>{};
    globalThis.qa={applyState,setStep,remember,restorePaneScroll,renderStatus,renderInline,submitDecision,renderGuidedCategories,renderAssignmentTargets,chooseItem,photoAdvisory,
      siteCellEditable:typeof siteCellEditable==='function'?siteCellEditable:null,
      initialiseGuidedForTest,chooseCategory,chooseCollection,
      chooseGeneralInformation:typeof chooseGeneralInformation==='function'?chooseGeneralInformation:null,
      generalInformationRows:typeof generalInformationRows==='function'?generalInformationRows:null,
      renderGeneralInformationView:typeof renderGeneralInformationView==='function'?renderGeneralInformationView:null,
      pointPhotoCounts:typeof pointPhotoCounts==='function'?pointPhotoCounts:null,
      buildGalleryBlocks:typeof buildGalleryBlocks==='function'?buildGalleryBlocks:null,
      renderContinuousPhotos:typeof renderContinuousPhotos==='function'?renderContinuousPhotos:null,
      gallerySnapshot:()=>typeof galleryBlocks==='undefined'?[]:galleryBlocks.map(block=>({key:block.key,loaded:block.loaded,total:block.photos.length})),
      visiblePhotos,createPointRow,openReview,closeReview,
      navigationSnapshot:()=>({step,category,selectedID,generalSummary:typeof generalSummary==='undefined'?false:generalSummary,expanded:Array.from(expanded),expandedSections:typeof expandedSections==='undefined'?[]:Array.from(expandedSections)}),
      siteRows,siteInformationTable,renderAnswer,saveAnswer,renderReviewContext,analysisDetailsLayout,openDocumentPreview,reconcileDraftAfterRefresh:typeof reconcileDraftAfterRefresh==='function'?reconcileDraftAfterRefresh:null,documentPreviewLoaded:typeof documentPreviewLoaded==='function'?documentPreviewLoaded:null,photoToolsLayout:typeof photoToolsLayout==='function'?photoToolsLayout:null,
      toggleSiteComparison:typeof toggleSiteComparison==='function'?toggleSiteComparison:null,
      applyProgressTick:typeof applyProgressTick==='function'?applyProgressTick:null,fetchProgress,
      pointMatchesFilter:typeof pointMatchesFilter==='function'?pointMatchesFilter:null,
      submissionCounts:typeof submissionCounts==='function'?submissionCounts:null,
      boundedPan:typeof boundedPan==='function'?boundedPan:null,photoMetadataText,linkedDocuments,dataItems,evidenceItems,
      renderPreview:typeof renderPreview==='function'?renderPreview:null,
      setPreviewTab:typeof setPreviewTab==='function'?setPreviewTab:null,
      renderPhotoMatch:typeof renderPhotoMatch==='function'?renderPhotoMatch:null,
      renderPhotoObservations:typeof renderPhotoObservations==='function'?renderPhotoObservations:null,
      renderAIPhases:typeof renderAIPhases==='function'?renderAIPhases:null,
      photoDisplayName:typeof photoDisplayName==='function'?photoDisplayName:null,
      syncWebReferences:typeof syncWebReferences==='function'?syncWebReferences:null,
      searchWebReferences:typeof searchWebReferences==='function'?searchWebReferences:null,
      referenceURL:typeof referenceURL==='function'?referenceURL:null,
      openPreview:typeof openPreview==='function'?openPreview:null,
      selectVisiblePhotos:typeof selectVisiblePhotos==='function'?selectVisiblePhotos:null,
      photoSelectionSummary:typeof photoSelectionSummary==='function'?photoSelectionSummary:null,
      openBulkMove,canMoveSelection:typeof canMoveSelection==='function'?canMoveSelection:null,
      restorePreviewFocus:typeof restorePreviewFocus==='function'?restorePreviewFocus:null,
      prepareViewerReturn(){viewerID=2;viewerTriggerID=1;returnFocus={isConnected:false};galleryScrollBeforeViewer=45;},
      selectionIds:()=>Array.from(selection),changed,canEditValue:()=>canEdit(),snapshot:()=>state,
      saveProbe(){let advances=0,result=true;mutate=async()=>result;advanceReview=()=>{advances++;};return{advances:()=>advances,setResult:value=>{result=value;}};},
      photoModeChanged:typeof photoModeChanged==='function'?photoModeChanged:null,
      prepareModeTest(){renderPhotos=()=>{};renderPointHeader=()=>{};controls=()=>{};}};return;
  function controls(){`);
  const context={document:{getElementById:element,createElement:tag=>element('created:'+tag+':'+elements.size)},location:{href:'http://localhost/local/photos/7/',pathname:'/local/photos/7/',origin:'http://localhost'},
    history:{replaceState(){}},URL,AbortController,CSS:{escape:value=>String(value)},innerWidth:1440,Option:function(text,value){const option=element('option:'+elements.size);option.textContent=text;option.value=value;return option;},sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
    requestAnimationFrame:callback=>frames.push(callback),confirm:()=>true};
  vm.createContext(context);vm.runInContext(script,context,{filename});
  return{qa:context.qa,element,storage,context,flush(){while(frames.length)frames.shift()();}};
}

module.exports=controller;
