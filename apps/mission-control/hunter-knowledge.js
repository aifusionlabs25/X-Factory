/* Optional public-source preparation. Loading a plan is read-only. */
(() => {
  const el = id => document.getElementById(id);
  const add = (tag, value, parent) => { const n = document.createElement(tag); n.textContent = value; parent.append(n); return n; };
  let plan = null, generation = 0, busy = false, prepared = null, callbacks;
  async function api(path, payload) {
    const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Knowledge preparation stopped. No facts were approved.');
    return result;
  }
  function reset() {
    generation++; plan = null; prepared = null;
    el('hunter-knowledge').hidden = true;
    el('hunter-knowledge-outline').textContent = '';
    el('hunter-knowledge-review').hidden = true;
  }
  function matchesForm() {
    return plan && el('commission-client-name').value.trim() === plan.fields.client_name &&
      el('owner-purpose').value.trim() === plan.fields.purpose;
  }
  function checkIdentity() {
    if (!plan || busy) return;
    el('prepare-hunter-knowledge').disabled = !matchesForm();
    el('hunter-knowledge-drift').hidden = matchesForm();
    callbacks.afterBusy();
  }
  async function load(result) {
    reset();
    const token = generation;
    el('hunter-knowledge').hidden = false;
    el('hunter-knowledge-status').textContent = 'Connecting your reviewed Hunter draft to Knowledge Bank preparation…';
    el('prepare-hunter-knowledge').disabled = true;
    el('hunter-knowledge-sources').textContent = '';
    el('hunter-knowledge-drift').hidden = true;
    try {
      const response = await api('/api/hunter/knowledge-plan', {source_id: result.source_id, prospect_id: result.prospect_id});
      if (generation !== token) return;
      plan = response;
      el('hunter-knowledge-company').textContent = plan.fields.client_name;
      el('hunter-knowledge-job').textContent = plan.fields.purpose;
      for (const source of plan.sources) {
        const row = add('p', source.observed_on ? `Hunter noted this on ${source.observed_on}: ` : 'Company website: ', el('hunter-knowledge-sources'));
        add('code', source.url, row);
      }
      for (const source of plan.excluded_sources) add('p', `Not included: ${source.url} — ${source.reason}`, el('hunter-knowledge-sources'));
      add('p', plan.research_direction, el('hunter-knowledge-sources'));
      el('hunter-knowledge-status').textContent = 'Ready to prepare. No websites have been visited by this step yet. Your click below authorizes public capture and extraction—not approval of facts.';
      checkIdentity();
    } catch (error) { if (generation === token) el('hunter-knowledge-status').textContent = error.message; }
  }
  function describe(packageId) {
    if (!prepared || prepared.package.package_id !== packageId) return '';
    return 'Prepared from Hunter’s source links. Check each fact against the company and the agent’s job. Missing sections are listed above; this draft is not a completeness guarantee.';
  }
  function mount(options) {
    callbacks = options;
    ['commission-client-name', 'owner-purpose'].forEach(id => el(id).addEventListener('input', checkIdentity));
    el('hunter-knowledge-review').addEventListener('click', () => { if (prepared) callbacks.openReview(prepared.package.package_id); });
    el('prepare-hunter-knowledge').addEventListener('click', async () => {
      if (busy || !matchesForm()) return;
      const token = generation;
      busy = true;
      // Prevent switching company, approving old facts or building mid-capture.
      const controls = [...document.querySelectorAll('button, input, select, textarea')].map(n => [n, n.disabled]);
      controls.forEach(([n]) => { n.disabled = true; });
      el('hunter-knowledge-status').textContent = 'Reading up to six public company pages and preparing source-linked draft facts. No model calls, build or outreach.';
      try {
        const result = await api('/api/hunter/prepare-knowledge', {source_id: plan.source_id, prospect_id: plan.prospect_id,
          plan_sha256: plan.plan_sha256, owner_requested: true});
        if (token !== generation) return;
        prepared = result;
        const outline = el('hunter-knowledge-outline'); outline.textContent = '';
        add('h5', 'Your draft Knowledge Bank', outline);
        const list = add('ul', '', outline);
        for (const section of result.outline) add('li', `${section.title} — ${section.entry_ids.length ? `${section.entry_ids.length} proposed fact${section.entry_ids.length === 1 ? '' : 's'} to review` : 'needs your information; nothing invented'}`, list);
        add('p', 'These are draft sections, not a completeness guarantee. You decide which facts belong. OMNARA packages approved files when you later choose Build.', outline);
        const skipped = result.package.website_capture.skipped_pages?.length || 0;
        const skipNote = skipped ? ` · ${skipped} broken discovered link${skipped === 1 ? '' : 's'} skipped and recorded` : '';
        el('hunter-knowledge-status').textContent = `${result.package.website_capture.pages.length} public pages captured${skipNote} · ${result.compilation.entries.length} draft facts · review required. Hunter’s research claims were not copied into these facts.`;
        el('hunter-knowledge-review').hidden = false;
        await callbacks.acceptPreparation(result);
      } catch (error) {
        if (token === generation) el('hunter-knowledge-status').textContent = `Preparation stopped — ${error.message} No Knowledge Bank facts were approved. You can use approved documents or paste verified facts below.`;
      } finally {
        busy = false;
        controls.forEach(([n, disabled]) => { n.disabled = disabled; });
        checkIdentity(); callbacks.afterBusy();
      }
    });
  }
  globalThis.HunterKnowledge = {mount, load, reset, describe, isBusy: () => busy,
    boundPackage: () => prepared?.package.package_id,
    selectionMismatch: id => Boolean(prepared && prepared.package.package_id === id && !matchesForm()),
    markReviewed: (id, count) => {
      if (prepared?.package.package_id === id) el('hunter-knowledge-status').textContent = `${count} facts approved by you and selected for this build. Missing sections remain open; Build is still a separate action.`;
    }};
})();
