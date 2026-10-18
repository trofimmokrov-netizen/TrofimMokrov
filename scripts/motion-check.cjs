const {chromium}=require('playwright');
const base=(process.env.SITE_URL||'http://127.0.0.1:8000').replace(/\/$/,'')+'/';
(async()=>{
const b=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox']});
const p=await b.newPage({viewport:{width:390,height:844}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto(base);await p.waitForFunction(()=>document.querySelectorAll('h1 .text-word').length>0);
if((await p.locator('h1').innerText()).replace(/\s+/g,' ')!=='Меньше рутины. Больше возможностей.')throw Error('Heading text changed');
for(const width of [320,390,768,1440]){await p.setViewportSize({width,height:1000});for(const file of ['index.html','about.html','services.html','portfolio.html','articles.html','contact.html','articles/automation-start.html']){await p.goto(base+file);if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow '+width+' '+file);}}
await p.goto(base);await p.locator('.living-note').scrollIntoViewIfNeeded();
const first=await p.locator('.living-phrase.is-current').innerText();await p.waitForFunction(first=>document.querySelector('.living-phrase.is-current').textContent!==first,first,{timeout:8000});
const pause=p.getByRole('button',{name:'Остановить смену фраз'});await pause.click();const held=await p.locator('.living-phrase.is-current').innerText();await p.waitForTimeout(5700);if(await p.locator('.living-phrase.is-current').innerText()!==held)throw Error('Pause failed');
await p.getByRole('button',{name:'Продолжить смену фраз'}).click();await p.waitForFunction(held=>document.querySelector('.living-phrase.is-current').textContent!==held,held,{timeout:8000});
await p.emulateMedia({reducedMotion:'reduce'});await p.locator('.motion-toggle').waitFor({state:'hidden'});await p.waitForFunction(()=>!document.getAnimations().some(a=>a.playState==='running'));
const plain=await b.newPage({javaScriptEnabled:false,viewport:{width:320,height:844}});await plain.goto(base);if(!await plain.locator('h1').isVisible())throw Error('No-JS heading hidden');if(await plain.locator('.living-phrase.is-current').innerText()!==first)throw Error('No-JS phrase');
await p.emulateMedia({reducedMotion:'no-preference'});await p.setViewportSize({width:390,height:844});await p.goto(base);await p.waitForTimeout(1500);await p.screenshot({path:'/tmp/motion-mobile.png'});
if(errors.length)throw Error(errors.join('\n'));console.log('PASS: 28 responsive page checks, heading content, timed phrase change, pause/resume, live reduced-motion preference, no-JS fallback and no JS errors');await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
