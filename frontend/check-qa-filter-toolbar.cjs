const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
let playwright;try{playwright=require('playwright');}catch{playwright=require(path.resolve(__dirname,'../../node_modules/playwright'));}
const root=path.resolve(__dirname,'..'),template=fs.readFileSync(path.join(root,'backend/templates/dashboards/qa_evidence_review.html'),'utf8');
const css=name=>fs.readFileSync(path.join(root,'backend/static/core/css',name+'.css'),'utf8');
const start=template.indexOf('<section class="qa-photo-pane"'),end=template.indexOf('<p id="qa-cross-category-note"');
const controls=template.slice(start,end).replace(/{%[\s\S]*?%}/g,'').replace(/{{[\s\S]*?}}/g,'');
(async()=>{
 const browser=await playwright.chromium.launch(require('./browser-test-options.cjs')());
 const results=[];
 try{
  const page=await browser.newPage();
  for(const [width,compact]of [[1920,true],[1366,true],[1024,true],[390,true],[1366,false]]){
   await page.setViewportSize({width,height:844});
   const paneWidth=width>650?width-(compact?320:660):width-20;
   await page.setContent(`<style>*{box-sizing:border-box}body{margin:0}${css('qa_evidence_review')}${css('qa_quick_review')}</style><main id="qa-evidence-review" class="qa-evidence-page ${compact?'qa-reference-review qa-two-pane':''}" style="padding:0"><section class="qa-photo-pane" style="width:${paneWidth}px"><div class="qa-photo-pane-scroll">${controls}</div></div></section></main>`);
   assert.equal(await page.locator('.qa-evidence-filterbar').count(),1,`${width}: evidence filters need their own top bar`);
   for(const id of ['qa-photo-view','qa-photo-status','qa-photo-search','qa-thumbnail-size']){
    assert.equal(await page.locator(`.qa-evidence-filterbar #${id}`).count(),1,`${id} must be in the filter bar`);
    assert.equal(await page.locator(`.qa-photo-toolbar #${id}`).count(),0,`${id} must not consume the assignment action row`);
   }
   assert.equal(await page.locator('#qa-photo-evidence-view > :first-child').getAttribute('class'),'qa-evidence-filterbar');
   const barPosition=await page.locator('.qa-evidence-filterbar').boundingBox(),titlePosition=await page.locator('#qa-item-title').boundingBox();
   assert(barPosition.y+barPosition.height<=titlePosition.y,`${width}: filters must precede the selected category or point heading`);
   const palette=await page.locator('.qa-evidence-filterbar').evaluate(bar=>({background:getComputedStyle(bar).backgroundColor,text:getComputedStyle(bar.querySelector('label')).color,input:getComputedStyle(bar.querySelector('select')).backgroundColor}));
   assert.equal(palette.background,'rgb(24, 60, 91)','Filters use the application navy header color');
   assert.equal(palette.text,'rgb(255, 255, 255)','Filter labels remain readable on navy');
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
   assert.equal(dimensions.position,'sticky','Filters remain reachable at the gallery top');
   results.push({width,compact,filterbarHeight:before.height});
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({suite:'Compact evidence filter toolbar',passed:results.length,total:5,results},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
