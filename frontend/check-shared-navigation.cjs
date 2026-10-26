// Synthetic CSS geometry check; authenticated routing/role checks live in Django tests.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const root=path.join(__dirname,'..'),read=n=>fs.readFileSync(path.join(root,'backend/static/core/css',n),'utf8');
const files=['style.css','platform_navigation.css','role_layout.css','enterprise.css','appearance.css','workspace_navigation.css','button_depth.css'];
const nav={QUALITY_ENGINEER:['My reviews','Projects & sites','Overview','Review activity','Reports'],
 ADMIN:['Tasks','Overview','Your projects','Review queue','Reports','Administration','Checklists'],
 TEAM_LEAD:['Tasks','Overview','Projects & sites','Review queue','Reports'],
 CLIENT:['Tasks','Overview','Projects & sites','Review queue','Reports'],ENGINEER:['My tasks'],
 SUPER_ADMIN:['Dashboard','Industries','Clients','Projects','Sites','Checklist Wizard']};
const checks=[];function check(label,run){try{run();checks.push({label,passed:true});}catch(e){checks.push({label,passed:false,error:e.message});process.exitCode=1;}}
function markup(role,compact){const qa=compact?read('qa_evidence_review.css')+read('qa_quick_review.css'):'';
 return `<!doctype html><html data-color-scheme="navy"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${qa+files.map(read).join('\n')}</style></head><body class="role-layout workspace-header-navigation${compact?' qa-review-compact-shell':''}" data-role="${role}"><header class="app-header enterprise-header"><a class="enterprise-brand"><img width="136" height="44" alt="Synthetic iSurvix header" style="display:block;width:136px;height:44px"></a>${role==='SUPER_ADMIN'?'':`<label class="header-select"><span class="sr-only">Industry and module</span><select aria-label="Module"><option>Telecom / Survey</option></select></label><label class="header-select"><span class="sr-only">Project</span><select aria-label="Project"><option>SYNTHETIC project with a long name</option></select></label>`}<div class="enterprise-header-actions">${['ADMIN','TEAM_LEAD','CLIENT'].includes(role)?'<a href="#reviews">Reviews</a>':''}<details class="enterprise-help"><summary>Help</summary></details><details class="enterprise-user"><summary>synthetic_${role.toLowerCase()}_account</summary></details></div><div class="workspace-navigation-row" id="role-navigation"><nav class="platform-nav workspace-nav-tiles" aria-label="Primary navigation">${nav[role].map((s,i)=>`<a href="#item-${i}"${i===0?' aria-current="page"':''}><svg class="workspace-nav-icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M3 3h18v18H3z"/></svg>${s}</a>`).join('')}</nav></div></header><main class="role-page-content">Synthetic CSS fixture only</main></body></html>`;}
(async()=>{const browser=await chromium.launch(require('./browser-test-options.cjs')());try{const page=await browser.newPage();await page.route('**/*',route=>route.abort());
 for(const [width,height] of [[1920,1080],[1366,768],[1024,768],[390,844]]){
  await page.setViewportSize({width,height});
  const roleSnapshots=[];
  for(const role of Object.keys(nav)){
   const snapshots=[];
   for(const compact of role==='QUALITY_ENGINEER'?[false,true]:[false]){
    await page.setContent(markup(role,compact));
    snapshots.push(await page.evaluate(()=>{const h=document.querySelector('.enterprise-header'),n=document.querySelector('#role-navigation'),r=h.getBoundingClientRect(),first=n.querySelector('a'),s=getComputedStyle(first);const controls=[...h.querySelectorAll('.enterprise-brand,select,.enterprise-header-actions>a,.enterprise-header-actions summary,.workspace-nav-tiles>a')].map(e=>({name:e.textContent||e.getAttribute('aria-label')||'brand',r:e.getBoundingClientRect()}));const collisions=[];for(let i=0;i<controls.length;i++)for(let j=i+1;j<controls.length;j++){const a=controls[i],b=controls[j];if(Math.min(a.r.right,b.r.right)-Math.max(a.r.left,b.r.left)>1&&Math.min(a.r.bottom,b.r.bottom)-Math.max(a.r.top,b.r.top)>1)collisions.push([a.name,b.name]);}return{navHeight:n.getBoundingClientRect().height,hiddenLabels:[...h.querySelectorAll('.sr-only')].every(e=>{const r=e.getBoundingClientRect();return r.width<=1&&r.height<=1;}),collisions,headerH:r.height,navY:n.getBoundingClientRect().y,firstX:first.getBoundingClientRect().x,font:s.fontSize,minHeight:parseFloat(s.minHeight),overflow:document.documentElement.scrollWidth>innerWidth,inside:[...n.querySelectorAll('a')].every(a=>a.getBoundingClientRect().top>=r.top&&a.getBoundingClientRect().bottom<=r.bottom+1)}}));
   }
   check(`${role} accessible selector labels do not enlarge the top bar at${width}`,()=>{for(const s of snapshots)assert.equal(s.hiddenLabels,true);});
   roleSnapshots.push({role,...snapshots[0]});
   check(`${role} header links remain contained without page overflow at${width}`,()=>{for(const s of snapshots){assert.equal(s.overflow,false);assert.equal(s.inside,true);}});
   check(`${role} shared link density and touch target at${width}`,()=>{for(const s of snapshots){assert.equal(s.font,width>980?'11px':'12px');assert.ok(s.minHeight>=(width>980?26:36));}});
   check(`${role} header controls never overlap at${width}`,()=>{for(const s of snapshots)assert.deepEqual(s.collisions,[]);});
   if(width<=480)check(`${role} mobile navigation stays one scrollable row with 44px touch targets`,()=>{for(const s of snapshots){assert.ok(s.navHeight<=56,JSON.stringify(s));assert.ok(s.minHeight>=44,JSON.stringify(s));}});
   if(role==='QUALITY_ENGINEER')check(`QA header stays identical between workspace and other pages at${width}`,()=>{assert.ok(Math.abs(snapshots[0].headerH-snapshots[1].headerH)<=1,JSON.stringify(snapshots));assert.ok(Math.abs(snapshots[0].navY-snapshots[1].navY)<=1);assert.ok(Math.abs(snapshots[0].firstX-snapshots[1].firstX)<=1);});
  }
  if(width>980)check(`All roles share the same compact header height at${width}`,()=>{assert.ok(Math.max(...roleSnapshots.map(s=>s.headerH))-Math.min(...roleSnapshots.map(s=>s.headerH))<=1,JSON.stringify(roleSnapshots.map(s=>({role:s.role,height:s.headerH}))));});
 }
}finally{await browser.close();}console.log(JSON.stringify({suite:'Shared header synthetic CSS geometry',passed:checks.filter(c=>c.passed).length,total:checks.length,checks},null,2));})().catch(e=>{console.error(e);process.exitCode=1;});
