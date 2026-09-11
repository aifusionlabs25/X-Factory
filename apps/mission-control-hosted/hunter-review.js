/* Research is rendered as text, never HTML or executable instructions. */
(() => {
  const fieldSpec = [
    ['purpose', 'System Prompt Brief — What should this X-Agent do?', 2000, 10, true],
    ['x_agent_name', 'X-Agent name — you choose', 80, 2],
    ['client_name', 'Client or company — confirm identity', 160, 2],
    ['target_users', 'Who will use this?', 1000, 2],
    ['personality', 'Personality and communication style', 1000, 2],
    ['additional_requirements', 'Proposed jobs — review and edit', 3000, 1, true],
    ['additional_boundaries', 'Boundaries — keep exclusions; add any others', 3000, 1, true],
  ];

  async function api(path, payload) {
    const response = await fetch(path, payload ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)} : {cache: 'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Hunter review is unavailable.');
    return result;
  }

  function mount({applyDraft}) {
    const el = id => document.getElementById(id);
    const text = (tag, value, parent) => { const node = document.createElement(tag); node.textContent = value; parent.append(node); return node; };
    let loaded = false, sourceId = '', review = null, selection = 0, busy = false;
    el('hunter-review').addEventListener('toggle', async () => {
      if (!el('hunter-review').open || loaded) return;
      loaded = true;
      try {
        const result = await api('/api/hunter/prospects');
        sourceId = result.source_id;
        el('hunter-notice').textContent = result.notice;
        for (const p of result.prospects) {
          const option = text('option', `${p.company_name}${p.blockers.length ? ' — HOLD' : ''}${p.already_reviewed ? ' — draft already reviewed' : ''}`, el('hunter-prospect'));
          option.value = p.prospect_id;
        }
      } catch (error) { loaded = false; el('hunter-error').textContent = error.message; }
    });
    el('hunter-prospect').addEventListener('change', async () => {
      const token = ++selection;
      review = null;
      el('hunter-review-form').hidden = true;
      el('hunter-error').textContent = '';
      if (!el('hunter-prospect').value) return;
      try {
        const result = await api('/api/hunter/review', {source_id: sourceId, prospect_id: el('hunter-prospect').value});
        if (token !== selection) return;
        review = result;
        const p = result.snapshot.original_prospect;
        const research = el('hunter-research'); research.textContent = '';
        text('h3', `${p.company_name} · research only`, research);
        text('p', `${p.location} · Historical score: ${p.overall_score}/100. ${p.score_rationale}`, research);
        text('p', p.why_hunter_selected, research);
        const sources = text('div', '', research);
        for (const s of p.public_sources) {
          const row = text('p', `${s.observed_on} · ${s.title} — ${s.claim} `, sources);
          // Deliberately plain text: importing does not fetch/open external URLs.
          text('code', s.url, row);
        }
        const more = text('details', '', research);
        text('summary', 'Research context, unknowns and original proposals', more);
        text('p', p.factory_intake_brief.anything_else_about_company, more);
        text('p', `Scope exclusions: ${p.intentionally_not_included.join('; ')}`, more);
        text('p', `Unverified technical readiness: ${(p.technical_readiness?.blockers || []).join('; ') || 'No live integrations certified by import.'}`, more);
        text('p', p.factory_intake_brief.knowledge_direction_only, more);
        text('pre', JSON.stringify(p, null, 2), more);
        const fields = el('hunter-fields'); fields.textContent = '';
        for (const [key, label, max, min, multiline] of fieldSpec) {
          const wrapper = text('label', label, fields);
          const input = document.createElement(multiline ? 'textarea' : 'input');
          input.id = `hunter-field-${key}`; input.required = true; input.maxLength = max; input.minLength = min;
          if (multiline) input.rows = key === 'purpose' ? 7 : 3;
          input.value = result.fields[key]; wrapper.append(input);
        }
        el('hunter-role').textContent = '';
        const blank = text('option', 'Choose a proven role…', el('hunter-role')); blank.value = '';
        const role = text('option', `${result.chassis.role_title} · ${result.chassis.version}`, el('hunter-role')); role.value = result.chassis.chassis_sha256;
        el('hunter-presence').value = '';
        el('hunter-appearance-hint').textContent = `Hunter suggested ${result.suggested_appearance}. Nothing is selected or activated.`;
        el('hunter-confirm').checked = false;
        el('hunter-replace').checked = false;
        el('hunter-apply').disabled = result.blockers.length > 0;
        el('hunter-apply').textContent = result.already_reviewed ? 'REOPEN SAVED DRAFT →' : 'USE REVIEWED DRAFT →';
        if (result.already_reviewed) {
          const saved = await api('/api/hunter/reopen-draft', {source_id: sourceId, prospect_id: p.prospect_id});
          if (token !== selection) return;
          for (const [key] of fieldSpec) { el(`hunter-field-${key}`).value = saved.fields[key]; el(`hunter-field-${key}`).readOnly = true; }
          el('hunter-role').value = saved.chassis.chassis_sha256;
          el('hunter-presence').value = saved.fields.presence_mode;
        }
        el('hunter-role').disabled = result.already_reviewed;
        el('hunter-presence').disabled = result.already_reviewed;
        el('hunter-result').textContent = result.already_reviewed ? 'Saved review shown read-only. Reopen it to continue in the Factory form; the receipt will not be overwritten.' : 'Saves a review receipt and fills the form only. Build remains a separate decision.';
        el('hunter-error').textContent = result.blockers.join(' ');
        el('hunter-review-form').hidden = false;
      } catch (error) { if (token === selection) el('hunter-error').textContent = error.message; }
    });
    el('hunter-review-form').addEventListener('submit', async event => {
      event.preventDefault();
      if (!review || busy || review.blockers.length || !el('hunter-confirm').checked || !el('hunter-replace').checked) return;
      if (!el('hunter-review-form').reportValidity()) return;
      const fields = Object.fromEntries(fieldSpec.map(([key]) => [key, el(`hunter-field-${key}`).value.trim()]));
      fields.presence_mode = el('hunter-presence').value;
      busy = true; el('hunter-apply').disabled = true; el('hunter-prospect').disabled = true;
      el('hunter-error').textContent = '';
      try {
        const result = review.already_reviewed
          ? await api('/api/hunter/reopen-draft', {source_id: sourceId, prospect_id: review.snapshot.prospect_id})
          : await api('/api/hunter/accept-draft', {source_id: sourceId, prospect_id: review.snapshot.prospect_id,
            snapshot_sha256: review.snapshot_sha256, chassis_sha256: el('hunter-role').value, fields, owner_confirmed: true});
        review.already_reviewed = true;
        applyDraft(result);
        el('hunter-result').textContent = `Draft ready for ${fields.x_agent_name}. No build, Knowledge Bank approval or outreach occurred. Review receipt: ${result.review_id.slice(0, 12)}.`;
      } catch (error) { el('hunter-error').textContent = error.message; }
      finally { busy = false; el('hunter-prospect').disabled = false; el('hunter-apply').disabled = Boolean(review?.already_reviewed); }
    });
  }
  globalThis.HunterReview = {mount};
})();
