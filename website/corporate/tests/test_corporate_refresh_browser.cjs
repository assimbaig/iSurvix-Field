/* Independent browser acceptance. Serve actual local pages/assets; never submit forms. */
const {chromium}=require(process.env.ISURVIX_PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const origin=process.env.CORPORATE_PREVIEW_ORIGIN;
const output=process.env.CORPORATE_QA_OUTPUT;
const live=process.env.CORPORATE_LIVE_AUDIT==='1';
if(!origin||!output)throw Error('Set CORPORATE_PREVIEW_ORIGIN and CORPORATE_QA_OUTPUT');
const pages=['index.html','solutions.html','engineering.html','portfolio.html','clients.html','company.html','ifield.html','igeoview.html','house-inspection.html','contact.html','industries.html','imoneta.html','engineering-intelligence.html','custom-engineering.html','products.html','privacy.html'];
const report={origin,checks:[],errors:[],pages:[]};
const check=(condition,message)=>{report.checks.push({message,passed:!!condition});assert(condition,message)};
(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_BROWSER_CHANNEL||'msedge'});
 try{
  for(const filename of pages){
   const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});
   const errors=[],failed=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('response',r=>{if(r.status()>=400)failed.push({url:r.url(),status:r.status()})});
   const response=await page.goto(origin+'/'+filename,{waitUntil:'networkidle'});
   if(live)await page.waitForTimeout(5000);
   check(response.status()===200||(live&&response.status()===403),filename+(live?' live navigation status recorded (200 or known403 transport anomaly)':' actual preview returns200'));
   check(await page.locator('h1').count()===1,filename+' exactly one main heading');
   check(await page.locator('footer a[href="privacy.html"]').count()>0,filename+' footer privacy journey');
   check(await page.locator('header a[href="clients.html"]').count()===0,filename+' no unfinished Clients primary promotion');
   const login=page.locator('a[href="https://app.isurvix.com/login/"]');
   check(await login.count()===(filename==='index.html'?1:0),filename+' homepage-only existing app login');
   for(const width of [1440,390]){
    await page.setViewportSize({width,height:width===1440?900:844});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    check(!overflow,filename+' no page-wide horizontal overflow at'+width);
    if(filename==='index.html'){
     const summary=page.locator('.platform-login summary');
     const box=await summary.boundingBox();
     check(box.height<=(width===1440?36:48),filename+' compact Login height at'+width);
     if(width===390)check(box.height>=44,'Login touch target remains44px');
     await summary.click();check(await login.isVisible(),'Login dropdown usable at'+width);
     await page.keyboard.press('Escape');check(!(await login.isVisible()),'Escape closes Login at'+width);
    }
    if(width===390){
     const menu=page.locator('header button[aria-controls="navigation"]');
     if(await menu.count()){
      await menu.click();check(await menu.getAttribute('aria-expanded')==='true',filename+' mobile menu opens');
      await page.keyboard.press('Escape');check(await menu.getAttribute('aria-expanded')==='false',filename+' Escape closes mobilemenu');
     }
    }
    await page.screenshot({path:path.join(output,filename+'-'+width+'.png'),fullPage:true});
   }
   check(errors.length===0,filename+' no uncaught script errors');
   const resourceFailures=failed.filter(item=>!(live&&item.status===403&&item.url===origin+'/'+filename));
   check(resourceFailures.length===0,filename+' no failed public resource responses'+(live?' excluding recorded initialHTML403':''));
   report.pages.push({filename,status:response.status(),title:await page.title(),errors,failed});await page.close();
  }
 }catch(e){report.errors.push(e.stack);process.exitCode=1}
 finally{await browser.close();fs.writeFileSync(path.join(output,'browser-refresh-results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:report.checks.filter(x=>x.passed).length,total:report.checks.length,errors:report.errors}));}
})();
