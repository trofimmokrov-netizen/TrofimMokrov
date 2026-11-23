const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const root=path.resolve(__dirname,'..');
const base=(process.env.SITE_URL||'http://127.0.0.1:8000').replace(/\/$/,'')+'/';
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {}),args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:1050},reducedMotion:'reduce'});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base,{waitUntil:'networkidle'});
 if(process.argv.includes('--capture')) await page.screenshot({path:path.join(root,'assets/site-preview.png')});
 const paths=['index.html','about.html','services.html','portfolio.html','articles.html','updates.html','contact.html','404.html',...fs.readdirSync(path.join(root,'articles')).filter(n=>n.endsWith('.html')).map(n=>'articles/'+n)];
 let count=0;
 for(const width of [320,390,768,1440]){
  await page.setViewportSize({width,height:900});
  for(const path of paths){
   const res=await page.goto(base+path,{waitUntil:'networkidle'});if(res.status()!==200)throw Error('HTTP '+path);
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow '+path+' '+width);
   await page.locator('img').evaluateAll(async xs=>{await Promise.all(xs.map(async x=>{x.loading='eager';await x.decode();}));});
   if(await page.locator('img').evaluateAll(xs=>xs.some(x=>!x.naturalWidth)))throw Error('Broken image '+path);
   if(await page.locator('h1').count()!==1)throw Error('h1 '+path);
   count++;
  }
 }
 const fragmentUnobstructed=()=>page.evaluate(()=>{
  const top=document.getElementById(location.hash.slice(1))?.getBoundingClientRect().top;
  const header=document.querySelector('.site-header').getBoundingClientRect();
  return top>=header.bottom-1&&top<innerHeight;
 });
 for(const width of [320,390]){
  await page.setViewportSize({width,height:844});
  await page.goto(base+'contact.html#request-form');
  if(!await fragmentUnobstructed())throw Error('Contact form fragment under header at '+width+'px');
  await page.goto(base);
  await page.locator('.hero .form-action').click();await page.waitForURL('**/contact.html#request-form');
  if(!await fragmentUnobstructed())throw Error('Contact form action lands under header at '+width+'px');
  await page.goto(base+'services.html');
  await page.locator('.service-index a[href="#business-system"]').click();await page.waitForURL('**/services.html#business-system');
  if(!await fragmentUnobstructed())throw Error('On-page service fragment under header at '+width+'px');
 }
 await page.setViewportSize({width:390,height:844});await page.goto(base);
 const menu=page.getByRole('button',{name:'Меню'});await menu.click();if(await menu.getAttribute('aria-expanded')!=='true')throw Error('Menu did not open');
 await page.keyboard.press('Escape');if(await menu.getAttribute('aria-expanded')!=='false')throw Error('Escape did not close menu');
 await menu.click();await page.getByRole('navigation',{name:'Основная навигация'}).getByRole('link',{name:'Статьи',exact:true}).click();await page.waitForURL('**/articles.html');
 if(await page.locator('nav a[aria-current="page"]').innerText()!=='Статьи')throw Error('Current page');
 await page.goto(base);await page.locator('summary').first().click();if(!await page.locator('details').first().getAttribute('open').then(x=>x!==null))throw Error('FAQ');
 await page.screenshot({path:'/tmp/site-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1050});await page.screenshot({path:'/tmp/site-desktop.png'});
 const plain=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});const nojs=await plain.newPage();await nojs.goto(base+'articles/automation-start.html');
 if(!await nojs.getByRole('navigation',{name:'Основная навигация'}).isVisible())throw Error('No-JS navigation hidden');
 if(!await nojs.getByRole('navigation',{name:'Содержание статьи'}).isVisible())throw Error('TOC hidden');
 if(!await nojs.locator('.reading').isVisible())throw Error('No-JS content hidden');
 const blocked=await browser.newContext({viewport:{width:390,height:844}});const fail=await blocked.newPage();await fail.route(url=>url.pathname.endsWith('/assets/main.js'),r=>r.abort());await fail.goto(base);if(!await fail.locator('#main-nav').isVisible())throw Error('Navigation hidden after script failure');
 const fallbackContext=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});
 await fallbackContext.route(url=>url.pathname.endsWith('/crm/form/loader_25.js'),route=>route.fulfill({
  contentType:'application/javascript',
  body:'const helper=document.createElement("iframe");helper.id="mock-bitrix-helper";helper.hidden=true;document.currentScript.ownerDocument.querySelector("[data-b24-form]").after(helper);',
 }));
 const fallback=await fallbackContext.newPage();
 await fallback.clock.install();
 await fallback.goto(base+'contact.html#request-form');
 await fallback.locator('#mock-bitrix-helper').waitFor({state:'attached'});
 await fallback.clock.fastForward(15100);
 await fallback.getByRole('link',{name:'Другие способы связи'}).waitFor();
 await fallback.evaluate(()=>{
  const form=document.createElement('form');
  form.innerHTML='<label>Имя <input name="name"></label>';
  document.querySelector('[data-b24-form]').after(form);
 });
 await fallback.locator('#request-form-alternative').waitFor({state:'hidden'});
 await fallback.locator('#request-form input').waitFor();
 await fallbackContext.close();
 await page.goto(base); if(await page.locator('h1').evaluate(el=>getComputedStyle(el).animationName)!=='none')throw Error('Reduced-motion animation');
 await page.keyboard.press('Tab');if(!await page.locator('.skip').evaluate(el=>document.activeElement===el))throw Error('Skip link not first keyboard target');
 if(errors.length)throw Error(errors.join('\n'));
 console.log(`PASS: ${count} page/viewport checks; image loading, mobile menu, Escape, navigation, fragment offsets, Bitrix24 fallback and recovery, FAQ, no-JS, script-failure fallback; no JavaScript errors.`);
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
