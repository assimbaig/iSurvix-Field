const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map(),element=id=>{if(!elements.has(id))elements.set(id,{dataset:{canSubmit:'false',isEngineer:'false'},textContent:'',hidden:true,querySelectorAll(){return [];},classList:{toggle(){}}});return elements.get(id);};
const filename=path.resolve(__dirname,'../backend/static/core/js/survey_processing.js');
const source=fs.readFileSync(filename,'utf8').replace("  root.querySelector('.sp-tabs').addEventListener",`
  globalThis.survey={ready,renderStatus,mergeSummary,setState(value){state=value;}};return;
  root.querySelector('.sp-tabs').addEventListener`);
const context={document:{getElementById:element}};vm.createContext(context);vm.runInContext(source,context,{filename});
let checks=0;
assert.equal(context.survey.ready({status:'paused',checklist_items:[{id:'one'}]}),false,'A paused analysis cannot masquerade as a ready review result');checks++;
const active={id:2,revision:1,status:'paused',label:'Paused',completed:5,total:10,can_resume:true,source_digest:'frozen'};
context.survey.setState({active});context.survey.renderStatus();
assert.equal(element('sp-pause').hidden,false,'Authorized paused revision has a visible resume control');checks++;
assert.equal(element('sp-pause').textContent,'Resume AI','Resume is distinct from failed-job retry');checks++;
assert.ok(element('sp-progress').value>0,'Pausing retains completed progress');checks++;
const merged=context.survey.mergeSummary({id:2,can_pause:true,can_resume:false,control_token:'older-generation'},{id:2,status:'paused',can_pause:false,can_resume:true,pause_message:'Saved checkpoints retained.',control_token:'latest-generation'});
assert.equal(merged.can_resume,true,'Lightweight polling refreshes pause permissions');checks++;
assert.equal(merged.can_pause,false,'Lightweight polling clears old pause permission');checks++;
assert.equal(merged.control_token,'latest-generation','Lightweight polling refreshes the generation-bound processing control');checks++;
console.log(JSON.stringify({suite:'Survey pause UI unit checks',checks,passed:checks}));
