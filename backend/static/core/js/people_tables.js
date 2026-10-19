/* Reuse server-rendered, permission-scoped forms without changing their actions. */
(()=>{'use strict';
const create=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
function tableFor(items,kind,title){
 const frame=create('div','people-table-scroll');frame.tabIndex=0;frame.setAttribute('aria-label',title+' table; scroll for more records');
 const table=create('table','people-table'),head=create('thead'),row=create('tr');
 const columns=kind==='access'?['Person','Primary project / company','Recorded access','Add access']:kind==='industry'?['Admin','Current industry','Assignment']:kind==='invites'?['Invited email','Role','Project / expiry / status','Action']:['Person','Role','Account / project / status','Actions'];
 for(const label of columns){const th=create('th','',label);th.scope='col';row.append(th);}head.append(row);table.append(head);const body=create('tbody');
 for(const item of items){const tr=create('tr'),name=item.querySelector('h3'),badge=item.querySelector('.gw-badge'),details=item.querySelector(':scope > p'),actions=item.querySelector(':scope > .gw-actions'),who=create('th');who.scope='row';if(name)who.append(name);else who.textContent='Account';tr.append(who);
  const cell=node=>{const td=create('td');if(node)td.append(node);tr.append(td);return td;};
  if(kind==='access'){
   cell(details);const grants=item.querySelector('.gw-membership-list'),grantCell=cell();
   if(grants?.querySelector('.gw-membership')){const disclosure=create('details','people-grants'),summary=create('summary','',`View ${grants.querySelectorAll('.gw-membership').length} grants`);summary.title='Inspect recorded project grants';disclosure.append(summary,grants);grantCell.append(disclosure);}else if(grants)grantCell.append(grants);
   cell(item.querySelector(':scope > details'));
  }else if(kind==='industry'){cell(details);cell(item.querySelector(':scope > form'));}
  else{cell(badge);cell(details);const actionCell=cell(actions||item.querySelector(':scope > form'));actionCell.className='people-action-cell';}
  tr.dataset.peopleSearch=[who.textContent,badge?.textContent,details?.textContent].filter(Boolean).join(' ').toLocaleLowerCase();
  body.append(tr);item.remove();
 }
 const empty=create('tr','people-no-match');empty.hidden=true;const emptyCell=create('td','','No matching records.');emptyCell.colSpan=columns.length;empty.append(emptyCell);body.append(empty);table.append(body);frame.append(table);return frame;
}
function toolbar(section,frames){
 const tools=create('div','people-table-tools'),search=create('input'),count=create('span','people-row-count');search.type='search';search.placeholder='Search this table';search.setAttribute('aria-label','Search '+(section.querySelector('h2')?.textContent||'records'));count.setAttribute('aria-live','polite');tools.append(search,count);
 const filter=()=>{const term=search.value.trim().toLocaleLowerCase();let visible=0,total=0;for(const frame of frames){let matches=0;const rows=[...frame.querySelectorAll('[data-people-search]')];for(const row of rows){row.hidden=!!term&&!row.dataset.peopleSearch.includes(term);if(!row.hidden)matches++;}const empty=frame.querySelector('.people-no-match');empty.hidden=matches>0;empty.firstChild.textContent=rows.length?'No matching records.':'No records in this scope.';if(!frame.hidden){total+=rows.length;visible+=matches;}}count.textContent=`${visible} of ${total} records`;};
 search.addEventListener('input',filter);return {tools,filter};
}
function transform(section,kind){const items=[...section.querySelectorAll(':scope > .gw-item')];section.classList.add('people-table-panel');const frame=tableFor(items,kind,section.querySelector('h2')?.textContent||'People');const control=toolbar(section,[frame]);section.querySelectorAll(':scope > .gw-empty,:scope > h3').forEach(node=>node.remove());section.append(control.tools,frame);control.filter();}
const team=document.getElementById('team');
if(team){
 if(document.querySelector('.sa-tabbed-desk'))transform(team,'people');
 else{
  const headings=[...team.querySelectorAll(':scope > h3')],frames=[],tabs=create('nav','people-table-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','People and invitations');
  if(headings.length){team.classList.add('people-table-panel');for(const [index,heading]of headings.entries()){
   const items=[];let cursor=heading.nextElementSibling;while(cursor&&cursor.tagName!=='H3'){const next=cursor.nextElementSibling;if(cursor.classList.contains('gw-item'))items.push(cursor);cursor=next;}
   const kind=index===1?'access':index===2?'invites':'people',frame=tableFor(items,kind,heading.textContent),tab=create('button','',index===0?'People':index===1?'Project access':'Invitations');tab.type='button';tab.id='people-table-tab-'+index;tab.setAttribute('role','tab');frame.id='people-table-panel-'+index;tab.setAttribute('aria-controls',frame.id);frame.setAttribute('role','tabpanel');frame.setAttribute('aria-labelledby',tab.id);heading.remove();tabs.append(tab);frames.push(frame);
  }
  const control=toolbar(team,frames);team.append(control.tools,tabs,...frames);const buttons=[...tabs.children];function select(index,focus=false){frames.forEach((frame,at)=>{frame.hidden=at!==index;buttons[at].setAttribute('aria-selected',String(at===index));buttons[at].tabIndex=at===index?0:-1;});if(focus)buttons[index].focus();control.filter();}
  buttons.forEach((button,index)=>{button.addEventListener('click',()=>select(index));button.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();select(event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length,true);});});select(0);
  team.querySelectorAll(':scope > .gw-empty').forEach(empty=>empty.remove());
  }
 }
}
for(const[id,kind]of [['sa-admin-industries','industry'],['sa-project-access','access'],['sa-invitations','invites']]){const section=document.getElementById(id);if(section)transform(section,kind);}
for(const button of document.querySelectorAll('.people-table button')){const label=button.getAttribute('aria-label')||button.textContent.trim();if(!label)continue;button.title=label;button.setAttribute('aria-label',label);button.dataset.peopleGlyph=/revoke|deactivate|remove/i.test(label)?'×':/unlock|activate/i.test(label)?'▷':/grant/i.test(label)?'+':'✓';button.classList.add('people-icon-action');}
})();
