const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
let playwright;try{playwright=require('playwright');}catch{playwright=require(path.resolve(__dirname,'../../node_modules/playwright'));}
const root=path.resolve(__dirname,'..'),template=fs.readFileSync(path.join(root,'backend/templates/dashboards/qa_evidence_review.html'),'utf8');
const css=name=>fs.readFileSync(path.join(root,'backend/static/core/css',name+'.css'),'utf8');
const start=template.indexOf('<section class="qa-photo-pane"'),end=template.indexOf('{% if qa_quick_review %}<div id="qa-review-resizer"');
const controls=template.slice(start,end).replace(/{%[\s\S]*?%}/g,'').replace(/{{[\s\S]*?}}/g,'');
(async()=>{
 const browser=await playwright.chromium.launch(require('./browser-test-options.cjs')());
 const results=[];
 try{
  const page=await browser.newPage();
  for(const [width,compact]of [[1920,true],[1366,true],[1024,true],[390,true],[1366,false]]){
   await page.setViewportSize({width,height:844});
   const paneWidth=width>650?width-(compact?320:660):width-20;
   await page.setContent(`<style>*{box-sizing:border-box}body{margin:0}${css('qa_evidence_review')}${css('qa_quick_review')}#qa-photo-pane{width:${paneWidth}px;height:650px;max-height:650px}</style><main id="qa-evidence-review" class="qa-evidence-page ${compact?'qa-reference-review qa-two-pane':''}" style="padding:0">${controls}</main>`);
   assert.equal(await page.locator('.qa-evidence-filterbar').count(),1,`${width}: evidence filters need their own top bar`);
   for(const id of ['qa-photo-view','qa-photo-status','qa-photo-search','qa-thumbnail-size']){
    assert.equal(await page.locator(`.qa-evidence-filterbar #${id}`).count(),1,`${id} must be in the filter bar`);
    assert.equal(await page.locator(`.qa-photo-toolbar #${id}`).count(),0,`${id} must not consume the assignment action row`);
   }
   assert.equal(await page.locator('#qa-photo-evidence-view > :first-child').getAttribute('class'),'qa-view-tools','All controls and category information need one frozen tools area');
   assert.equal(await page.locator('.qa-view-tools > :first-child').getAttribute('class'),'qa-evidence-filterbar');
   assert.equal(await page.locator('.qa-evidence-filterbar + .qa-photo-toolbar').count(),1,'Linking actions sit immediately below filters');
   const barPosition=await page.locator('.qa-evidence-filterbar').boundingBox(),titlePosition=await page.locator('#qa-item-title').boundingBox();
   assert(barPosition.y+barPosition.height<=titlePosition.y,`${width}: filters must precede the selected category or point heading`);
   const palette=await page.locator('.qa-evidence-filterbar').evaluate(bar=>({background:getComputedStyle(bar).backgroundColor,text:getComputedStyle(bar.querySelector('label')).color,input:getComputedStyle(bar.querySelector('select')).backgroundColor}));
   assert.equal(palette.background,'rgb(232, 241, 250)','Filters use a softer application blue surface');
   assert.equal(palette.text,'rgb(35, 56, 78)','Filter labels remain readable on soft blue');
   assert.equal(palette.input,'rgb(255, 255, 255)','Inputs retain white readable surfaces');
   if(width<=650)await page.locator('#qa-photo-tools').evaluate(node=>node.open=false);
   const before=await page.locator('.qa-evidence-filterbar').boundingBox();
   if(width>1100&&compact)assert(before.height<=52,`${width}: desktop filter bar should stay one compact row, got${before.height}`);
   if(width<=650){
    await page.locator('#qa-photo-tools summary').click();
    assert.equal(await page.locator('#qa-photo-search').isVisible(),true,'Touch filters can be expanded');
   }
   await page.locator('#qa-photo-search').fill('antenna');
   await page.locator('#qa-photo-status').selectOption('unassigned');
   await page.locator('#qa-thumbnail-size').selectOption('large');
   assert.equal(await page.locator('#qa-photo-search').inputValue(),'antenna');
   assert.equal(await page.locator('#qa-photo-status').inputValue(),'unassigned');
   const dimensions=await page.locator('.qa-evidence-filterbar').evaluate(bar=>({
    overflow:document.documentElement.scrollWidth>innerWidth,
    outside:[...bar.querySelectorAll('input,select')].filter(el=>el.getBoundingClientRect().width&&
     (el.getBoundingClientRect().right>bar.getBoundingClientRect().right+1||el.getBoundingClientRect().left<bar.getBoundingClientRect().left-1)).map(el=>el.id),
    position:getComputedStyle(bar).position
   }));
   assert.equal(dimensions.overflow,false,`${width}: no page-wide overflow`);
   assert.deepEqual(dimensions.outside,[],`${width}: no clipped filter fields`);
   assert.equal(dimensions.position,'static','The outer tools wrapper owns sticky positioning');
   if(width<=650){
    const selectedActions=page.locator('.qa-photo-toolbar');
    await selectedActions.locator('#qa-photo-selection').evaluate(el=>{el.textContent='2 selected in this view';});
    await selectedActions.locator('#qa-clear-selection').evaluate(el=>el.hidden=false);
    const actionBox=await selectedActions.boundingBox();
    assert(actionBox.height<=52,'Selecting multiple photos must keep mobile actions in one touch-scroll row, leaving evidence usable');
    await selectedActions.evaluate(el=>{el.scrollLeft=el.scrollWidth;});
    assert(await selectedActions.locator('#qa-clear-selection').isVisible(),'All selection controls remain reachable by touch scrolling');
   }
   await page.locator('#qa-review-photos').evaluate(gallery=>{gallery.innerHTML=Array.from({length:40},(_,i)=>`<div class="test-evidence-row" style="height:90px">Synthetic evidence ${i}</div>`).join('');});
   const tools=page.locator('.qa-view-tools'),pane=page.locator('.qa-photo-pane-scroll');
   const initialTools=await tools.boundingBox(),initialPhoto=await page.locator('.test-evidence-row').first().boundingBox();
   assert(initialTools.height<650-60,'Frozen controls retain useful evidence space');
   for(const offset of [150,350]){
    await pane.evaluate((el,y)=>{el.scrollTop=y;},offset);
    const frozen=await tools.boundingBox(),photo=await page.locator('.test-evidence-row').first().boundingBox();
    assert(Math.abs(frozen.y-initialTools.y)<=1,`${width}: tools stay fixed while evidence scrolls`);
    assert(photo.y<initialPhoto.y-100,`${width}: evidence scrolls independently below frozen tools`);
    assert(await tools.evaluate(el=>{const r=el.getBoundingClientRect();return !!document.elementFromPoint(r.x+15,r.y+15)?.closest('.qa-view-tools');}),'Evidence cannot paint over frozen controls');
   }
   results.push({width,compact,filterbarHeight:before.height});
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({suite:'Compact evidence filter toolbar',passed:results.length,total:5,results},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
