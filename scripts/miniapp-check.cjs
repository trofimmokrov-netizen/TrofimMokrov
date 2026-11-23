/* Navigation tests with a simulated Telegram bridge. No real applications are sent. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {site,services}=require('../miniapp/catalog.json');
const base=(process.env.SITE_URL||'http://127.0.0.1:8011').replace(/\/$/,'')+'/miniapp/';
const requestURL=site.base_url.replace(/\/$/,'')+'/contact.html#request-form';
const sdkURL='https://telegram.org/js/telegram-web-app.js*';

function sdk(platform,theme='light',openLink='record') {
  const siteOpener=openLink==='record' ? 'openLink(url){window.__siteLinks.push(url)},'
    : openLink==='throws' ? 'openLink(){throw Error("Unsupported")},' : '';
  return 'window.__siteLinks=[];window.__telegramLinks=[];window.__sent=[];window.Telegram={WebApp:{'
    +'platform:'+JSON.stringify(platform)+',colorScheme:'+JSON.stringify(theme)+',ready(){},expand(){},onEvent(){},'
    +'BackButton:{show(){},hide(){},onClick(callback){window.__back=callback}},'
    +siteOpener+'openTelegramLink(url){window.__telegramLinks.push(url)},sendData(data){window.__sent.push(data)}}};';
}

function routeSDK(context,platform,theme,openLink) {
  return context.route(sdkURL,route=>route.fulfill({contentType:'application/javascript',body:sdk(platform,theme,openLink)}));
}

async function assertFallback(page,trigger,destination) {
  await page.context().route(destination.split('#')[0],route=>route.fulfill({
    contentType:'text/html; charset=utf-8',
    body:'<!doctype html><h1 id="request-form">Форма заявки</h1>',
  }));
  const [popup]=await Promise.all([page.waitForEvent('popup'),trigger.click()]);
  await popup.waitForURL(destination);
  assert.equal(await popup.locator('#request-form').textContent(),'Форма заявки');
  await popup.close();
}

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
  const errors=[];
  let layouts=0;
  try {
    for (const theme of ['light','dark']) {
      const context=await browser.newContext();
      await routeSDK(context,'android',theme);
      const page=await context.newPage();
      page.on('pageerror',error=>errors.push(error.message));
      for (const width of [320,390,768]) {
        await page.setViewportSize({width,height:844});
        await page.goto(base);
        await page.waitForSelector('.service-card');
        assert.equal(await page.locator('.service-card').count(),services.length);
        assert.equal(await page.locator('html').evaluate((el,name)=>el.classList.contains(name),theme),true);
        for (const view of ['services','contact']) {
          await page.locator('[data-view="'+view+'"]').click();
          assert.equal(await page.locator('#'+view+'-view').isVisible(),true);
          assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+theme+' '+width+' '+view);
          layouts++;
        }
      }
      await page.locator('[data-view="services"]').click();
      const service=page.locator('.service-card').filter({has:page.getByRole('heading',{name:'Сайты с помощью AI',exact:true})});
      await service.locator('summary').click();
      assert.equal(await service.locator('details').getAttribute('open'),'');
      for (const link of await page.locator('[data-request-link]').all()) assert.equal(await link.getAttribute('href'),requestURL);
      for (const trigger of [service.locator('[data-request-link]'),page.locator('#choose-pilot'),page.locator('#choose-other'),page.locator('#tab-request')]) await trigger.click();
      await page.locator('[data-view="contact"]').click();
      assert.equal(await page.locator(':focus').getAttribute('id'),'contact-title');
      await page.locator('#contact-request').click();
      await page.locator('#personal-link').click();
      assert.deepEqual(await page.evaluate(()=>window.__siteLinks),Array(5).fill(requestURL));
      assert.deepEqual(await page.evaluate(()=>window.__telegramLinks),[site.telegram]);
      assert.deepEqual(await page.evaluate(()=>window.__sent),[]);
      assert.equal(page.url(),base);
      assert.equal(context.pages().length,1);
      await page.evaluate(()=>window.__back());
      assert.equal(await page.locator('#services-view').isVisible(),true);
      await context.close();
    }

    const mobile=await browser.newContext({isMobile:true,hasTouch:true,viewport:{width:390,height:844}});
    await routeSDK(mobile,'ios');
    const phone=await mobile.newPage();
    phone.on('pageerror',error=>errors.push(error.message));
    await phone.goto(base);
    await phone.waitForSelector('.service-card');
    await phone.evaluate(()=>{
      document.documentElement.style.setProperty('--tg-safe-area-inset-top','24px');
      document.documentElement.style.setProperty('--tg-content-safe-area-inset-top','16px');
      document.documentElement.style.setProperty('--tg-safe-area-inset-bottom','30px');
      document.documentElement.style.setProperty('--tg-content-safe-area-inset-left','25px');
    });
    assert.equal(await phone.locator('body').evaluate(el=>getComputedStyle(el).paddingTop),'40px');
    assert.equal(await phone.locator('.tabs').evaluate(el=>getComputedStyle(el).paddingBottom),'40px');
    assert.equal(await phone.locator('.tabs').evaluate(el=>getComputedStyle(el).paddingLeft),'25px');
    assert((await phone.locator('#tab-request').boundingBox()).height>=44);
    await phone.locator('#tab-request').tap();
    assert.deepEqual(await phone.evaluate(()=>window.__siteLinks),[requestURL]);
    await mobile.close();

    for (const [platform,openLink] of [['unknown','record'],['ios','throws'],['android','missing']]) {
      const fallback=await browser.newContext();
      await routeSDK(fallback,platform,'light',openLink);
      const page=await fallback.newPage();
      page.on('pageerror',error=>errors.push(error.message));
      await page.goto(base);
      await page.waitForSelector('.service-card');
      await assertFallback(page,page.locator('#tab-request'),requestURL);
      await fallback.close();
    }

    const failed=await browser.newContext();
    await failed.route('**/catalog.json',route=>route.fulfill({status:503,body:'unavailable'}));
    await failed.route(sdkURL,route=>route.abort());
    const page=await failed.newPage();
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(base);
    await page.getByText('Не удалось загрузить услуги.',{exact:false}).waitFor();
    await page.locator('[data-view="contact"]').click();
    assert.equal(await page.locator('#personal-link').isVisible(),true);
    await assertFallback(page,page.locator('#contact-request'),new URL('../contact.html#request-form',base).href);
    await failed.close();

    const noJS=await browser.newContext({javaScriptEnabled:false});
    const staticPage=await noJS.newPage();
    await staticPage.goto(base);
    await assertFallback(staticPage,staticPage.locator('#tab-request'),new URL('../contact.html#request-form',base).href);
    await noJS.close();

    assert.deepEqual(errors,[]);
    console.log('PASS: '+layouts+' theme and viewport layouts, catalog and contacts, every application link, mobile tap and safe areas, Telegram openLink, and browser fallbacks.');
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exit(1)});
