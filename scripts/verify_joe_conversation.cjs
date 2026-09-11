// Actual owner UI. Default: mocked responses. --live: six bounded Luna calls, no retries.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const live=process.argv.includes('--live');
const projectId='project-0b8e596080b7a6ee0bd97576';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.STUDIO_TEST_CHROMIUM});
 const results=[];let calls=0,sessions=0;
 const out=path.resolve('verification',`joe-conversation-${live?'live':'mock'}-${Date.now()}`);fs.mkdirSync(out,{recursive:true});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const r=route.request(),u=new URL(r.url());
   if(u.origin!=='http://127.0.0.1:8877')return route.abort();
   if(r.method()==='GET')return route.continue();
   if(u.pathname===`/api/prepared-agents/${projectId}/text-session`){sessions++;return live?route.continue():route.fulfill({json:{session_id:'mock-'+sessions}});}
   if(u.pathname===`/api/prepared-agents/${projectId}/text-turn`){
    calls++;assert(calls<=6,'Six-call ceiling');
    if(live)return route.continue();
    await new Promise(r=>setTimeout(r,1200));
    return route.fulfill({json:{text:'Mock reply for UI plumbing only.',output:{handoff:{request_summary:null,facts:[],unknowns:[],corrections:[]}}}});
   }
   return route.abort();
  });
  page.on('response',async response=>{
   if(response.url().endsWith('/text-turn')){
    const value=await response.json();results.push(value);
    fs.writeFileSync(path.join(out,'responses.json'),JSON.stringify({live,calls,sessions,results},null,2));
   }
  });
  await page.addInitScript(id=>localStorage.setItem('x-factory-prepared-project',id),projectId);
  await page.goto('http://127.0.0.1:8877/',{waitUntil:'networkidle'});
  await page.getByRole('button',{name:'Reopen my prepared agent',exact:true}).click();
  const chat=page.locator('#prepared-conversation');await chat.waitFor();
  assert(await chat.isVisible());
  assert(await page.locator('#prepared-agent > div > :first-child').evaluate(n=>n.id==='prepared-conversation'),'Conversation comes first');
  const input=chat.getByRole('textbox',{name:'Message for the live text test'});
  async function send(message){
   await input.fill(message);await chat.getByRole('button',{name:'Send to Luna',exact:true}).click();
   await chat.getByRole('status').filter({hasText:/Waiting for/}).waitFor();
   assert(await input.isDisabled(),'Prevent editing during inference');
   await chat.getByRole('status').filter({hasText:/Reply received|Session complete|live test stopped/}).waitFor({timeout:210000});
   assert(!/live test stopped/.test(await chat.getByRole('status').innerText()),await chat.getByRole('status').innerText());
   console.log(`Completed ${calls}/6: ${message}`);
  }
  await send('what sevices do you offer?');
  await send('what is your purpose here?');
  await send('Do you install swimming pool pumps?');
  await send("My AC isn't cooling. I'm in Lubbock and it's urgent.");
  await send("Correction: I'm actually in Wolfforth. Please summarize this for the service team.");
  await chat.screenshot({path:path.join(out,'conversation.png')});
  await chat.getByRole('button',{name:'Start fresh session',exact:true}).click();
  assert.equal(await chat.locator('.prepared-model-transcript p').count(),0);
  await send('What customer request, location, urgency or earlier questions do you have from me in this session?');
  assert.equal(sessions,2);assert.equal(calls,6);assert.deepEqual(errors,[]);
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No mobile overflow');
  await chat.screenshot({path:path.join(out,'fresh-mobile.png')});
  if(live){
   assert.match(results[0].text,/plumbing/i);assert.match(results[0].text,/HVAC|heating|cooling/i);
   assert.match(results[1].text,/intake|guide|help|handoff/i);
   assert.match(results[2].text,/confirm|approved|not|don't|do not|isn't|isn’t/i);
   const last=results[4].output.handoff;
   assert.match(last.request_summary,/AC|cooling|air condition/i);
   assert.match(JSON.stringify(last.facts),/Wolfforth/i);
   assert(!/Lubbock/i.test(JSON.stringify(last.facts)),'No stale current location');
   assert.match(JSON.stringify(last.corrections),/Lubbock/i);
   const fresh=results[5].output.handoff;
   assert.equal(fresh.request_summary,null);assert.deepEqual(fresh.facts,[]);assert.deepEqual(fresh.unknowns,[]);assert.deepEqual(fresh.corrections,[]);
  }
  console.log(`PASS ${live?'LIVE':'MOCK'} owner chat; results: ${out}`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
