/* Prepared agent: one review package, no silent approval or automatic build. */
(() => {
  let current = null, busy = false, generation = 0, unsaved = false;
  const node = (tag, text, parent) => { const n = document.createElement(tag); n.textContent = text; parent?.append(n); return n; };
  const panel = node('section', ''); panel.id = 'prepared-agent'; panel.className = 'prepared-agent'; panel.hidden = true;
  const host = document.getElementById('purpose-form');
  host.parentNode.insertBefore(panel, host.nextSibling);
  const heading = node('h2', 'Your prepared agent', panel);
  const status = node('p', '', panel); status.setAttribute('role', 'status');
  const error = node('p', '', panel); error.setAttribute('role', 'alert');
  const content = node('div', '', panel);
  const guide=node('nav','',panel);guide.className='prepared-guide';guide.setAttribute('aria-label','Your next step');panel.insertBefore(guide,content);
  function goTo(target){
    if(!target)return;
    for(let p=target;p&&p!==panel;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
    target.scrollIntoView({block:'center',behavior:'smooth'});
    target.setAttribute('tabindex','-1');target.focus({preventScroll:true});
  }
  async function api(path, payload) {
    const r = await fetch(path, payload ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)} : {cache:'no-store'});
    const data = await r.json(); if (!r.ok) throw Error(data.error || 'This step could not finish.'); return data;
  }
  function button(text, action, parent=content) {
    const b = node('button', text, parent); b.type = 'button'; b.addEventListener('click', async () => {
      if (busy) return; busy = true; b.disabled = true; error.textContent = '';
      try { await action(); } catch(e) { error.textContent = e.message; } finally { busy = false; b.disabled = false; }
    }); return b;
  }
  function render(project) {
    const retainedChat = current?.project_id === project.project_id && current?.text_candidate?.candidate_sha256 === project.text_candidate?.candidate_sha256
      ? content.querySelector('#prepared-conversation') : null;
    // Polling replaces the content: retain disclosure choices for this project.
    const disclosureState = new Map();
    const disclosureKey = detail => {
      const parts = [];
      for (let n = detail; n && n !== content; n = n.parentElement) {
        if (n.tagName === 'DETAILS') parts.unshift(n.querySelector(':scope > summary')?.textContent || '');
      }
      return JSON.stringify(parts);
    };
    if (current?.project_id === project.project_id) {
      content.querySelectorAll('details').forEach(d => disclosureState.set(disclosureKey(d), d.open));
    }
    unsaved=false;
    current = project; panel.hidden = false;
    document.getElementById('idea-start-panel').hidden=true;
    document.getElementById('purpose-form').hidden=true;
    document.getElementById('hunter-inbox').hidden=true;
    document.getElementById('hunter-review').hidden=true;
    heading.textContent = project.fields.x_agent_name ? `${project.fields.x_agent_name} · prepared agent` : 'Preparing your agent';
    status.textContent = project.message; content.replaceChildren();
    guide.replaceChildren();
    node('small','YOUR PATH · Prepare → Review → Build → Test → Package',guide);
    const guideText=node('p','',guide);guideText.setAttribute('role','status');
    const guideAction=(label,selector)=>{const b=node('button',label,guide);b.type='button';b.onclick=()=>goTo(content.querySelector(selector));};
    if(['RESEARCHING','PREPARING','BUILDING'].includes(project.status)){
      guideText.textContent='Working on your agent. Progress updates here automatically.';
    }else if(project.status==='BUILT'){
      const decision=project.dojo?.decision;
      guideText.textContent=decision==='RUNNING'?'Your local app is ready. Quality checks are running.':decision==='REVIEW_REQUIRED'?'Your local app is ready to try. Quality checks have findings to review before release.':'Your local app is ready. Open it below, or test here.';
      const testData = new URLSearchParams(location.search).get('mode') === 'ephemeral-test' ? `&mode=ephemeral-test&data=${encodeURIComponent(btoa(unescape(encodeURIComponent(JSON.stringify(project)))) )}` : '';
      const open=node('a',`Open ${project.fields.x_agent_name||'your agent'}’s app ↗`,guide);open.className='prepared-open-candidate';open.href=`/agent-app.html?project=${encodeURIComponent(project.project_id)}${testData}`;open.target='_blank';open.rel='noopener';
      guideAction('1 · Try your agent ↓','#prepared-conversation');
      guideAction(decision?'2 · See quality results ↓':'2 · Check agent quality ↓','#prepared-quality');
      node('small','Opens a clean chat app using this saved build and portrait. Keep the Factory server running. Public release is still pending review.',guide);
    }else if(project.status==='APPROVED'){
      guideText.textContent='Review complete. Your next step is to build the approved agent.';guideAction('Next · Build your agent ↓','#prepared-build');
    }else if(project.status==='NEEDS_ATTENTION'||(project.stale||[]).some(s=>['research','design','prompt'].includes(s))){
      guideText.textContent='Preparation needs attention. Your saved work is retained. Read the update below, then refresh the affected drafts.';
      guideAction('Next · Review recovery step ↓','#prepared-refresh');
    }else{
      guideText.textContent='Review the prepared Knowledge Bank and System Prompt, then approve the package. Save any edits first.';
      guideAction('Review Knowledge Bank ↓','.prepared-knowledge');guideAction('Review System Prompt ↓','#prepared-system-prompt');guideAction('Finish review ↓','.prepared-attestation');
    }
    const appearance=node('details','',content);node('summary','Agent picture · upload your own',appearance);
    const portrait=node('img','',appearance);portrait.alt=`${project.fields.x_agent_name||'Agent'} portrait`;portrait.className='prepared-portrait';portrait.hidden=!project.portrait;if(project.portrait)portrait.src=project.portrait;
    node('p','Choose a JPG, PNG or WebP. Your picture is saved with this project and shown in the Factory conversation. Animated avatar activation is separate.',appearance);
    const picker=node('input','',appearance);picker.type='file';picker.accept='image/png,image/jpeg,image/webp';picker.setAttribute('aria-label','Upload agent picture');
    const pictureStatus=node('p','',appearance);pictureStatus.setAttribute('role','status');
    picker.onchange=async()=>{
      const file=picker.files[0];if(!file)return;
      try{
        if(unsaved)throw Error('Save your other edits before uploading the picture.');
        if(file.size>10*1024*1024)throw Error('Choose a picture smaller than 10 MB.');
        picker.disabled=true;pictureStatus.textContent='Preparing and saving your picture…';
        const bitmap=await createImageBitmap(file);const canvas=document.createElement('canvas');
        let image;
        // PNG size depends on image detail, not just dimensions. Measure the
        // actual encoded result and fit it automatically to the request budget.
        try{
          for(let edge=256;edge>=16;edge=Math.floor(edge*.75)){
            const scale=Math.min(1,edge/Math.max(bitmap.width,bitmap.height));
            canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));
            canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);
            image=canvas.toDataURL('image/png');if(image.length<=54000)break;
          }
        }finally{bitmap.close();}
        const saved=await api(`/api/prepared-agents/${project.project_id}/portrait`,{revision_sha256:current.revision_sha256,image});
        current=saved;portrait.src=saved.portrait;portrait.hidden=false;
        const chatPortrait=content.querySelector('.prepared-conversation .prepared-portrait');if(chatPortrait){chatPortrait.src=saved.portrait;chatPortrait.hidden=false;}
        pictureStatus.textContent='Picture saved. Continue with your next step above.';
      }catch(e){pictureStatus.textContent=e.message;}finally{picker.disabled=false;picker.value='';}
    };
    if(['RESEARCHING','PREPARING','BUILDING'].includes(project.status)){
      node('p',`Working · status checked ${new Date().toLocaleTimeString()}. This page updates automatically; no need to click again.`,content);
      const progress=node('progress','',content);progress.removeAttribute('value');progress.setAttribute('aria-label','Preparation in progress');
    }
    node('small', `Revision ${project.revision} · ${project.status.replaceAll('_',' ')} · no production actions`, content);
    const execution=node('details','',content);node('summary','Who prepared this · execution record',execution);
    execution.open=['RESEARCHING','PREPARING'].includes(project.status);
    const stages = node('ol', '', execution);
    project.stages.forEach(s => node('li', `${s.actor.toUpperCase()} · ${s.execution_mode === 'HERMES_INFERENCE' ? 'Hermes model execution' : 'local compilation'} · ${s.usage?.model_calls || 0} model calls`, stages));
    if(!['RESEARCHING','PREPARING','BUILDING'].includes(project.status)){
      button('← Back to my opportunity',async()=>{panel.hidden=true;document.getElementById('idea-start-panel').hidden=false;document.getElementById('purpose-form').hidden=false;});
    }
    if (project.design) {
      node('h3','Proposed job',content); node('p',project.fields.purpose,content);
      node('p',project.design.role_rationale,content);
      node('h3','Personality and communication style',content); node('p',project.fields.personality,content);
      if(['NEEDS_REVIEW','APPROVED','NEEDS_ATTENTION','BUILT'].includes(project.status)){
        const edit=node('details','',content);node('summary','Edit identity or job',edit);
        const inputs={};
        [['x_agent_name','X-Agent name'],['client_name','Company'],['purpose','What should this X-Agent do?']].forEach(([key,title])=>{
          const label=node('label',title,edit);const field=node(key==='purpose'?'textarea':'input','',label);field.value=project.fields[key];inputs[key]=field;
        });
        button('Save identity and job',async()=>render(await api(`/api/prepared-agents/${project.project_id}/edit`,{
          revision_sha256:current.revision_sha256,fields:Object.fromEntries(Object.entries(inputs).map(([k,n])=>[k,n.value]))})),edit);
        node('p','Identity or job changes require a fresh specialist draft. Existing versions remain available.',edit);
      }
    }
    if (project.knowledge.length) {
      node('h3', `Knowledge Bank · ${project.knowledge.length} ${project.approval?'reviewed':'draft'} answers`, content);
      node('p',project.approval?'This package was approved by you for a local build only.':'These are drafts, not approved facts. Review the answers and their sources before approving the package.',content);
      const list = node('div','',content); list.className = 'prepared-knowledge';
      project.knowledge.forEach(entry => {
        const d = node('details','',list); node('summary',entry.question,d);
        node('p',entry.answer,d); node('small',entry.relevance,d);
        entry.sources.forEach(source => {
          if(source.source_name){node('p',`${source.source_name} · owner-supplied source, not independently verified${source.interpretation==='OWNER_DESCRIPTION_ONLY_NO_OCR'?' · image description only':''}`,d);return;}
          try { const u = new URL(source.url); if (!['https:','http:'].includes(u.protocol)) return;
            const a = node('a',`${u.hostname} · ${source.retrieved_at.slice(0,10)}`,d); a.href=u.href; a.target='_blank'; a.rel='noopener noreferrer';
          } catch (_) { /* invalid URLs are never activated */ }
        });
        if(['NEEDS_REVIEW','APPROVED','BUILT'].includes(project.status)){
          const label=node('label','Edit this draft answer',d);const answer=node('textarea','',label);answer.rows=3;answer.value=entry.answer;
          button('Save answer correction',async()=>render(await api(`/api/prepared-agents/${project.project_id}/edit`,{
            revision_sha256:current.revision_sha256,knowledge:project.knowledge.map(e=>({entry_id:e.entry_id,question:e.question,answer:e.entry_id===entry.entry_id?answer.value:e.answer}))})),d);
          if(project.knowledge.length>1)button('Remove this draft answer',async()=>render(await api(`/api/prepared-agents/${project.project_id}/edit`,{
            revision_sha256:current.revision_sha256,knowledge:project.knowledge.filter(e=>e.entry_id!==entry.entry_id).map(e=>({entry_id:e.entry_id,question:e.question,answer:e.answer}))})),d);
        }
        if(entry.source_note)node('p',entry.source_note,d);
      });
    }
    if (project.gaps.length) {
      node('h3','Missing information and assumptions',content);
      const ul = node('ul','',content); project.gaps.forEach(g => node('li',g,ul));
    }
    if (project.system_prompt) {
      const label = node('label','System Prompt — drafted by Troy',content); label.htmlFor='prepared-system-prompt';
      const prompt = node('textarea','',content); prompt.id='prepared-system-prompt'; prompt.value=project.system_prompt; prompt.rows=16;
      prompt.readOnly=!['NEEDS_REVIEW','APPROVED','BUILT'].includes(project.status);
      if (!prompt.readOnly) {
        const save = button('Save prompt edits',async()=>render(await api(`/api/prepared-agents/${project.project_id}/edit`,{revision_sha256:current.revision_sha256,system_prompt:prompt.value})));
        save.disabled=true;
        prompt.addEventListener('input',()=> {save.disabled=false; document.getElementById('prepared-approve')?.setAttribute('disabled',''); document.getElementById('prepared-build')?.setAttribute('disabled','');});
      }
    }
    const draftsStale=(project.stale||[]).some(s=>['research','design','prompt'].includes(s));
    if(project.status==='NEEDS_REVIEW' && project.system_prompt && project.knowledge.length && !draftsStale){
      node('p','Want a stronger prompt? Troy can revise this draft using your current edits and Knowledge Bank. One Hermes/Luna call; no new research, approval or build.',content);
      button('Ask Troy to improve this prompt',async()=>{
        if(unsaved)throw Error('Save your prompt and identity edits before asking Troy to revise them.');
        await follow(await api(`/api/prepared-agents/${project.project_id}/refresh`,{revision_sha256:current.revision_sha256,owner_requested:true}));
      });
    }
    if (draftsStale || project.status==='NEEDS_ATTENTION') {
      node('p',`Needs updating: ${(project.stale||[]).join(', ') || 'unfinished specialist draft'}. Refresh uses up to 11 Hermes model calls (or only Troy when the existing research/design remains valid). It does not approve or build.`,content);
      button('Refresh affected drafts',async()=>follow(await api(`/api/prepared-agents/${project.project_id}/refresh`,{revision_sha256:current.revision_sha256,owner_requested:true}))).id='prepared-refresh';
    }
    if (project.status === 'NEEDS_REVIEW' && !draftsStale) {
      const label=node('label','',content); label.className='prepared-attestation';
      const check=node('input','',label); check.type='checkbox'; check.id='prepared-attestation';
      label.append(document.createTextNode(' I reviewed the proposed job, all Knowledge Bank answers, gaps and System Prompt. I approve this exact package for a local build.'));
      const approve=button('Approve reviewed package',async()=>{if(unsaved)throw Error('Save your edits before approving.');render(await api(`/api/prepared-agents/${project.project_id}/approve`,{revision_sha256:current.revision_sha256,owner_approved:true}));});
      approve.id='prepared-approve'; approve.disabled=true; check.addEventListener('change',()=>{approve.disabled=unsaved||!check.checked;});
    }
    if (project.status==='APPROVED') {
      const build=button('Build this reviewed agent →', async()=> {if(unsaved)throw Error('Save and review your edits before building.');status.textContent='Building the exact reviewed package…'; render(await api(`/api/prepared-agents/${project.project_id}/build`,{revision_sha256:current.revision_sha256,owner_requested:true}));});
      build.id='prepared-build';
    }
    if (project.mission_id) {
      const technical=node('details','',content);node('summary','Technical tools · local knowledge checker',technical);
      button('Open technical knowledge checker',async()=>globalThis.openPreparedCandidate(project.mission_id),technical);
      node('p','This is not the conversational agent. It matches approved statements without a language model and may miss ordinary wording. Use Talk to your agent above to test the actual System Prompt and Knowledge Bank.',technical);
      const dojo=node('details','',content);node('summary','Dojo · five-call live regression',dojo);
      dojo.id='prepared-quality';
      dojo.open=Boolean(project.dojo);
      node('p','Runs the same frozen text runtime used below: grounded FAQ, unknown handling, intake, corrected details in the handoff and fresh-session isolation. Maximum five Hermes/Luna calls, no retries. This is a focused regression, not complete certification or ANAM validation.',dojo);
      if(project.dojo){node('p',project.dojo.decision.replaceAll('_',' '),dojo);if(project.dojo.failed_checks?.length)node('p',project.dojo.failed_checks.join(', '),dojo);}
      if(project.dojo?.message)node('p',project.dojo.message,dojo);
      if(project.dojo?.decision==='RUNNING'){
        const progress=node('progress','',dojo);progress.setAttribute('aria-label','Dojo check in progress');
        const update=node('p',`Dojo is running. Status checked ${new Date().toLocaleTimeString()}; updates appear automatically.`,dojo);
        update.setAttribute('role','status');
      }
      if(project.dojo?.findings?.length){
        node('p','These rule findings remain unresolved. A refusal can also trigger a conservative keyword rule; review the exact response below. This result does not clear the candidate.',dojo);
        project.dojo.findings.forEach(f=>{const item=node('details','',dojo);node('summary',`${f.rule_id} · ${f.output_lane}`,item);node('p',f.description,item);node('blockquote',f.evidence,item);});
      }
      if(!project.dojo)button('Check agent quality · 5 model calls',async()=>{
        await api(`/api/prepared-agents/${project.project_id}/dojo`,{owner_requested:true,candidate_sha256:project.text_candidate.candidate_sha256});
        await follow(await api(`/api/prepared-agents/${project.project_id}`));
      },dojo);
      const modelTest=retainedChat || node('section','',content);
      modelTest.id='prepared-conversation';modelTest.className='prepared-conversation';
      content.prepend(modelTest);
      const returnButton=document.getElementById('return-to-live-agent');
      if(returnButton){returnButton.hidden=false;returnButton.onclick=()=>{panel.hidden=false;modelTest.scrollIntoView({block:'start'});modelTest.querySelector('textarea')?.focus({preventScroll:true});};}
      if(!retainedChat){
      const ephemeral = new URLSearchParams(location.search).get('mode') === 'ephemeral-test';
      node('small',ephemeral ? 'EPHEMERAL REHEARSAL · NO MODEL CALLS' : 'REAL CONVERSATION · HERMES / LUNA',modelTest);
      node('h3','Talk to your agent',modelTest);
      const chatPortrait=node('img','',modelTest);chatPortrait.className='prepared-portrait';chatPortrait.alt=`${project.fields.x_agent_name} portrait`;chatPortrait.hidden=!project.portrait;if(project.portrait)chatPortrait.src=project.portrait;
      node('p',`${project.fields.x_agent_name} will answer using Troy’s reviewed System Prompt and your approved Knowledge Bank. Ask naturally—including follow-up questions.`,modelTest);
      node('p',ephemeral ? 'Each Send uses a deterministic browser fixture. Zero provider calls, no microphone, avatar, dispatch or external actions. Use fictional customer details only.' : 'Each Send uses one model call. Seven messages per session. No microphone, avatar, dispatch or external actions. Test with fictional customer details.',modelTest);
      let session=null,nextTurn=1;
      const progress=node('p','Ready. Type a message or choose a starter below.',modelTest);progress.setAttribute('role','status');
      const transcript=node('div','',modelTest);transcript.className='prepared-model-transcript';transcript.setAttribute('aria-live','polite');
      const starters=node('div','',modelTest);starters.className='prepared-conversation-starters';
      modelTest.insertBefore(starters,transcript);
      const label=node('label','Your message',modelTest);label.htmlFor='prepared-chat-message';
      const input=node('textarea','',modelTest);input.rows=3;input.maxLength=3000;input.setAttribute('aria-label','Message for the live text test');
      input.id='prepared-chat-message';input.placeholder='For example: What services do you offer?';
      ['What services do you offer?','What is your purpose here?'].forEach(question=>button(question,async()=>{input.value=question;input.focus();},starters));
      const send=button('Send to Luna',async()=>{
        if(!input.value.trim())throw Error('Enter a message first.');
        input.disabled=true;fresh.disabled=true;send.textContent='Agent is answering…';
        const began=Date.now();const tick=()=>{progress.textContent=`Waiting for ${project.fields.x_agent_name} · ${Math.floor((Date.now()-began)/1000)} seconds. Please keep this page open; do not resend.`;};tick();
        const timer=setInterval(tick,1000);
        try{
        if(!session)session=await api(`/api/prepared-agents/${project.project_id}/text-session`,{owner_requested:true,candidate_sha256:project.text_candidate.candidate_sha256});
        const message=input.value.trim();node('p',`You: ${message}`,transcript);
        const result=await api(`/api/prepared-agents/${project.project_id}/text-turn`,{session_id:session.session_id,message,expected_turn:nextTurn,owner_requested:true});
        node('p',`${project.fields.x_agent_name}: ${result.text}`,transcript);
        const details=node('details','',transcript);node('summary','Current handoff',details);node('pre',JSON.stringify(result.output.handoff,null,2),details);
        transcript.scrollTop=transcript.scrollHeight;
        nextTurn++;input.value='';
        progress.textContent=nextTurn>7?'Session complete · 7 of 7 messages used. Start a fresh session to continue.':`Reply received · ${nextTurn-1} of 7 messages used.`;
        if(nextTurn>7)send.hidden=true;
        }catch(e){progress.textContent=`The live test stopped: ${e.message} No automatic retry was made. Start a fresh session when the issue is resolved.`;send.hidden=true;}
        finally{clearInterval(timer);input.disabled=false;fresh.disabled=false;send.textContent='Send to Luna';}
      },modelTest);
      const fresh=button('Start fresh session',async()=>{
        session=null;nextTurn=1;input.value='';transcript.replaceChildren();progress.textContent='Fresh session — no previous customer details. Your next Send starts a new conversation.';send.disabled=false;send.hidden=false;
      },modelTest);
      node('small','Conversation is kept while this page updates. Reloading the page starts a new conversation; test evidence remains saved locally.',modelTest);
      }
    }
    content.querySelectorAll('details').forEach(d => {
      const key=disclosureKey(d);
      if(disclosureState.has(key))d.open=disclosureState.get(key);
    });
    if(project.dojo?.decision==='RUNNING')content.querySelector('#prepared-quality').open=true;
    if(project.status==='BUILT'){
      const settings=node('details','',content);settings.className='prepared-settings';node('summary','Edit agent · picture, Knowledge Bank and System Prompt',settings);
      for(const child of [...content.children])if(child!==settings&&child.id!=='prepared-conversation'&&child.id!=='prepared-quality')settings.append(child);
      const quality=content.querySelector('#prepared-quality');
      if(quality){quality.querySelector('summary').textContent='Quality results · review before release';
        if(project.dojo?.findings?.length){const explanation=node('p','The automatic checker flagged wording for review. Read the quoted answer: a refusal that repeats a price can also trigger this rule. You can keep testing the local app; this result does not approve release.',quality);quality.insertBefore(explanation,quality.children[1]);}
      }
    }
    try { localStorage.setItem('x-factory-prepared-project',project.project_id); } catch (_) {}
  }
  content.addEventListener('input',event=>{
    const field=event.target;
    if(!field.matches('input:not([type=checkbox]):not([type=file]),textarea')||field.getAttribute('aria-label')==='Message for the live text test')return;
    unsaved=true;
    document.getElementById('prepared-approve')?.setAttribute('disabled','');
    document.getElementById('prepared-build')?.setAttribute('disabled','');
    const check=document.getElementById('prepared-attestation');if(check)check.checked=false;
  });
  async function follow(project,onProgress) {
    const token=++generation; render(project);
    onProgress?.(project);
    while(token===generation && (['RESEARCHING','PREPARING','BUILDING'].includes(current.status)||current.dojo?.decision==='RUNNING')) {
      await new Promise(r=>setTimeout(r,1500));
      if(token!==generation) break;
      const updated=await api(`/api/prepared-agents/${project.project_id}`);
      render(updated);onProgress?.(updated);
    }
    return current;
  }
  async function start(idea) {
    error.textContent=''; panel.hidden=false;
    await follow(await api('/api/prepared-agents',{idea_id:idea.idea_id,owner_requested:true}));
  }
  let saved; try { saved=localStorage.getItem('x-factory-prepared-project'); } catch (_) {}
  if(saved && /^project-[a-f0-9]{24}$/.test(saved)) {
    panel.hidden=false;
    button('Reopen my prepared agent',async()=>follow(await api(`/api/prepared-agents/${saved}`)));
  }
  globalThis.PreparedAgent={start,fromHunter:async (prospectId,onProgress)=>follow(await api('/api/prepared-from-hunter',{prospect_id:prospectId,owner_requested:true}),onProgress)};
})();
