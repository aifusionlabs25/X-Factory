// Isolated UI regression. No server, provider, credentials or project writes.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.STUDIO_TEST_CHROMIUM});
 try{
  const page=await browser.newPage();let polls=0;
  const project={project_id:'project-aaaaaaaaaaaaaaaaaaaaaaaa',revision:1,status:'BUILT',message:'Built',fields:{x_agent_name:'Fixture'},stages:[],knowledge:[],gaps:[],mission_id:'fixture',text_candidate:{candidate_sha256:'fixture'},dojo:{decision:'RUNNING'}};
  await page.route('**/*',route=>{
   if(route.request().url().includes('/api/')){
    polls++;
    return route.fulfill({json:{...project,dojo:{decision:polls<4?'RUNNING':'REVIEW_REQUIRED',findings:[]}}});
   }
   return route.fulfill({contentType:'text/html',body:'<div id="idea-start-panel"></div><div id="hunter-inbox"></div><div id="hunter-review"></div><form id="purpose-form"></form>'});
  });
  await page.goto('http://fixture.test');
  await page.evaluate(()=>localStorage.setItem('x-factory-prepared-project','project-aaaaaaaaaaaaaaaaaaaaaaaa'));
  await page.addScriptTag({path:path.resolve('apps/mission-control/prepared-agent.js')});
  await page.getByRole('button',{name:'Reopen my prepared agent'}).click();
  const dojo=page.locator('details').filter({has:page.getByText('Dojo · five-call live regression',{exact:true})});
  const execution=page.locator('details').filter({has:page.getByText('Who prepared this · execution record',{exact:true})});
  assert(await dojo.evaluate(n=>n.open),'Running Dojo opens on reopen');
  const chat=page.locator('#prepared-chat-message');await chat.fill('Keep my unfinished question');
  await execution.locator('summary').click();
  await page.waitForTimeout(1800);
  assert(await dojo.evaluate(n=>n.open),'Dojo stays open across poll');
  assert(await execution.evaluate(n=>n.open),'Other disclosure stays open across poll');
  await dojo.locator('summary').click();
  await page.waitForTimeout(1700);
  assert.equal(await dojo.evaluate(n=>n.open),false,'Owner can deliberately collapse');
  await dojo.locator('summary').click();
  await page.getByText('REVIEW REQUIRED',{exact:true}).waitFor();
  assert(await dojo.evaluate(n=>n.open),'Completion keeps result open');
  assert(await execution.evaluate(n=>n.open),'Completion preserves other sections');
  assert.equal(await chat.inputValue(),'Keep my unfinished question','Polling retains the chat DOM and unfinished message');
  console.log('PASS: running, repeated polls, owner collapse/reopen, final result; zero provider calls.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
