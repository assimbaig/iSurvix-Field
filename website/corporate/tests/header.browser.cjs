let chromium;
try { ({chromium}=require('playwright')); }
catch { ({chromium}=require('../../../.local/node_modules/playwright')); }
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const base=path.resolve(__dirname,'..');const output=path.resolve(base,'../../.local/corporate-qa');fs.mkdirSync(output,{recursive:true});const published=!process.argv.includes('--preview');const prefix=published?'header-v4-published':'header-v4-proposed';
const checks=[];const cases=[];const check=(name,pass)=>{checks.push({name,passed:Boolean(pass)});assert.ok(pass,name)};
const intersect=(a,b)=>a&&b&&Math.min(a.x+a.width,b.x+b.width)>Math.max(a.x,b.x)&&Math.min(a.y+a.height,b.y+b.height)>Math.max(a.y,b.y);
async function preparedPage(context){
 const page=await context.newPage();
 if(!published)for(const file of ['index.html','platform-login-v4.css','corporate-refresh-v1.css','corporate-refresh-v2.css'])await page.route(url=>url.origin==='https://isurvix.com'&&url.pathname==='/'+file,route=>route.fulfill({status:200,contentType:file.endsWith('.css')?'text/css':'text/html; charset=utf-8',body:fs.readFileSync(path.join(base,file))}));
 return page;
}
(async()=>{const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});let failure;try{
 for(const viewport of [{width:1920,height:1080},{width:1366,height:768},{width:390,height:844},{width:360,height:800}]){
  const context=await browser.newContext({viewport,hasTouch:viewport.width<800,reducedMotion:'reduce'});const page=await preparedPage(context);const errors=[];const failed=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('requestfailed',request=>failed.push({path:new URL(request.url()).pathname,reason:request.failure()?.errorText}));
  await page.goto('https://isurvix.com/index.html?next=https%3A%2F%2Fexample.invalid%2F',{waitUntil:'domcontentloaded'});
  const disclosure=page.locator('header details.platform-login');const summary=disclosure.locator('summary');
  await summary.waitFor({state:'visible',timeout:25000});await page.waitForLoadState('networkidle');
  const summaryBox=await summary.boundingBox();const brand=await page.locator('header .brand').boundingBox();const nav=page.locator('#navigation');const toggle=page.locator('header button.menu-toggle');
  check(`${viewport.width}: login is at far-right page gutter`,summaryBox.x+summaryBox.width>=viewport.width-30&&summaryBox.x+summaryBox.width<=viewport.width-10);
  check(`${viewport.width}: logo remains on left page gutter`,brand.x>=10&&brand.x<=30);
  const ax=await context.newCDPSession(page);const tree=await ax.send('Accessibility.getFullAXTree');
  const named=tree.nodes.filter(node=>!node.ignored&&node.name?.value==='Login to iSurvix Platform'&&['DisclosureTriangle','button'].includes(node.role?.value));
  check(`${viewport.width}: one accessible native Platform disclosure`,named.length===1&&await page.locator('header details.platform-login > summary').count()===1);
  await ax.detach();
  check(`${viewport.width}: Let\u2019s talk CTA removed from homepage header`,!(await page.locator('header').innerText()).includes('Let\u2019s talk'));
  const style=await summary.evaluate(el=>{const s=getComputedStyle(el);return{background:s.backgroundColor,color:s.color,radius:parseFloat(s.borderTopLeftRadius)}});
  const bg=style.background.match(/\d+/g).map(Number);const fg=style.color.match(/\d+/g).map(Number);
  check(`${viewport.width}: original dark rounded pill design`,bg.slice(0,3).every(x=>x<100)&&fg.slice(0,3).every(x=>x>220)&&style.radius>=20&&await summary.evaluate(el=>el.classList.contains('nav-contact')));
  check(`${viewport.width}: logo and login do not overlap`,!intersect(brand,summaryBox));
  check(`${viewport.width}: no horizontal overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  check(`${viewport.width}: visible label is only Login`,(await summary.innerText()).trim()==='Login');
  check(`${viewport.width}: compact pill keeps mobile touch height`,summaryBox.width<=100&&(viewport.width<800?summaryBox.height>=44:summaryBox.height<=40));

  if(await nav.isVisible()){
   const n=await nav.boundingBox();check(`${viewport.width}: all navigation grouped right next to login`,n.x>brand.x+brand.width&&n.x+n.width<=summaryBox.x&&summaryBox.x-(n.x+n.width)<=32);
  }else{
   check(`${viewport.width}: compact visible mobile Login label`,(await summary.innerText()).trim()==='Login');
   const t=await toggle.boundingBox();check(`${viewport.width}: mobile menu touch target and no overlap`,t.width>=44&&t.height>=44&&!intersect(t,summaryBox)&&!intersect(t,brand));
  }
  await page.screenshot({path:path.join(output,`${prefix}-closed-${viewport.width}x${viewport.height}.png`)});
  await summary.focus();await page.keyboard.press('Enter');check(`${viewport.width}: keyboard opens disclosure`,await disclosure.evaluate(el=>el.open));
  const login=disclosure.locator('a[href="https://app.isurvix.com/login/"]');
  check(`${viewport.width}: live iField link fixed despite next query`,await login.isVisible()&&await disclosure.locator('a').count()===3);
  check(`${viewport.width}: three verified platform logo links only`,await disclosure.locator('.platform-login-product').count()===3&&await disclosure.locator('.platform-login-product img').count()===3&&(await disclosure.locator('.platform-login-panel').innerText()).trim()==='');
  const panel=await disclosure.locator('.platform-login-panel').boundingBox();check(`${viewport.width}: menu not clipped`,panel.x>=0&&panel.x+panel.width<=viewport.width+1);
  await page.screenshot({path:path.join(output,`${prefix}-open-${viewport.width}x${viewport.height}.png`)});
  await page.keyboard.press('Tab');check(`${viewport.width}: keyboard reaches iField`,await login.evaluate(el=>el===document.activeElement));
  await page.keyboard.press('Escape');check(`${viewport.width}: Escape closes and returns focus`,!await disclosure.evaluate(el=>el.open)&&await summary.evaluate(el=>el===document.activeElement));
  await summary.click();await page.locator('main h1').first().click({position:{x:2,y:2}});check(`${viewport.width}: outside click closes`,!await disclosure.evaluate(el=>el.open));
  if(await toggle.isVisible()){
   await toggle.click();await summary.tap();check(`${viewport.width}: touch and main navigation coordinate`,await disclosure.evaluate(el=>el.open)&&await toggle.getAttribute('aria-expanded')==='false');
  }else await summary.click();
  if(viewport.width===1920){await Promise.all([page.waitForURL('https://app.isurvix.com/login/',{waitUntil:'networkidle'}),login.click()]);check('actual HTTPS application login remains reachable',await page.locator('input[type="password"]').isVisible());}
  check(`${viewport.width}: no runtime errors`,errors.length===0);check(`${viewport.width}: no failed requests`,failed.length===0);
  cases.push({viewport,style,errors,failed});await context.close();
 }
 if(!published){
  const context=await browser.newContext({viewport:{width:390,height:844},javaScriptEnabled:false});const page=await preparedPage(context);await page.goto('https://isurvix.com/index.html',{waitUntil:'networkidle'});const disclosure=page.locator('details.platform-login');await disclosure.locator('summary').click();check('JS-free native disclosure works',await disclosure.evaluate(el=>el.open));check('JS-free real iField anchor remains visible',await disclosure.locator('a[href="https://app.isurvix.com/login/"]').isVisible());await context.close();
 }
}catch(error){failure={name:error.name,message:error.message};throw error;}finally{fs.writeFileSync(path.join(output,`${prefix}-results.json`),JSON.stringify({checks,cases,failure,published,interceptions:published?0:'homepage HTML and new v3 stylesheet only; JS and app are real',credentialsRead:false,appRecordWrites:false},null,2));await browser.close();}console.log(JSON.stringify({checks:checks.length,passed:checks.filter(x=>x.passed).length,published}));})().catch(error=>{console.error(error.message);process.exitCode=1});
