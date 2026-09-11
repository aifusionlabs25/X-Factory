/* Local Hunter lead inbox. A send creates a handoff only; Factory use remains explicit. */
(() => {
  const el = id => document.getElementById(id);
  let callback = null, loading=false, preparing=false;
  const labels = {emergency_after_hours: 'Emergency / after-hours', moving_relocation: 'Moving / relocation', complex_service_estimate: 'Complex service / estimate'};
  async function api(path, payload) {
    const options=payload ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)} : {cache: 'no-store'};
    const response = await fetch(path,{...options,signal:AbortSignal.timeout(30000)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Hunter lead inbox stopped safely.');
    return result;
  }
  function button(text, handler, disabled = false) {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = text; b.disabled = disabled; b.addEventListener('click', handler); return b;
  }
  function render(result) {
    const list = el('hunter-inbox-list'); list.textContent = '';
    if (!result.leads.length) { list.textContent = 'No owner-reviewed Hunter leads are waiting.'; return; }
    result.leads.forEach(lead => {
      const card = document.createElement('article'); card.className = 'hunter-inbox-card';
      const copy = document.createElement('div');
      const title = document.createElement('h4'); title.textContent = lead.company_name; copy.append(title);
      const meta = document.createElement('p'); meta.textContent = `${labels[lead.wedge] || lead.wedge} · Historical Hunter score ${lead.score}/100 (not refreshed) · ${lead.website}`; copy.append(meta);
      const blocked = Boolean(lead.reverification_required || lead.blockers?.length);
      const status = document.createElement('span'); status.className = `hunter-inbox-status ${!blocked && lead.status === 'HANDOFF_READY' ? 'ready' : 'pending'}`;
      status.textContent = lead.reverification_required ? 'Needs fresh research' : blocked ? 'Review needed' : lead.status === 'HANDOFF_READY' ? 'Ready for Factory review' : 'Ready to send'; copy.append(status);
      if (blocked) { const note = document.createElement('small'); note.textContent = lead.reverification_required ? 'The old Hunter research is on hold. You can prepare an agent from fresh company research here; the old sales qualification is not automatically renewed.' : lead.blockers.join(' '); copy.append(note); }
      const actions = document.createElement('div'); actions.className = 'hunter-inbox-actions';
      const preparationNote=document.createElement('small');preparationNote.textContent='Fresh preparation reads the company again, then Aria, OMNARA and Troy draft the agent. Up to 11 Hermes/Luna calls; no approval, build or outreach. Old Hunter claims remain unapproved.';copy.append(preparationNote);
      const progress=document.createElement('p');progress.className='hunter-operation-progress';progress.setAttribute('role','status');progress.setAttribute('aria-live','polite');copy.append(progress);
      if(lead.preparation)progress.textContent=`Saved preparation: ${lead.preparation.message}`;
      const primaryLabel=lead.preparation?'OPEN SAVED PREPARATION →':'RESEARCH & PREPARE THIS AGENT →';
      actions.append(button(primaryLabel,async()=>{
        if(preparing){el('hunter-inbox-status').textContent='An agent is already being prepared. Its progress remains visible on the selected lead.';return;}
        preparing=true;el('refresh-hunter-inbox').disabled=true;
        const states=[...actions.querySelectorAll('button')].map(b=>[b,b.disabled]);states.forEach(([b])=>{b.disabled=true;});
        const started=Date.now();let message='Starting fresh company research…';
        const update=()=>{progress.textContent=`${message} · ${Math.floor((Date.now()-started)/1000)} seconds elapsed. You do not need to find Hunter or copy a prompt.`;};
        card.setAttribute('aria-busy','true');update();const timer=setInterval(update,1000);
        try {
          const result=await globalThis.PreparedAgent.fromHunter(lead.prospect_id,p=>{message=p.message;update();});
          progress.textContent=result.message;
          el('hunter-inbox-status').textContent=result.status==='NEEDS_REVIEW'?'Your prepared package is ready for review. Hunter qualification and knowledge approval remain separate.':result.message;
          const open=button('OPEN PREPARED PACKAGE →',()=>{document.getElementById('prepared-agent').scrollIntoView({behavior:'auto',block:'start'});});actions.append(open);
        }
        catch(error){progress.textContent=`Preparation stopped — ${error.message}`;el('hunter-inbox-status').textContent=progress.textContent;}
        finally{preparing=false;el('refresh-hunter-inbox').disabled=false;clearInterval(timer);card.removeAttribute('aria-busy');states.forEach(([b,disabled])=>{b.disabled=disabled;});}
      }));
      card.append(copy, actions); list.append(card);
    });
  }
  async function load() {
    if(preparing){el('hunter-inbox-status').textContent='Preparation is still running. Keeping the selected lead and its progress visible.';return;}
    if(loading)return;loading=true;
    const control=el('refresh-hunter-inbox');control.disabled=true;control.textContent='CHECKING INBOX…';
    el('hunter-inbox').setAttribute('aria-busy','true');
    el('hunter-inbox-status').textContent='Reading saved Hunter leads and checking their status. This reload does not run new web research.';
    try {const result=await api('/api/hunter/inbox');render(result);el('hunter-inbox-status').textContent=`Inbox checked at ${new Date().toLocaleTimeString()} · ${result.leads.length} saved leads. Choose “Research & prepare this agent” to run fresh research.`;}
    catch(error){el('hunter-inbox-status').textContent=`Inbox check failed — ${error.message}`;}
    finally{loading=false;control.disabled=false;control.textContent='RELOAD SAVED LEADS';el('hunter-inbox').removeAttribute('aria-busy');}
  }
  function mount(options) { callback = options.applyDraft; el('refresh-hunter-inbox').addEventListener('click', load); load(); }
  globalThis.HunterInbox = {mount, load};
})();
