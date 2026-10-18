/* The Telegram bridge is simulated; this never creates real applications. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=(process.env.SITE_URL||'http://127.0.0.1:8011').replace(/\/$/,'')+'/miniapp/';
const sdk=(platform,theme='light')=>`window.__sent=[];window.__events={};window.Telegram={WebApp:{platform:${JSON.stringify(platform)},colorScheme:${JSON.stringify(theme)},ready(){},expand(){},onEvent(n,f){window.__events[n]=f},BackButton:{show(){},hide(){},onClick(f){window.__back=f}},sendData(s){window.__sent.push(s)}}};`;
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 let checks=0;const errors=[];
 try{
  for(const theme of ['light','dark']){
   const context=await browser.newContext();await context.route('https://telegram.org/js/telegram-web-app.js*',r=>r.fulfill({contentType:'application/javascript',body:sdk('android',theme)}));
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
   for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});await page.goto(base);await page.waitForSelector('.service-card');assert.equal(await page.locator('.service-card').count(),10);
    for(const view of ['services','request','contact']){
     await page.locator(`[data-view="${view}"]`).click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow ${theme} ${width} ${view}`);checks++;
    }
   }
   await page.setViewportSize({width:390,height:844});await page.goto(base);await page.waitForSelector('.service-card');
   await page.locator('.service-card').filter({has:page.getByRole('heading',{name:'Сайты с помощью AI',exact:true})}).getByRole('button').click();
   assert.equal(await page.locator('#service').inputValue(),'websites');
   await page.locator('#details').fill('Нужен сайт для мастерской с каталогом работ');await page.locator('#contact').fill('@example_visitor');
   await page.locator('#review-button').click();assert.equal(await page.locator('#review').isVisible(),false,'consent must be explicit');
   await page.locator('#consent').check();await page.locator('#review-button').click();await page.locator('#review').waitFor({state:'visible'});
   assert.match(await page.locator('#review-service').innerText(),/Сайты/);assert.equal(await page.evaluate(()=>window.__sent.length),0);
   await page.locator('#edit-button').click();await page.locator('#details').fill('Обновлённая задача для мастерской и каталога');await page.locator('#review-button').click();
   await page.locator('#send-button').click();await page.locator('#send-button').evaluate(b=>b.click());
   const sent=await page.evaluate(()=>window.__sent);assert.equal(sent.length,1);const data=JSON.parse(sent[0]);assert.equal(data.source,undefined);assert.equal(data.consent,true);assert.equal(data.service_id,'websites');assert.match(data.details,/Обновлённая/);assert.equal(data.chat_id,undefined);
   await page.goto(base);await page.waitForSelector('.service-card');
   await page.locator('#choose-pilot').click();assert.equal(await page.locator('#request-format').inputValue(),'pilot');assert.equal(await page.locator('#portfolio-interest').isChecked(),false);
   await page.locator('#service').selectOption('websites');await page.locator('#details').fill('Проверим один экран сайта на небольшой задаче');await page.locator('#contact').fill('@example_visitor');await page.locator('#consent').check();await page.locator('#review-button').click();
   assert.match(await page.locator('#review-format').innerText(),/Пробная задача/);assert.match(await page.locator('#review-portfolio').innerText(),/Без запроса/);assert.match(await page.locator('#review-pilot-note').innerText(),/индивидуально/);
   await page.locator('#edit-button').click();await page.locator('#portfolio-interest').check();await page.locator('#review-button').click();assert.match(await page.locator('#review-portfolio').innerText(),/Разрешение на публикацию ещё не дано/);await page.locator('#send-button').click();
   const pilot=JSON.parse(await page.evaluate(()=>window.__sent[0]));assert.equal(pilot.request_format,'pilot');assert.equal(pilot.portfolio_interest,true);
   await page.goto(base);await page.waitForSelector('.service-card');await page.locator('#choose-pilot').click();await page.locator('#portfolio-interest').check();await page.locator('#request-format').selectOption('standard');assert.equal(await page.locator('#portfolio-interest').isChecked(),false);assert.equal(await page.locator('#portfolio-interest-option').isVisible(),false);
   await page.locator('[data-view="request"]').click();await page.evaluate(()=>window.__back());assert.equal(await page.locator('#services-view').isVisible(),true);
   if(theme==='light')await page.screenshot({path:'/tmp/trofim-miniapp-390.png',fullPage:true});
   await context.close();
  }
  const context=await browser.newContext();await context.route('https://telegram.org/js/telegram-web-app.js*',r=>r.fulfill({contentType:'application/javascript',body:sdk('unknown')}));
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.waitForSelector('.service-card');await page.locator('#choose-other').click();await page.locator('#details').fill('Тест просмотра приложения вне Telegram');await page.locator('#contact').fill('visitor@example.test');await page.locator('#consent').check();await page.locator('#review-button').click();assert.equal(await page.locator('#send-button').isDisabled(),true);assert.match(await page.locator('#context-note').innerText(),/просмотр/);await context.close();
  const failed=await browser.newContext();await failed.route('**/catalog.json',r=>r.fulfill({status:503,body:'unavailable'}));await failed.route('https://telegram.org/js/telegram-web-app.js*',r=>r.abort());const p=await failed.newPage();await p.goto(base);await p.getByText('Не удалось загрузить услуги.',{exact:false}).waitFor();await p.locator('[data-view="contact"]').click();assert.equal(await p.locator('#personal-link').isVisible(),true);await failed.close();
  assert.deepEqual(errors,[]);console.log(`PASS: ${checks} theme/width/view layouts; standard and pilot requests, separate optional portfolio interest, review/edit, one sendData, identity-free payload, Telegram back button, browser preview and catalogue failure fallback.`);
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
