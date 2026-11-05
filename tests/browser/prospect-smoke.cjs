/* Run with AOS + dashboard already serving; only synthetic documents are used. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.AOS_BROWSER_EXECUTABLE, args:['--no-sandbox','--disable-dev-shm-usage']});
  for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
    const page = await browser.newPage({viewport});
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));
    await page.goto(process.env.AOS_SMOKE_URL || 'http://127.0.0.1:7777');
    await page.getByRole('menuitem', {name:'Prospect Briefs',exact:true}).click();
    await page.getByLabel('Founder API token (kept in memory)').fill('synthetic-browser-token');
    await page.getByLabel('Project', {exact:true}).fill('browser-' + viewport.width);
    await page.getByLabel('Prospect name', {exact:true}).fill('Synthetic Factory');
    await page.getByLabel('Meeting purpose', {exact:true}).fill('Evidence-led discovery');
    await page.getByLabel('Documents — TXT, MD, DOCX, text PDF', {exact:true}).setInputFiles({
      name:'notes.txt',mimeType:'text/plain',buffer:Buffer.from('Buyer: Synthetic Person\n<img src=x onerror="window.injected=true">')
    });
    await page.getByRole('button',{name:'Create brief locally',exact:true}).click();
    await page.getByRole('heading',{name:'Draft follow-up',exact:true}).waitFor();
    await page.getByRole('button',{name:'notes.txt · line 1',exact:true}).click();
    assert.equal(await page.locator('.source-passage').innerText(),'Buyer: Synthetic Person');
    assert.equal(await page.evaluate(() => window.injected),undefined);
    const draft = page.getByLabel('Editable draft — saving creates a new review version');
    await draft.fill('Thank you. Please send the missing documents.');
    assert.equal(await page.getByRole('button',{name:'Approve for use',exact:true}).isDisabled(),true);
    await page.getByRole('button',{name:'Save draft changes',exact:true}).click();
    await page.getByRole('button',{name:'Approve for use',exact:true}).waitFor();
    await page.getByRole('button',{name:'Approve for use',exact:true}).click();
    await page.waitForFunction(() => document.querySelector('.prospect-panel + .prospect-panel')?.textContent.includes('approved · extractive'));
    assert.equal(await page.evaluate(() => localStorage.getItem('synthetic-browser-token')),null);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
    assert.deepEqual(errors,[]);
    await page.screenshot({path:'/tmp/prospect-browser-'+viewport.width+'.png',fullPage:true});
    console.log('PASS prospect upload/edit/review/citation/XSS/layout', viewport.width);
    await page.close();
  }
  await browser.close();
})().catch(err=>{console.error(err);process.exit(1)});
