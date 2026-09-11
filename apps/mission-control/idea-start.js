/* All entry sources converge on the existing owner brief and commissioning flow. */
(() => {
  const el = id => document.getElementById(id);
  let callbacks, mode = 'idea', draft = null, busy = false, appliedBinding = null;
  let roles = [], selectedRoleId = '', researchJob = null, researchResult = null, pollGeneration = 0;
  let roleChosenByOwner = false, roleRankings = [], roleCapabilityGaps = [], roleFitExplanation = '';
  let attachments=[];
  const add = (tag, text, parent) => { const node = document.createElement(tag); node.textContent = text; parent.append(node); return node; };
  const roleId = role => role?.chassis_id || role?.role_id || role?.id || '';
  const roleTitle = role => role?.display_name || role?.role_title || role?.title || role?.name || 'Untitled role';
  const selectedRole = () => roles.find(role => roleId(role) === selectedRoleId) || null;
  const jobState = job => String(job?.status || '').toLowerCase();
  const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

  async function api(path, payload) {
    const response = await fetch(path, payload ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)} : {cache: 'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'This step could not be completed. Your input is still here.');
    return result;
  }

  function setBusy(value) {
    busy = value;
    ['prepare-idea', 'research-idea', 'use-idea', 'idea-seed', 'idea-company', 'idea-website', 'idea-post-text', 'owner-purpose', 'refresh-idea-roles', 'accept-idea-research', 'idea-resolved-company', 'idea-resolved-website', 'resume-idea-research'].forEach(id => { if (el(id)) el(id).disabled = value; });
    document.querySelectorAll('[data-entry-mode]').forEach(b => { b.disabled = value; });
    syncActions();
    callbacks?.updateBuildState();
  }

  function syncActions() {
    const reconnectPending = Boolean(researchJob?.job_id && !el('resume-idea-research').hidden);
    el('research-idea').disabled = busy || !draft || reconnectPending;
    el('use-idea').disabled = busy || !draft || !selectedRole();
    el('accept-idea-research').disabled = busy || !researchResult || !selectedRole();
    el('idea-start-role').disabled = busy || el('idea-manual-role').hidden;
    el('idea-role-choice').disabled = busy || el('idea-direction-review').hidden;
  }

  function resetResearch() {
    pollGeneration += 1; researchJob = null; researchResult = null;
    el('idea-research-panel').hidden = true; el('idea-direction-review').hidden = true;
    el('resume-idea-research').hidden = true; el('idea-job-error').textContent = '';
    el('idea-resolved-company').required = false; el('idea-resolved-website').required = false;
    el('research-idea').textContent = 'Prepare my agent →';
    el('use-idea').textContent = 'Manual setup · skip specialist preparation';
  }

  function explainSelectedRole() {
    const role = selectedRole();
    const rank = roleRankings.find(item => roleId(item.role) === selectedRoleId);
    const reasons = (rank?.reasons || []).filter(reason => typeof reason === 'string');
    let explanation = role
      ? reasons.length ? reasons.join(' ') : `You chose ${roleTitle(role)}. The current brief has no direct matching signals for this role; review its scope below.`
      : roleFitExplanation;
    if (roleCapabilityGaps.length) explanation += ` Capabilities still unavailable: ${roleCapabilityGaps.join(', ')}. Choosing a role does not add these capabilities.`;
    el('idea-start-role-reason').textContent = explanation;
    el('idea-role-choice-note').textContent = explanation;
    ['idea-start-role', 'idea-role'].forEach(prefix => {
      el(`${prefix}-limit-details`).hidden = !role;
      el(`${prefix}-summary`).textContent = role?.summary || '';
      const list = el(`${prefix}-limits`); list.textContent = '';
      const limits = [...(role?.capability_limits || role?.authority?.capability_limits || []), ...(role?.boundaries || [])];
      [...new Set(limits)].forEach(limit => add('li', limit, list));
    });
  }

  function fillRoleChoices(recommendation, available = [], preferredId = '') {
    const seen = new Map();
    [...available, recommendation?.recommended, ...(recommendation?.alternatives || [])].filter(Boolean).forEach(role => { if (roleId(role)) seen.set(roleId(role), {...seen.get(roleId(role)), ...role}); });
    roles = [...seen.values()];
    const recommended = recommendation?.recommended;
    selectedRoleId = seen.has(preferredId) ? preferredId : roleId(recommended);
    roleRankings = recommendation?.role_recommendation?.ranked || recommendation?.ranked || [];
    roleCapabilityGaps = recommendation?.role_recommendation?.capability_gaps || recommendation?.capability_gaps || [];
    ['idea-start-role', 'idea-role-choice'].forEach(id => {
      const select = el(id); select.textContent = '';
      add('option', recommended ? 'Choose a starting role…' : 'No clear match — choose a role', select).value = '';
      roles.forEach(role => { add('option', `${roleTitle(role)}${roleId(role) === roleId(recommended) ? ' · recommended' : ''}`, select).value = roleId(role); });
      select.value = selectedRoleId;
    });
    const reason = recommendation?.reason || recommendation?.explanation || recommendation?.role_recommendation?.explanation || (recommended
      ? 'This is the closest available starting point. Check that it fits the job before continuing.'
      : 'No available role clearly fits this brief. Edit the job or choose a suitable role explicitly before continuing.');
    roleFitExplanation = reason;
    el('idea-recommended-role').textContent = recommended ? roleTitle(recommended) : 'No clear role match';
    const recommendedRank = roleRankings.find(item => roleId(item.role) === roleId(recommended));
    el('idea-role-reason').textContent = recommendedRank?.reasons?.length ? recommendedRank.reasons.join(' ') : reason;
    explainSelectedRole();
    syncActions();
  }

  async function refreshRoles() {
    if (!el('owner-purpose').checkValidity()) throw new Error('Describe the job in 10–2,000 characters.');
    const [library, recommendation] = await Promise.all([api('/api/roles'), api('/api/roles/recommend', {purpose: el('owner-purpose').value.trim()})]);
    fillRoleChoices(recommendation, Array.isArray(library) ? library : library.roles || [], roleChosenByOwner ? selectedRoleId : '');
  }

  function switchMode(next) {
    if (busy) return;
    mode = next;
    document.querySelectorAll('[data-entry-mode]').forEach(b => {
      const selected = b.dataset.entryMode === mode;
      b.classList.toggle('selected', selected); b.setAttribute('aria-pressed', String(selected));
    });
    el('idea-start-panel').hidden = mode === 'hunter';
    // The legacy draft importer cannot refresh stale Hunter research. Keep it
    // out of the normal owner journey instead of offering a second dead end.
    el('hunter-review').hidden = true;
    el('hunter-inbox').hidden = mode !== 'hunter';
    el('purpose-form').hidden = mode === 'hunter' || !draft;
    el('idea-start-title').textContent = mode === 'website' ? 'Bring the link that caught your attention.' : 'What sparked the idea?';
    el('idea-seed-help').textContent = mode === 'website'
      ? 'Paste a company website or an X post. Add the post text below if you have it.'
      : 'Describe the opportunity in your own words. A short idea is enough to start.';
    el('idea-seed').placeholder = mode === 'website' ? 'https://example.com or https://x.com/…' : 'An agent for independent moving companies that answers questions and helps customers prepare a move request…';
    if (mode === 'hunter') globalThis.HunterInbox?.load();
  }

  async function showDraft(result) {
    draft = result; resetResearch(); roles = [];
    roleChosenByOwner = draft.recommendation?.selected_by === 'OWNER_EXPLICIT_CHOICE';
    selectedRoleId = roleChosenByOwner ? roleId(draft.recommendation.recommended) : '';
    el('idea-result').hidden = false;
    el('commissioning-form').hidden = true;
    el('purpose-form').hidden = false;
    el('idea-next-actions').hidden = false;
    el('idea-manual-role').hidden = false;
    el('manual-purpose-actions').hidden = true;
    el('recommended-fit').hidden = true;
    el('owner-purpose').value = draft.fields.purpose;
    el('idea-result-title').textContent = draft.fields.client_name || 'A starting point for your idea';
    const labels = {IDEA: 'YOUR IDEA', COMPANY_NAME: 'COMPANY STARTING POINT', WEBSITE: 'WEBSITE STARTING POINT', X_POST: 'INSPIRATION FROM X'};
    el('idea-source-label').textContent = labels[draft.seed_kind] || 'YOUR DRAFT';
    el('idea-result-note').textContent = 'This is only your starting brief. Choose Prepare my agent to have research, Aria, OMNARA and Troy prepare the proposed job, Knowledge Bank and System Prompt for your review.';
    el('idea-missing').textContent = '';
    for (const message of (draft.missing_information || [])) add('li', typeof message === 'string' ? message : JSON.stringify(message), el('idea-missing'));
    el('idea-research-status').textContent = (draft.notices || []).join(' ');
    el('idea-research-summary').hidden = true;
    el('idea-research-help').textContent = 'Prepare my agent returns the proposed job, sourced Knowledge Bank drafts and tailored System Prompt together. You review them before approval or build. Manual setup skips that preparation and leaves you to supply the knowledge.';
    try { localStorage.setItem('x-factory-last-idea', draft.idea_id); } catch (_) { /* saving the server draft does not depend on browser storage */ }
    try { await refreshRoles(); }
    catch (error) { fillRoleChoices(null); el('idea-start-role-reason').textContent = `Roles could not be loaded. ${error.message} Choose “Check role fit” to try again.`; }
  }

  function currentInput(includePurpose = false) {
    const input = {seed: el('idea-seed').value.trim()};
    if(attachments.length)input.attachments=attachments.map(a=>({name:a.name,text:a.text,...(a.image?{image:a.image}:{})}));
    for (const [key, id] of [['company_name', 'idea-company'], ['website', 'idea-website'], ['post_text', 'idea-post-text']]) {
      if (el(id).value.trim()) input[key] = el(id).value.trim();
    }
    if (includePurpose) {
      input.purpose = el('owner-purpose').value.trim();
      if (selectedRoleId && roleChosenByOwner) input.selected_chassis_id = selectedRoleId;
    }
    return input;
  }

  async function saveEdits({forceNew = false} = {}) {
    if (!draft) throw new Error('Shape your idea first.');
    if (!el('owner-purpose').checkValidity()) throw new Error('Describe the job in 10–2,000 characters.');
    if (forceNew || draft.fields.purpose !== el('owner-purpose').value.trim() || (selectedRoleId && roleId(draft.recommendation?.recommended) !== selectedRoleId)) {
      draft = await api('/api/ideas/prepare', currentInput(true));
      try { localStorage.setItem('x-factory-last-idea', draft.idea_id); } catch (_) { /* browser storage optional */ }
    }
    return draft;
  }

  async function prepare(event) {
    event.preventDefault();
    if (busy || !el('idea-start-form').reportValidity()) return;
    setBusy(true); el('idea-error').textContent = ''; el('prepare-idea').textContent = 'Preparing your brief…';
    try {
      await showDraft(await api('/api/ideas/prepare', currentInput()));
    } catch (error) { el('idea-error').textContent = error.message; }
    finally { setBusy(false); el('prepare-idea').textContent = 'Shape my idea →'; }
  }

  function renderProgress(job) {
    const state = jobState(job);
    const labels = {queued: 'Queued', running: 'Researching', needs_review: 'Ready for your review', failed: 'Needs attention', cancelled: 'Stopped'};
    el('idea-research-panel').hidden = false;
    el('idea-job-state').textContent = labels[state] || 'Checking progress';
    el('idea-job-state').dataset.state = state;
    el('idea-job-title').textContent = state === 'needs_review' ? 'Review the direction.' : state === 'failed' ? 'Research needs attention.' : 'Finding the best starting point.';
    const progress = Array.isArray(job.progress) ? job.progress : Array.isArray(job.events) ? job.events : [];
    el('idea-job-progress').textContent = '';
    progress.forEach(item => { const message = typeof item === 'string' ? item : item.message || item.detail || item.description; if (message) add('li', message, el('idea-job-progress')); });
    const last = progress.at(-1);
    el('idea-job-status').textContent = job.message || job.progress_message || (typeof last === 'string' ? last : last?.message) || ({queued: 'Your research request is queued.', running: 'Research is running. Progress appears here as work completes.', needs_review: 'Read the findings, adjust the brief, and choose the starting role.', failed: 'Your brief is saved. Review the issue below before starting another research attempt.', cancelled: 'Research stopped. Your brief is still available.'}[state] || 'Checking the saved research request.');
  }

  function safeSourceLink(source, parent) {
    try {
      const url = new URL(source.url);
      if (!['https:', 'http:'].includes(url.protocol)) return;
      const anchor = add('a', source.title || url.hostname, parent);
      anchor.href = url.href; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
      if (source.observed_on) add('small', `Checked ${source.observed_on}`, parent);
    } catch (_) { /* Invalid source URLs are never navigated. */ }
  }

  async function showResearchResult(job) {
    if (!job.result || !job.result_sha256) throw new Error('The research result is incomplete. Check the saved request again; it has not been used.');
    researchResult = job.result;
    el('idea-direction-review').hidden = false;
    el('idea-findings-summary').textContent = researchResult.summary || 'Research is ready for review.';
    el('idea-findings').textContent = '';
    const sources = researchResult.sources || [];
    const sourceMap = new Map(sources.map(source => [source.source_id, source]));
    (researchResult.findings || []).forEach(finding => {
      const item = add('li', typeof finding === 'string' ? finding : finding.statement || '', el('idea-findings'));
      (finding.source_ids || []).forEach(id => { const source = sourceMap.get(id); if (source) { const reference = add('span', ' ', item); safeSourceLink(source, reference); } });
    });
    el('idea-research-sources').textContent = '';
    sources.forEach(source => safeSourceLink(source, add('li', '', el('idea-research-sources'))));
    if (!sources.length) add('li', 'No confirmed public sources were returned.', el('idea-research-sources'));
    el('idea-research-uncertainties').textContent = '';
    const uncertainties = researchResult.uncertainties || [];
    uncertainties.forEach(item => add('li', typeof item === 'string' ? item : item.description || item.question || '', el('idea-research-uncertainties')));
    if (!uncertainties.length) add('li', 'No additional uncertainties were listed. Company facts still need your Knowledge Bank review.', el('idea-research-uncertainties'));
    el('idea-evidence-count').textContent = `${sources.length} sources · ${uncertainties.length} open questions`;
    if (researchResult.proposed_purpose) el('owner-purpose').value = researchResult.proposed_purpose;
    const needsIdentity = researchResult.identity_status === 'AMBIGUOUS';
    el('idea-company-resolution').hidden = !needsIdentity;
    el('idea-resolved-company').required = needsIdentity;
    el('idea-resolved-website').required = needsIdentity;
    el('idea-resolved-company').value = needsIdentity ? '' : draft.fields.client_name || '';
    el('idea-resolved-website').value = needsIdentity ? '' : draft.website || '';
    el('idea-identity-explanation').textContent = 'More than one company could match. Confirm the company name and website you mean before using this direction.';
    el('idea-company-candidates').textContent = '';
    (researchResult.company_candidates || []).forEach(candidate => { const item = add('li', candidate.name || 'Company candidate', el('idea-company-candidates')); if (candidate.website) { add('span', ' · ', item); safeSourceLink({url: candidate.website, title: candidate.website}, item); } });
    if (job.recommendation) fillRoleChoices(job.recommendation, roles, roleChosenByOwner ? selectedRoleId : '');
    else await refreshRoles();
    el('idea-manual-role').hidden = true;
    el('research-idea').textContent = 'Research again';
    el('use-idea').textContent = 'Continue without these findings';
    el('resume-idea-research').hidden = true;
    el('idea-research-status').textContent = 'Research is ready. Review the proposed direction below; no Knowledge Bank facts have been approved.';
  }

  async function pollResearch(initial) {
    const generation = ++pollGeneration;
    let job = initial;
    while (generation === pollGeneration) {
      researchJob = job; renderProgress(job);
      const state = jobState(job);
      if (state === 'needs_review') { await showResearchResult(job); return; }
      if (state === 'failed' || state === 'cancelled') {
        el('idea-job-error').textContent = typeof job.error === 'string' ? job.error : job.error?.message || job.failure_message || 'The research request ended without a reviewable result.';
        el('research-idea').textContent = 'Try research again'; return;
      }
      if (!['queued', 'running'].includes(state)) throw new Error('Research returned an unknown status. Check the saved request before starting anything new.');
      await pause(1800);
      if (generation !== pollGeneration) return;
      job = await api(`/api/idea-research/${encodeURIComponent(job.job_id)}`);
    }
  }

  function researchError(error) {
    el('idea-research-panel').hidden = false; el('idea-job-error').textContent = error.message;
    el('idea-job-status').textContent = researchJob?.job_id
      ? 'The connection needs attention. The saved research may still be running. Check its progress to reconnect.'
      : 'A research result could not be confirmed. Your brief is saved; review the issue before trying again.';
    el('resume-idea-research').hidden = !researchJob?.job_id;
  }

  async function startResearch() {
    if (busy || !draft) return;
    if (globalThis.PreparedAgent) {
      setBusy(true); el('idea-error').textContent = '';
      try { await saveEdits(); await PreparedAgent.start(draft); }
      catch(error) { el('idea-error').textContent = error.message; }
      finally { setBusy(false); }
      return;
    }
    // This branch is reached only by an owner click. Terminal jobs remain
    // immutable; an explicit new run gets a fresh draft and a fresh job slot.
    const ownerRequestedAnotherRun = ['needs_review', 'failed', 'cancelled'].includes(jobState(researchJob));
    setBusy(true); el('idea-job-error').textContent = ''; el('idea-error').textContent = '';
    try {
      await saveEdits({forceNew: ownerRequestedAnotherRun}); resetResearch();
      el('idea-research-panel').hidden = false;
      el('idea-job-status').textContent = 'Starting the research request…';
      el('research-idea').textContent = 'Research is running…';
      const job = await api(`/api/ideas/${encodeURIComponent(draft.idea_id)}/research-jobs`, {owner_requested: true, draft_sha256: draft.draft_sha256});
      researchJob = job;
      try { localStorage.setItem('x-factory-last-idea-research', JSON.stringify({idea_id: draft.idea_id, job_id: job.job_id})); } catch (_) { /* Server state remains authoritative. */ }
      await pollResearch(job);
    } catch (error) { researchError(error); }
    finally { setBusy(false); if (el('research-idea').textContent === 'Research is running…') el('research-idea').textContent = 'Research & recommend a role →'; }
  }

  async function resumeResearch() {
    if (busy || !researchJob?.job_id) return;
    setBusy(true); el('idea-job-error').textContent = ''; el('resume-idea-research').hidden = true;
    try { await pollResearch(await api(`/api/idea-research/${encodeURIComponent(researchJob.job_id)}`)); }
    catch (error) { researchError(error); }
    finally { setBusy(false); }
  }

  async function finishApply(acceptedDraft, knowledge) {
    appliedBinding = knowledge ? {packageId: knowledge.package.package_id, company: acceptedDraft.fields.client_name, purpose: acceptedDraft.fields.purpose} : null;
    await callbacks.applyDraft(acceptedDraft, knowledge, {selectedRole: selectedRole()});
    draft = acceptedDraft;
    el('idea-next-actions').hidden = true; el('idea-start-panel').hidden = true; el('idea-manual-role').hidden = true;
    el('idea-research-panel').hidden = true; el('idea-direction-review').hidden = true;
    el('idea-resolved-company').required = false; el('idea-resolved-website').required = false;
    el('purpose-form').hidden = false; el('manual-purpose-actions').hidden = false;
    try { localStorage.setItem('x-factory-last-idea', draft.idea_id); } catch (_) { /* Browser storage is optional. */ }
  }

  async function useDraft() {
    if (busy || !draft) return;
    if (!selectedRole()) { el('idea-error').textContent = 'Choose a starting role before personalizing.'; return; }
    el('idea-error').textContent = ''; setBusy(true);
    try { await saveEdits(); await finishApply(draft, null); }
    catch (error) { el('idea-error').textContent = error.message; }
    finally { setBusy(false); }
  }

  async function acceptResearch() {
    if (busy || !draft || !researchResult || !researchJob) return;
    el('idea-job-error').textContent = '';
    if (!el('owner-purpose').reportValidity()) return;
    if (!selectedRole()) { el('idea-job-error').textContent = 'Choose a suitable starting role before using this direction.'; return; }
    const resolveIdentity = !el('idea-company-resolution').hidden;
    if (resolveIdentity && (!el('idea-resolved-company').reportValidity() || !el('idea-resolved-website').reportValidity())) return;
    setBusy(true);
    try {
      const payload = {owner_requested: true, job_id: researchJob.job_id, result_sha256: researchJob.result_sha256,
        draft_sha256: draft.draft_sha256, purpose: el('owner-purpose').value.trim(), selected_chassis_id: selectedRoleId};
      if (resolveIdentity) { payload.company_name = el('idea-resolved-company').value.trim(); payload.website = el('idea-resolved-website').value.trim(); }
      const reviewed = await api(`/api/ideas/${encodeURIComponent(draft.idea_id)}/research-review`, payload);
      if (!reviewed.draft) throw new Error('The reviewed draft was not returned. The direction has not been applied.');
      await finishApply(reviewed.draft, reviewed.research || null);
    } catch (error) { el('idea-job-error').textContent = error.message; }
    finally { setBusy(false); }
  }

  function bindingMismatch(packageId) {
    return Boolean(appliedBinding && appliedBinding.packageId === packageId &&
      (el('commission-client-name').value.trim() !== appliedBinding.company || el('owner-purpose').value.trim() !== appliedBinding.purpose));
  }

  function showManual() {
    el('purpose-form').hidden = false;
    el('manual-purpose-actions').hidden = false;
    el('idea-next-actions').hidden = true;
    el('idea-manual-role').hidden = true; el('idea-start-role').disabled = true;
    el('idea-research-panel').hidden = true; el('idea-role-choice').disabled = true;
    el('idea-resolved-company').required = false; el('idea-resolved-website').required = false;
  }
  function returnToStart(){
    if(el('prepared-agent'))el('prepared-agent').hidden=true;
    switchMode('idea');
    el('commissioning-form').hidden=true;
    el('purpose-form').hidden=true;
    el('chassis-depot').scrollIntoView({behavior:'auto',block:'start'});
    el('idea-seed').focus({preventScroll:true});
  }

  function mount(options) {
    callbacks = options;
    const manual=add('details','',el('idea-next-actions'));add('summary','Advanced · manual setup instead',manual);
    add('p','This skips research, Aria, OMNARA and Troy. You must supply your own knowledge and configuration.',manual);manual.append(el('use-idea'));
    const sources=add('section','',el('idea-start-form'));sources.className='idea-extra';
    el('idea-start-form').insertBefore(sources,el('prepare-idea').parentNode);
    add('h3','Add source files or an image reference',sources);
    add('p','Up to four TXT, MD, CSV, JSON or YAML documents (24 KB total text). Images use your written description—not automatic image reading. Nothing is approved. Text and descriptions go to the specialists only when you choose Prepare my agent.',sources);
    const picker=add('input','',sources);picker.type='file';picker.multiple=true;picker.accept='.txt,.md,.csv,.json,.yaml,.yml,.png,.jpg,.jpeg,.webp';picker.id='idea-source-files';picker.setAttribute('aria-label','Idea source attachments');
    const list=add('div','',sources);
    function changed(){draft=null;el('idea-next-actions').hidden=true;el('idea-result').hidden=true;el('idea-error').textContent='Source material changed. Choose Shape my idea to save the updated brief.';syncActions();}
    function draw(){list.replaceChildren();attachments.forEach((a,i)=>{
      const row=add('div','',list);add('strong',a.name,row);
      if(a.image){const image=add('img','',row);image.src='data:image/jpeg;base64,'+a.image;image.alt='Owner-supplied reference';image.style.maxWidth='180px';}
      const label=add('label',a.image?'Describe the image for the specialists (required; no OCR)':'Source text (unapproved)',row);
      const text=add('textarea','',label);text.rows=3;text.maxLength=12000;text.value=a.text;text.addEventListener('input',()=>{a.text=text.value;changed();});
      const remove=add('button','Remove attachment',row);remove.type='button';remove.onclick=()=>{attachments.splice(i,1);draw();changed();};
    });}
    picker.addEventListener('change',async()=>{
      try{if(busy)return;if(attachments.length+picker.files.length>4)throw Error('Attach up to four files.');
        const pending=[];
        for(const file of picker.files){
          const name=file.name.replace(/[^\w .()-]/g,'_').slice(0,100);
          if(/\.(png|jpe?g|webp)$/i.test(name)){
            if(file.size>8*1024*1024)throw Error('Use an image under 8 MB.');
            const bitmap=await createImageBitmap(file);try{
              const canvas=document.createElement('canvas'),scale=Math.min(1,320/Math.max(bitmap.width,bitmap.height));canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);
              const image=canvas.toDataURL('image/jpeg',.55).split(',')[1];if(image.length>14000)throw Error('Use a simpler or smaller image reference.');pending.push({name,text:'',image});
            }finally{bitmap.close();}
          }else{
            if(!/\.(txt|md|csv|json|ya?ml)$/i.test(name))throw Error('Unsupported document. Export it as TXT or MD first.');
            if(file.size>24000)throw Error('Use a source excerpt under 24 KB.');
            const text=await file.text();if(text.includes('\u0000')||text.includes('\ufffd'))throw Error('Use a UTF-8 text document.');pending.push({name,text});
          }
        }
        const combined=[...attachments,...pending];if(new TextEncoder().encode(JSON.stringify(combined)).length>36000)throw Error('Combined attachments are too large. Use shorter text or fewer images.');
        attachments=combined;draw();changed();
      }catch(e){el('idea-error').textContent=e.message;}finally{picker.value='';}
    });
    el('idea-start-form').addEventListener('submit', prepare);
    el('research-idea').addEventListener('click', startResearch);
    el('use-idea').addEventListener('click', useDraft);
    el('accept-idea-research').addEventListener('click', acceptResearch);
    el('resume-idea-research').addEventListener('click', resumeResearch);
    el('refresh-idea-roles').addEventListener('click', async () => {
      if (busy) return; setBusy(true);
      try { await refreshRoles(); } catch (error) { el('idea-start-role-reason').textContent = error.message; }
      finally { setBusy(false); }
    });
    ['idea-start-role', 'idea-role-choice'].forEach(id => el(id).addEventListener('change', () => {
      selectedRoleId = el(id).value; roleChosenByOwner = true;
      el('idea-start-role').value = selectedRoleId; el('idea-role-choice').value = selectedRoleId;
      explainSelectedRole();
      syncActions();
    }));
    document.querySelectorAll('[data-entry-mode]').forEach(b => b.addEventListener('click', () => switchMode(b.dataset.entryMode)));
    ['idea-seed', 'idea-company', 'idea-website', 'idea-post-text'].forEach(id => el(id).addEventListener('input', () => {
      if (!draft) return;
      draft = null; resetResearch(); selectedRoleId = ''; roleChosenByOwner = false;
      el('idea-result').hidden = true; el('idea-next-actions').hidden = true; el('idea-manual-role').hidden = true;
      el('idea-error').textContent = 'Your starting information changed. Choose “Shape my idea” to update the draft.';
      syncActions();
    }));
    el('owner-purpose').addEventListener('input', () => { if (draft && !researchResult) el('idea-start-role-reason').textContent = 'The brief changed. Choose “Check role fit” to compare the updated job, or keep your chosen role.'; });
    el('commission-client-name').addEventListener('input', () => callbacks.updateBuildState());
    document.querySelectorAll('[data-studio-target]').forEach(b => b.addEventListener('click', () => {
      if (busy) return;
      document.querySelectorAll('[data-studio-target]').forEach(n => n.classList.toggle('selected', n === b));
      const target = b.dataset.studioTarget;
      el('studio-recent').hidden = target !== 'recent';
      if (target === 'create' || target === 'hunter') {
        if(el('prepared-agent'))el('prepared-agent').hidden=true;
        switchMode(target === 'hunter' ? 'hunter' : 'idea');
        el('chassis-depot').scrollIntoView({behavior: 'smooth', block: 'start'});
        if (target === 'create') el('idea-seed').focus({preventScroll: true});
      } else {
        const node = el(target === 'crew' ? 'studio-crew' : 'studio-recent');
        if (node.tagName === 'DETAILS') node.open = true;
        node.scrollIntoView({behavior: 'smooth', block: 'start'});
      }
    }));
    // A saved draft is offered explicitly; reloading never replaces an active form.
    let saved; try { saved = localStorage.getItem('x-factory-last-idea'); } catch (_) { /* storage optional */ }
    if (saved && /^idea-[a-z0-9-]+$/.test(saved)) {
      const resume = add('button', 'Reopen my last idea', el('idea-start-form')); resume.type = 'button'; resume.className = 'idea-resume';
      resume.addEventListener('click', async () => {
        if (busy) return;
        setBusy(true);
        try {
          const result = await api(`/api/ideas/${encodeURIComponent(saved)}`);
          attachments=result.attachments||[];draw();
          el('idea-seed').value = result.seed || result.input?.seed || result.fields.purpose;
          el('idea-company').value = result.input?.company_name || result.fields.client_name || '';
          el('idea-website').value = result.website || '';
          el('idea-post-text').value = result.post_text || result.input?.post_text || '';
          await showDraft(result);
          let lastJob; try { lastJob = JSON.parse(localStorage.getItem('x-factory-last-idea-research') || 'null'); } catch (_) { /* Ignore malformed optional browser state. */ }
          if (lastJob?.idea_id === draft.idea_id && typeof lastJob.job_id === 'string') {
            researchJob = {job_id: lastJob.job_id}; el('idea-research-panel').hidden = false;
            el('idea-job-status').textContent = 'This idea has a saved research request. Check progress to reopen it.';
            el('resume-idea-research').hidden = false;
          }
        } catch (error) { el('idea-error').textContent = error.message; }
        finally { setBusy(false); }
      });
    }
    switchMode('idea'); syncActions();
  }
  globalThis.IdeaStart = {mount, showManual, returnToStart, bindingMismatch, selectedRole, isBusy: () => busy, resetBinding: () => { appliedBinding = null; }};
})();
