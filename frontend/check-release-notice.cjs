// Real-browser component fixture. Saved account/release/session persistence and
// authorization are verified by Django tests and independent live-browser QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const read = relative => fs.existsSync(path.join(root, relative)) ? fs.readFileSync(path.join(root, relative), 'utf8') : '';
const controller = read('backend/static/core/js/release_notice.js');
const css = read('backend/static/core/css/release_notice.css');
const shared = ['style.css','role_layout.css','enterprise.css','appearance.css','workspace_navigation.css','button_depth.css'].map(name=>read('backend/static/core/css/'+name)).join('\n');
const checks=[];
const check=(name,run)=>{try{run();checks.push({name,passed:true});}catch(error){checks.push({name,passed:false,error:error.message});process.exitCode=1;}};
const fixture=({release='a'.repeat(40),nonce='login-one-release-a',actor='account-one',authenticated=true,url='/release-notices/ack/'}={})=>`<!doctype html><html data-color-scheme="navy"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${shared}\n${css}</style></head><body class="role-layout workspace-header-navigation" data-role="ENGINEER"><header class="app-header">iSurvix</header><main class="role-page-content"><h1>Existing review workspace</h1><label>Unsaved review<input id="review-input" value="Retain this review input"></label><button id="review-action">Save review</button></main>${authenticated?`
<dialog id="ifield-release-notice" class="release-notice" aria-labelledby="release-notice-title" data-release-id="${release}" data-cache-nonce="${nonce}" data-actor-key="${actor}" data-ack-url="${url}">
 <header class="release-notice-header"><div><p class="release-notice-kicker">iField update</p><h2 id="release-notice-title" tabindex="-1">What's new in iField</h2><p class="release-notice-version">V1.3 Beta · 6 November 2026</p></div><button type="button" data-release-close aria-label="Close for this login only">×</button></header>
 <ul class="release-notice-changes"><li>Clearer company Admin overview.</li><li>Existing workflows and human decisions preserved.</li></ul>
 <form id="release-notice-form"><input name="csrfmiddlewaretoken" value="synthetic-csrf" type="hidden"><label class="release-notice-preference" for="release-notice-remember"><input id="release-notice-remember" type="checkbox" checked>Don't show this update again</label><p class="release-notice-help">This applies to this update only. New releases will appear again.</p><p data-release-status role="status" aria-live="polite"></p><p data-release-error role="alert" hidden></p><footer><button type="button" data-release-session>Continue for this login</button><button type="submit" data-release-submit>Continue</button></footer></form>
