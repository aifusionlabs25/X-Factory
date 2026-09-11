const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.STUDIO_TEST_CHROMIUM});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.route('**/*',route=>{
   const request=route.request();
   return new URL(request.url()).origin==='http://127.0.0.1:8877'&&request.method()==='GET'?route.continue():route.abort();
  });
  await page.goto('http://127.0.0.1:8877/',{waitUntil:'networkidle'});
  assert(await page.locator('#idea-seed').isVisible());
  assert(await page.locator('#prepare-idea').isVisible());
  assert.equal(await page.locator('[data-nextjs-dialog],.vite-error-overlay').count(),0);
  assert.equal(errors.length,0,errors.join('\n'));
  await page.screenshot({path:path.resolve('outputs/prepared-agent-qa-20260905/server-home.png')});
  console.log('PASS: running server renders opportunity input and preparation controls with no console errors. GET-only; no provider calls.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
