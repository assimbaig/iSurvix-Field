const assert=require('node:assert/strict');
const documents=require('../backend/static/core/js/engineer_documents.js');
let checks=0;
function check(condition,label){assert.ok(condition,label);checks++;}
const limits={max_batch:5,max_bytes:30*1024*1024};
for(const [name,type] of [['sketch.JPG','image/jpeg'],['plan.png','image/png'],['report.pdf','application/pdf'],['sheet.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],['sketch.webp','image/webp']]){
  check(documents.validationError({name,type,size:200},limits)==='','Supported document accepted: '+name);
}
check(!!documents.validationError({name:'report.docx',size:100},limits),'Unsupported Word document is clearly rejected');
check(!!documents.validationError({name:'report.pdf',type:'application/pdf',size:0},limits),'Empty evidence is rejected');
check(!!documents.validationError({name:'report.pdf',size:limits.max_bytes+1},limits),'Oversized evidence is rejected');
check(!!documents.validationError({name:'report.pdf',type:'text/html',size:100},limits),'A misleading MIME type is rejected before upload');
const queue=Array.from({length:13},(_,i)=>({file:{name:i+'.pdf'},kind:i<9?'report':'hand_sketch',status:'ready',valid:true}));
queue.push({file:{name:'invalid.docx'},kind:'report',status:'failed',valid:false});
const batches=documents.batches(queue,5);
check(batches.length===3,'Thirteen documents use three bounded batches by kind');
check(batches.every(batch=>batch.length<=5&&batch.every(item=>item.kind===batch[0].kind)),'Each batch preserves one classification and the backend bound');
check(batches.flat().length===13,'Invalid file is not silently included');
const state={photos:[],documents:[],digest:'saved'};
check(documents.confirmedReceipt({documents:[{id:1},{id:2}],state},2),'Successful upload requires a complete saved-state receipt');
check(!documents.confirmedReceipt({documents:[{id:1}],state},2),'Partial response cannot be shown as successful');
check(!documents.confirmedReceipt({documents:[{id:1},{id:2}],state:{digest:'saved'}},2),'Malformed saved state cannot unlock submission');
(async()=>{
  const previous={document:global.document,FormData:global.FormData,XMLHttpRequest:global.XMLHttpRequest};
  const elements=new Map();let busy=false,lastMessage={};
  const make=()=>({dataset:{},children:[],handlers:{},hidden:false,value:'report',textContent:'',
    append(...children){this.children.push(...children);},replaceChildren(...children){this.children=children;},
    setAttribute(){},querySelectorAll(){return [];},addEventListener(name,callback){this.handlers[name]=callback;}});
  const el=id=>{if(!elements.has(id))elements.set(id,make());return elements.get(id);};
  try{
    global.document={getElementById:el,createElement:make};
    global.FormData=class{append(){}};
    global.XMLHttpRequest=class{constructor(){this.handlers={};this.upload={addEventListener(){}};this.status=400;this.responseText=JSON.stringify({error:'Corrupt PDF: test fixture.'});}open(){}setRequestHeader(){}addEventListener(name,callback){this.handlers[name]=callback;}send(){queueMicrotask(()=>this.handlers.load());}};
    const root={dataset:{documentUploadUrl:'/documents/upload/',documentRemoveUrl:'/documents/remove/',sessionUrl:'/session/'}};
    const saved={...state,can_edit:true,document_upload:limits};
    const component=documents.create({root,getState:()=>saved,busy:()=>busy,blocked:()=>busy,setBusy:value=>{busy=value;},setSession(){},csrf:'fixture',uncheck(){},changed(){},message:(text,error=false)=>{lastMessage={text,error};},acceptState(){},load:async()=>{},request:async(url,data)=>data.action==='start'?{token:'fixture'}:{}});
    el('capture-document-files').handlers.change({target:{files:[{name:'corrupt.pdf',type:'application/pdf',size:100}],value:''}});
    el('capture-document-form').handlers.submit({preventDefault(){}});
    await new Promise(setImmediate);
    check(component.incomplete(),'A rejected corrupt document remains pending until explicitly removed');
    check(el('capture-document-progress-label').textContent.includes('retry remaining'),'The failed transfer initially reports that retry is needed');
    const remove=el('capture-document-pending').children[0].children.at(-1);remove.handlers.click();
    check(!component.incomplete(),'Removing the corrupt pending document clears the submission blocker');
    check(el('capture-document-progress-area').hidden,'Removing the last pending file hides its obsolete failed-transfer progress');
    check(el('capture-document-progress-label').textContent==='','The removed file no longer appears as awaiting retry');
    check(!lastMessage.error&&!lastMessage.text.includes('Corrupt'),'The removed failed file does not leave an obsolete global error');
  }finally{Object.assign(global,previous);}
  console.log(JSON.stringify({suite:'Engineer document intake unit checks',checks,passed:checks}));
})().catch(error=>{console.error(error);process.exitCode=1;});