</dialog>`:''}<script>window.releaseNoticeCaught=[];window.releaseNoticeObservedSettled=0;(()=>{const original=Promise.prototype.catch;Promise.prototype.catch=function(handler){if(typeof handler!=='function')return original.call(this,handler);const result=original.call(this,reason=>{if(reason&&typeof reason.code==='string')window.releaseNoticeCaught.push(reason.code);return handler(reason);});result.then(()=>{window.releaseNoticeObservedSettled++;},()=>{window.releaseNoticeObservedSettled++;});return result;};})();document.getElementById('review-action').focus();${controller}</script></body></html>`;
(async()=>{
 const browser=await chromium.launch(require('./browser-test-options.cjs')());
 try {
  const page=await browser.newPage({viewport:{width:1366,height:768}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  let current={},reply='success',requests=[],held=[],unexpected=[];
  await page.route('**/*',async route=>{unexpected.push(route.request().url());await route.abort();});
  await page.route('http://ifield.test/**',async route=>{
   if(route.request().url().endsWith('/release-notices/ack/')){
    const body=route.request().postDataJSON();requests.push({body,csrf:route.request().headers()['x-csrftoken']});
    if(reply==='hold'){held.push(route);return;}
    if(reply==='network'){await route.abort('failed');return;}
    if(reply==='malformed'){await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,release_id:'wrong',dismissal:'remembered'})});return;}
    if(reply==='already-remembered'){await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,release_id:body.release_id,dismissal:'remembered'})});return;}
    if(reply==='only-session'){await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,release_id:body.release_id,dismissal:'session_only'})});return;}
    if(reply==='stale'){await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({ok:false,code:'release_changed',message:'Release changed'})});return;}
    if(reply==='failure'){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,code:'save_unavailable'})});return;}
    if(reply==='oversize'){await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,extra:'x'.repeat(20000)})});return;}
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,release_id:body.release_id,dismissal:body.suppress_current?'remembered':'session_only'})});return;
   }
   if(route.request().method()==='POST')unexpected.push(route.request().url());
   await route.fulfill({status:200,contentType:'text/html',body:fixture(current)});
  });
  const visit=async options=>{current=options||{};await page.goto('http://ifield.test/work/');};
  const isOpen=()=>page.evaluate(()=>!!document.getElementById('ifield-release-notice')?.open);
  const wait=async predicate=>{const until=Date.now()+2500;while(!predicate()){if(Date.now()>until)throw Error('Controlled acknowledgement request was not observed');await page.waitForTimeout(10);}};
  await visit();
  const opened=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,checked:document.getElementById('release-notice-remember').checked,focus:document.activeElement.id}));
  check('An offered release opens its accessible notice with remember checked',()=>{assert.equal(opened.open,true);assert.equal(opened.checked,true);assert.equal(opened.focus,'release-notice-title');});
  await page.keyboard.press('Escape');
  const closed=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,focus:document.activeElement.id,input:document.getElementById('review-input').value}));
  check('Escape permits manual review and restores focus and unsaved input',()=>{assert.equal(closed.open,false);assert.equal(closed.focus,'review-action');assert.equal(closed.input,'Retain this review input');});
  await wait(()=>requests.length===1);
  check('Escape sends a session-only acknowledgement with CSRF',()=>{assert.equal(requests.length,1);assert.equal(requests[0].body.suppress_current,false);assert.equal(requests[0].csrf,'synthetic-csrf');});
  await visit();
  const repeated=await page.evaluate(()=>document.getElementById('ifield-release-notice').open);
  check('Current nonce/release is hidden after session dismissal',()=>assert.equal(repeated,false));
  await visit({nonce:'fresh-login',actor:'account-one'});
  const freshOpen=await page.evaluate(()=>document.getElementById('ifield-release-notice').open);
  check('A fresh login is offered the update again',()=>assert.equal(freshOpen,true));
  await page.locator('[data-release-close]').click();
  await wait(()=>requests.length===2);
  await visit({nonce:'fresh-login',actor:'account-two'});
  const otherAccount=await isOpen();
  check('Another account does not inherit a previous account dismissal',()=>assert.equal(otherAccount,true));
  await page.locator('[data-release-session]').click();
  await wait(()=>requests.length===3);

  reply='hold';requests=[];
  const remembered={release:'c'.repeat(40),nonce:'remembered-login',actor:'account-one'};
  await visit(remembered);
  for(let index=0;index<7;index++)await page.keyboard.press('Tab');
  const focusTrapped=await page.evaluate(()=>document.activeElement.closest('dialog')?.id==='ifield-release-notice');
  check('Keyboard navigation stays inside the notice',()=>assert.equal(focusTrapped,true));
  await page.locator('[data-release-submit]').click();
  await wait(()=>requests.length===1);
  await page.locator('#release-notice-form').dispatchEvent('submit');
  const pending=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,status:document.querySelector('[data-release-status]').textContent,disabled:document.querySelector('[data-release-submit]').disabled}));
  check('Saving waits for server confirmation and prevents duplicate submissions',()=>{assert.equal(pending.open,true);assert.equal(pending.status,'Saving…');assert.equal(pending.disabled,true);assert.equal(requests.length,1);});
  check('Acknowledgement contains only the agreed current-release fields',()=>{assert.deepEqual(requests[0].body,{release_id:remembered.release,session_nonce:remembered.nonce,suppress_current:true});assert.equal(requests[0].csrf,'synthetic-csrf');});
  await held.shift().fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,release_id:remembered.release,dismissal:'remembered'})});
  await page.waitForFunction(()=>!document.getElementById('ifield-release-notice').open);
  const saved=await page.locator('[data-release-status]').textContent();
  check('Only a matching successful response confirms Saved for this update',()=>assert.equal(saved,'Saved for this update.'));
  await visit(remembered);
  const alreadyRemembered=await isOpen();
  check('Current acknowledged notice does not repeat in this login',()=>assert.equal(alreadyRemembered,false));
  reply='success';
  await visit({...remembered,release:'d'.repeat(40)});
  const future=await isOpen();
  check('A new release appears even with the same account and visit nonce',()=>assert.equal(future,true));
  await page.locator('[data-release-close]').click();
  await wait(()=>requests.length===2);

  reply='network';requests=[];
  const unchecked={release:'e'.repeat(40),nonce:'unchecked-login',actor:'account-one'};
  await visit(unchecked);
  await page.locator('#release-notice-remember').uncheck();
  await page.locator('[data-release-submit]').click();
  await wait(()=>requests.length===1);
  const sessionOnly=await isOpen();
  check('Unchecked Continue dismisses for this login despite unavailable acknowledgement',()=>{assert.equal(sessionOnly,false);assert.equal(requests[0].body.suppress_current,false);});
  await visit(unchecked);
  const fallback=await isOpen();
  check('Offline fallback is limited to the current login/release',()=>assert.equal(fallback,false));
  reply='success';
  await visit({...unchecked,nonce:'unchecked-new-login'});
  const uncheckedAgain=await isOpen();
  check('Session-only fallback does not suppress a new login',()=>assert.equal(uncheckedAgain,true));
  await page.locator('[data-release-close]').click();
  await wait(()=>requests.length===2);

  reply='failure';requests=[];
  await visit({release:'f'.repeat(40),nonce:'failure-login'});
  await page.locator('[data-release-submit]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-release-error]').hidden&&!document.querySelector('[data-release-submit]').disabled);
  const failed=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,status:document.querySelector('[data-release-status]').textContent,checked:document.getElementById('release-notice-remember').checked,retry:document.querySelector('[data-release-submit]').textContent}));
  check('A failed save retains the notice and preference with an honest Retry state',()=>{assert.equal(failed.open,true);assert.equal(failed.status,'Not saved.');assert.equal(failed.checked,true);assert.equal(failed.retry,'Try again');});
  reply='success';
  await page.locator('[data-release-submit]').click();
  await page.waitForFunction(()=>!document.getElementById('ifield-release-notice').open);
  check('Explicit retry saves once after a failure',()=>assert.equal(requests.length,2));

  reply='malformed';requests=[];
  await visit({release:'1'.repeat(40),nonce:'malformed-login'});
  await page.locator('[data-release-submit]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-release-error]').hidden);
  const malformed=await isOpen();
  check('A mismatched success response never confirms an acknowledgement',()=>assert.equal(malformed,true));
  await page.locator('[data-release-session]').click();
  const canContinue=await isOpen();
  check('Failed acknowledgement never blocks manual review',()=>assert.equal(canContinue,false));
  await wait(()=>requests.length===2);

  reply='stale';requests=[];
  await visit({release:'2'.repeat(40),nonce:'stale-login'});
  await page.locator('[data-release-submit]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-release-error]').hidden);
  const stale=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,error:document.querySelector('[data-release-error]').textContent,input:document.getElementById('review-input').value}));
  check('Stale release gives guidance without reloading or losing work',()=>{assert.equal(stale.open,true);assert.match(stale.error,/newer update/);assert.equal(stale.input,'Retain this review input');});
  await page.locator('[data-release-close]').click();
  await wait(()=>requests.length===2);

  reply='success';requests=[];
  await visit({release:'3'.repeat(40),nonce:'wrong-endpoint',url:'/governance/projects/'});
  await page.locator('[data-release-submit]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-release-error]').hidden);
  check('Invalid acknowledgement context cannot POST to another application action',()=>assert.deepEqual(unexpected,[]));
  await page.locator('[data-release-close]').click();

  reply='oversize';requests=[];
  await visit({release:'4'.repeat(40),nonce:'oversize-login'});
  await page.locator('[data-release-submit]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-release-error]').hidden);
  const oversized=await isOpen();
  check('Oversized response fails safely without false success',()=>assert.equal(oversized,true));
  reply='success';
  await page.locator('[data-release-close]').click();
  await wait(()=>requests.length===2);

  // Observe swallowed typed rejections without changing their original handlers.
  // Another device may already have remembered this same account/release.
  reply='already-remembered';requests=[];
  await visit({release:'8'.repeat(40),nonce:'stale-open-second-device'});
  await page.locator('#release-notice-remember').uncheck();
  await page.locator('[data-release-submit]').click();
  await page.waitForFunction(()=>window.releaseNoticeObservedSettled>=1);
  const idempotent=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,rejections:window.releaseNoticeCaught}));
  check('Session dismissal accepts a legitimate already-remembered server result',()=>{assert.equal(idempotent.open,false);assert.deepEqual(idempotent.rejections,[]);assert.equal(requests[0].body.suppress_current,false);});
  reply='only-session';requests=[];
  await visit({release:'9'.repeat(40),nonce:'must-confirm-permanent'});
  await page.locator('[data-release-submit]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-release-error]').hidden);
  const notPermanent=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,status:document.querySelector('[data-release-status]').textContent}));
  check('A checked preference never accepts a session-only result as permanent',()=>{assert.equal(notPermanent.open,true);assert.equal(notPermanent.status,'Not saved.');});
  reply='success';
  await page.locator('[data-release-session]').click();
  await wait(()=>requests.length===2);

  reply='hold';requests=[];
  const pendingClose={release:'6'.repeat(40),nonce:'close-pending'};
  await visit(pendingClose);
  await page.locator('[data-release-submit]').click();
  await wait(()=>requests.length===1);
  await page.keyboard.press('Escape');
  const nonBlocking=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,input:document.getElementById('review-input').value}));
  check('A pending acknowledgement can be closed without blocking review or a second request',()=>{assert.equal(nonBlocking.open,false);assert.equal(nonBlocking.input,'Retain this review input');assert.equal(requests.length,1);});
  await held.shift().fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,release_id:pendingClose.release,dismissal:'remembered'})});
  await page.waitForFunction(()=>!document.getElementById('release-notice-form').hasAttribute('aria-busy'));

  reply='hold';requests=[];
  await page.clock.install();
  await visit({release:'7'.repeat(40),nonce:'timeout-login'});
  await page.locator('[data-release-submit]').click();
  await wait(()=>requests.length===1);
  await page.clock.fastForward(10010);
  await page.waitForFunction(()=>!document.querySelector('[data-release-error]').hidden&&!document.querySelector('[data-release-submit]').disabled);
  const timeout=await page.evaluate(()=>({open:document.getElementById('ifield-release-notice').open,status:document.querySelector('[data-release-status]').textContent}));
  check('A stalled request reaches a bounded honest retry state',()=>{assert.equal(timeout.open,true);assert.equal(timeout.status,'Not saved.');});
  await held.shift().abort().catch(()=>{});
  reply='success';
  await page.locator('[data-release-session]').click();
  await wait(()=>requests.length===2);

  for(const [width,height]of[[1366,768],[1920,1080],[390,844]]){
   await page.setViewportSize({width,height});
   await visit({release:'5'.repeat(40),nonce:'layout-'+width});
   const geometry=await page.evaluate(()=>{const r=document.getElementById('ifield-release-notice').getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth};});
   check(`Notice is compact and contained at ${width}`,()=>{assert.ok(geometry.left>=0);assert.ok(geometry.right<=geometry.width);assert.ok(geometry.top>=0);assert.ok(geometry.bottom<=geometry.height);assert.equal(geometry.overflow,false);});
   await page.locator('[data-release-session]').click();
  }
  await visit({authenticated:false});
  const anonymous=await page.locator('#ifield-release-notice').count();
  check('No notice markup leaves the ordinary page usable',()=>assert.equal(anonymous,0));
  check('Notice controller has no uncaught JavaScript errors',()=>assert.deepEqual(errors,[]));
 } finally {await browser.close();}
 console.log(JSON.stringify({suite:'Release notice browser component fixture',passed:checks.filter(c=>c.passed).length,total:checks.length,checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
