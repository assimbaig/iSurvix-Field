(()=>{'use strict';const form=document.getElementById('library-actions');if(!form)return;
const boxes=[...form.querySelectorAll('[name="selected"]')],all=document.getElementById('library-select-all'),dialog=document.getElementById('library-confirm');
const desk=document.querySelector('.checklist-library');
function fit(){desk.style.height=Math.max(380,window.innerHeight-desk.getBoundingClientRect().top-10)+'px';}
window.addEventListener('resize',fit);document.fonts?.ready.then(fit);fit();
function update(){const count=boxes.filter(box=>box.checked).length;document.getElementById('library-selected').textContent=count+' selected';all.checked=!!boxes.length&&count===boxes.length;all.indeterminate=count>0&&count<boxes.length;document.querySelectorAll('[data-bulk]').forEach(button=>button.disabled=!count);}
all.addEventListener('change',()=>{boxes.forEach(box=>box.checked=all.checked);update();});boxes.forEach(box=>box.addEventListener('change',update));
function confirm(action,id){if(id)boxes.forEach(box=>box.checked=box.value===id);update();const selected=boxes.filter(box=>box.checked);if(!selected.length)return;document.getElementById('library-action').value=action;document.getElementById('library-confirm-delete').value='no';document.getElementById('library-confirm-title').textContent=action[0].toUpperCase()+action.slice(1)+' selected checklists';document.getElementById('library-confirm-text').textContent=selected.length+' checklist(s): '+selected.map(box=>box.closest('tr').querySelector('strong').textContent).join(', ')+(action==='delete'?'. Only unused, unpublished drafts without project defaults can be deleted.':'. Existing saved surveys remain preserved.');dialog.showModal();}
document.querySelectorAll('[data-bulk]').forEach(button=>button.addEventListener('click',()=>confirm(button.dataset.bulk)));
form.querySelectorAll('[data-row-action]').forEach(button=>button.addEventListener('click',()=>confirm(button.dataset.rowAction,button.dataset.id)));
dialog.addEventListener('close',()=>{if(dialog.returnValue==='confirm'){document.getElementById('library-confirm-delete').value='yes';form.requestSubmit();}});update();})();
