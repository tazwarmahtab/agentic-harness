/* Real dashboard and API, synthetic records only. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.AOS_BROWSER_EXECUTABLE, args:['--no-sandbox','--disable-dev-shm-usage']});
  try {
    for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
      const page = await browser.newPage({viewport});
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      const project = 'files-' + viewport.width;
      const headers = {Authorization:'Bearer synthetic-browser-token'};
      const base = 'http://127.0.0.1:7777';
      async function seed(scope, name, filename) {
        const r = await page.request.post(base+'/api/prospects', {headers, data:{venture:'netso',project:scope,prospect:name,purpose:'Synthetic knowledge browser acceptance',documents:[{filename,content_b64:Buffer.from('Buyer: Synthetic Person\nSupplied statement; unverified.').toString('base64')}]}});
        assert.equal(r.status(),201);
        const job = await r.json();
        const generated = await page.request.post(base+`/api/prospects/${job.id}/generate?venture=netso&project=${scope}`,{headers,data:{}});
        assert.equal(generated.status(),200);
      }
      await seed(project,'Synthetic Factory','notes.txt');
      await seed(project,'<img src=x onerror="window.injected=true">','evidence.txt');
      await seed('other-'+project,'Other scope secret','private.txt');
      await page.goto(base);
      await page.getByRole('menuitem',{name:'Knowledge & Files',exact:true}).click();
      await page.getByLabel('Founder API token (memory only)',{exact:true}).fill('wrong');
      await page.getByLabel('Project',{exact:true}).fill(project);
      await page.getByRole('button',{name:'Load project files',exact:true}).click();
      await page.getByRole('status').filter({hasText:'Could not load files (401)'}).waitFor();
      assert.equal(await page.locator('.knowledge-folder').count(),0);
      await page.getByLabel('Founder API token (memory only)',{exact:true}).fill('synthetic-browser-token');
      await page.getByRole('button',{name:'Load project files',exact:true}).click();
      await page.getByRole('status').filter({hasText:'2 prospect folders loaded'}).waitFor({timeout:8000}).catch(async e=>{console.log('STATUS',await page.locator('.knowledge [role=status]').innerText(),'ERRORS',errors);throw e});
      assert.equal(await page.locator('.knowledge-folder').count(),2);
      assert.equal(await page.locator('.knowledge-file').count(),8);
      assert.equal(await page.locator('.knowledge').getByText('Other scope secret',{exact:true}).count(),0);
      assert.equal(await page.evaluate(()=>window.injected),undefined);
      assert.equal(await page.locator('.knowledge img').count(),0);
      await page.getByLabel('Search folder names and filenames',{exact:true}).fill('notes');
      assert.equal(await page.locator('.knowledge-file').count(),1);
      await page.getByLabel('Search folder names and filenames',{exact:true}).fill('');
      await page.getByRole('button',{name:'Open folder: Synthetic Factory',exact:true}).click();
      assert.equal(await page.locator('.knowledge-file').count(),4);
      await page.getByRole('button',{name:'Originals',exact:true}).click();
      assert.equal(await page.locator('.knowledge-file').count(),1);
      await page.getByRole('button',{name:'Preview notes.txt in Synthetic Factory',exact:true}).click();
      assert.match(await page.locator('.knowledge-detail').innerText(),/Buyer: Synthetic Person/);
      const download = page.waitForEvent('download');
      await page.getByRole('button',{name:'Download original',exact:true}).click();
      const file = await download;
      assert.equal(file.suggestedFilename(),'notes.txt');
      assert.match(await fs.readFile(await file.path(),'utf8'),/Buyer: Synthetic Person/);
      await page.getByRole('button',{name:'View revision and review history',exact:true}).click();
      await page.getByRole('heading',{name:'Revision and review history',exact:true}).waitFor();
      await page.screenshot({path:'/tmp/knowledge-'+viewport.width+'.png',fullPage:true});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.equal(await page.locator('.knowledge-main').evaluate(e=>e.scrollWidth>e.clientWidth),false);
      await page.getByRole('button',{name:'Open brief and review',exact:true}).click();
      await page.getByRole('heading',{name:'Draft follow-up',exact:true}).waitFor();
      assert.equal(await page.getByLabel('Project',{exact:true}).inputValue(),project);
      assert.equal(await page.locator('#aos-page-title').innerText(),'Prospect Briefs');
      await page.getByRole('menuitem',{name:'Knowledge & Files',exact:true}).click();
      await page.getByRole('button',{name:'Load project files',exact:true}).click();
      await page.getByRole('status').filter({hasText:'2 prospect folders loaded'}).waitFor({timeout:8000}).catch(async e=>{console.log('STATUS',await page.locator('.knowledge [role=status]').innerText(),'ERRORS',errors);throw e});
      await page.getByLabel('Project',{exact:true}).fill('empty-project');
      assert.equal(await page.locator('.knowledge-file').count(),0);
      await page.getByRole('button',{name:'Load project files',exact:true}).click();
      await page.getByRole('status').filter({hasText:'0 prospect folders loaded'}).waitFor();
      assert.equal(await page.locator('.knowledge-file').count(),0);
      assert.equal(await page.evaluate(()=>JSON.stringify(localStorage).includes('synthetic-browser-token')),false);
      assert.deepEqual(errors,[]);
      console.log('PASS knowledge auth/scope/search/folders/preview/history/download/deep-link/XSS/layout',viewport.width);
      await page.close();
    }
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
