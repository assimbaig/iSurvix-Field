(()=>{
const button=document.getElementById('task-export-selected');
const tools=document.getElementById('engineer-task-tools');if(tools)tools.addEventListener('toggle',()=>document.querySelector('.engineer-task-list')?.classList.toggle('engineer-show-tools',tools.open));
const boxes=[...document.querySelectorAll('.task-select')];
const update=()=>{button.disabled=!boxes.some(box=>box.checked);};
boxes.forEach(box=>box.addEventListener('change',update));
document.getElementById('task-select-all').addEventListener('change',event=>{boxes.forEach(box=>box.checked=event.target.checked);update();});
button.addEventListener('click',()=>{const target=new URL(document.getElementById('task-export').href,location.href);target.searchParams.set('selected',boxes.filter(box=>box.checked).map(box=>box.value).join(','));location.assign(target.href);});
const key='isurvix.taskExplorer.columns.v1';let preferences={};
try{const stored=JSON.parse(localStorage.getItem(key)||'{}');if(stored&&typeof stored==='object')preferences=stored;}catch(error){}
document.querySelectorAll('[data-task-column]').forEach(control=>{
const apply=()=>document.querySelectorAll('[data-task-cell="'+control.dataset.taskColumn+'"]').forEach(cell=>cell.hidden=!control.checked);
if(typeof preferences[control.dataset.taskColumn]==='boolean')control.checked=preferences[control.dataset.taskColumn];apply();
control.addEventListener('change',()=>{apply();preferences[control.dataset.taskColumn]=control.checked;try{localStorage.setItem(key,JSON.stringify(preferences));}catch(error){}});
});
})();