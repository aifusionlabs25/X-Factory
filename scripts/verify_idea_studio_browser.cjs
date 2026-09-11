/* Browser regression. Python companion provides isolated, synthetic sources. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.STUDIO_TEST_URL;
if (!base || process.env.STUDIO_TEST_ISOLATED !== '1') throw new Error('Run through verify_idea_studio_browser.py; never against a live workspace.');

(async () => {
  const options = {headless: true};
  if (process.env.STUDIO_TEST_CHROMIUM) options.executablePath = process.env.STUDIO_TEST_CHROMIUM;
  const browser = await chromium.launch(options);
  const out = path.resolve('outputs/studio-qa-2026-09-04/async-rd-roles');
  fs.mkdirSync(out, {recursive: true});
  const errors = [], posts = [], interceptedBuilds = [], externalRequests = [];
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== base) {
      externalRequests.push(url.origin);
      return route.abort('blockedbyclient');
    }
    if (request.method() === 'POST' && /\/api\/chassis\/[^/]+\/commission$/.test(url.pathname)) {
      interceptedBuilds.push({path: url.pathname, payload: request.postDataJSON()});
      return route.fulfill({status: 409, contentType: 'application/json', body: JSON.stringify({error: 'Synthetic regression captured the selected role; no build was executed.'})});
    }
    return route.continue();
  });
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (request.method() === 'POST') posts.push(new URL(request.url()).pathname); });
  const checkNoOverflow = async label => {
    const overflow = await page.evaluate(() => [...document.querySelectorAll('body *')].filter(el => {
      const rect = el.getBoundingClientRect(); return rect.width && (rect.right > innerWidth + 1 || rect.left < -1);
    }).map(el => ({tag: el.tagName, id: el.id, cls: el.className, right: Math.round(el.getBoundingClientRect().right), width: Math.round(el.getBoundingClientRect().width)})).slice(0, 18));
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), label + ': page overflows ' + JSON.stringify(overflow));
  };
  try {
    await page.goto(base, {waitUntil: 'networkidle'});
    if(process.env.STUDIO_LEGACY_FLOW==='1')await page.evaluate(()=>{delete globalThis.PreparedAgent;});
    await page.screenshot({path: path.join(out, 'studio-desktop.png'), fullPage: true});
    console.log(JSON.stringify({title: await page.title(), visibleButtons: await page.locator('button:visible').allTextContents(), pageErrors: errors}));
    if (process.env.STUDIO_INSPECT_ONLY) return;
    const blocked = await page.request.post(base + '/api/ideas/prepare', {headers: {Origin: 'https://untrusted.example'}, data: {seed: 'An unauthorized cross-site draft'}});
    assert.equal(blocked.status(), 403, 'Cross-site draft creation must be blocked');
    assert(await page.locator('#idea-start-panel').isVisible());
    assert(!await page.locator('#hunter-inbox').isVisible());
    assert(!await page.locator('#purpose-form').isVisible());
    await checkNoOverflow('desktop');
    await page.locator('#idea-seed').fill('An agent for a pet boarding company that answers questions and gathers booking requests for staff review.');
    await page.locator('#prepare-idea').click();
    await page.locator('#idea-result').waitFor({state: 'visible'});
    await page.waitForFunction(() => document.querySelectorAll('#idea-start-role option[value]:not([value=""])').length === 7);
    assert.equal(await page.locator('#idea-start-role option:not([value=""])').count(), 7, 'All seven starting roles must be available');
    assert.match(await page.locator('#owner-purpose').inputValue(), /pet boarding/i);
    const purpose = 'Help pet boarding customers prepare a stay request for human review. Do not confirm a booking or invent prices.';
    await page.locator('#owner-purpose').fill(purpose);
    await page.locator('#idea-start-role').selectOption('role-reception-intake');
    await page.locator('#use-idea').click();
    await page.locator('#commissioning-form').waitFor({state: 'visible'});
    assert.equal(await page.locator('#owner-purpose').inputValue(), purpose);
    assert.equal(await page.locator('#commission-agent-name').inputValue(), '');
    assert.equal(await page.locator('#commissioning-chassis-id').inputValue(), 'role-reception-intake', 'Manual role choice must survive opening personalization');
    assert(!posts.some(route => /missions|commission/.test(route)), 'Intake must not build');
    await page.reload({waitUntil: 'networkidle'});
    await page.getByRole('button', {name: 'Reopen my last idea', exact: true}).click();
    await page.locator('#idea-result').waitFor({state: 'visible'});
    assert.equal(await page.locator('#owner-purpose').inputValue(), purpose, 'Resume preserves edited brief');
    await page.waitForFunction(() => document.querySelector('#idea-start-role').value === 'role-reception-intake');

    // An unrelated creative job must not silently become a concierge.
    await page.locator('#owner-purpose').fill('Write sonnets about interstellar cartography and imaginary nebulae.');
    await page.locator('#idea-start-role').selectOption('');
    const nofitReply = page.waitForResponse(response => response.url().endsWith('/api/roles/recommend'));
    await page.locator('#refresh-idea-roles').click();
    assert.equal((await (await nofitReply).json()).recommended, null, 'No-fit must be explicit');
    await page.waitForFunction(() => document.querySelector('#idea-start-role').value === '');
    assert(await page.locator('#use-idea').isDisabled(), 'No-fit must require an owner role choice');
    assert.match(await page.locator('#idea-start-role-reason').textContent(), /no|fit|choose/i);
    await page.screenshot({path: path.join(out, 'studio-no-fit.png'), fullPage: true});

    await page.locator('[data-entry-mode="website"]').click();
    await page.locator('#idea-seed').fill('A home-services concierge idea from https://x.com/example/status/12345');
    await page.locator('.idea-extra summary').click();
    await page.locator('#idea-company').fill('Studio Test Services');
    await page.locator('#idea-website').fill('https://example.com/');
    await page.locator('#idea-post-text').fill('Homeowners need a simple way to ask service questions after hours.');
    await page.locator('#prepare-idea').click();
    await page.locator('#idea-result').waitFor({state: 'visible'});
    assert.match(await page.locator('#owner-purpose').inputValue(), /Homeowners need/);
    const researchReply = page.waitForResponse(response => /\/api\/ideas\/[^/]+\/research-jobs$/.test(response.url()));
    await page.locator('#research-idea').click();
    const job = await (await researchReply).json();
    assert.match(job.status, /QUEUED|RUNNING/);
    await page.locator('#idea-research-panel').waitFor({state: 'visible'});
    assert(await page.locator('#use-idea').isDisabled(), 'Running research must not apply incomplete findings');
    await page.locator('#idea-direction-review').waitFor({state: 'visible', timeout: 30000});
    assert.match(await page.locator('#idea-evidence-count').textContent(), /1 source/);
    assert.match(await page.locator('#idea-findings').textContent(), /water heaters/);
    await page.locator('summary').filter({hasText: 'Sources and open questions'}).click();
    assert.equal(await page.locator('#idea-research-sources a').first().getAttribute('href'), 'https://example.com/');
    assert.match(await page.locator('#idea-research-uncertainties').textContent(), /coverage and pricing/);
    assert(!posts.some(route => /missions|commission|\/approve$|\/compile$|\/review$|website-knowledge/.test(route)), 'R&D must not capture approved knowledge or build');
    assert.equal((await (await page.request.get(base + '/api/knowledge-packages')).json()).packages.length, 0, 'R&D findings are not knowledge files');
    await checkNoOverflow('research desktop');
    await page.screenshot({path: path.join(out, 'studio-research-review.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('#idea-direction-review').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(out, 'studio-research-mobile.png'), fullPage: true});
    await page.screenshot({path: path.join(out, 'studio-research-mobile-viewport.png')});
    await checkNoOverflow('research mobile');
    await page.setViewportSize({width: 1440, height: 1000});

    // Choose a different available role, then accept direction only.
    await page.locator('#idea-role-choice').selectOption('role-reception-intake');
    const directionReply = page.waitForResponse(response => /\/api\/ideas\/[^/]+\/research-review$/.test(response.url()));
    await page.locator('#accept-idea-research').click();
    const reviewed = await (await directionReply).json();
    assert.equal(reviewed.review.knowledge_approved, false);
    assert.equal(reviewed.review.mission_created, false);
    assert.equal(reviewed.review.selected_chassis_id, 'role-reception-intake');
    await page.locator('#commissioning-form').waitFor({state: 'visible'});
    assert.equal(await page.locator('#commission-client-name').inputValue(), 'Studio Test Services');
    assert.equal(await page.locator('#commissioning-chassis-id').inputValue(), 'role-reception-intake');
    assert.equal(await page.locator('#website-knowledge-url').inputValue(), 'https://example.com/');
    assert(!await page.locator('#knowledge-review-desk').isVisible(), 'Direction acceptance must not approve facts');
    assert.equal((await (await page.request.get(base + '/api/knowledge-packages')).json()).packages.length, 0);

    // Company facts use the existing, separate capture/review boundary.
    await page.locator('#capture-website-knowledge').click();
    await page.locator('#review-website-knowledge').waitFor({state: 'visible'});
    assert(await page.locator('#run-commissioning').isDisabled(), 'Captured but unreviewed pages pause build');
    await page.locator('#review-website-knowledge').click();
    await page.locator('#knowledge-review-desk').waitFor({state: 'visible', timeout: 30000});
    assert.match(await page.locator('#review-desk-summary').textContent(), /propos/i);
    assert(!posts.some(route => /missions|commission|\/compilation\/review$/.test(route)), 'Source preparation must not approve facts or build');
    assert.equal(await page.locator('#knowledge-review-entries input:checked').count(), 0, 'Website facts start unselected');
    assert(await page.locator('#run-commissioning').isDisabled(), 'Unreviewed facts must block build');
    await page.screenshot({path: path.join(out, 'studio-fact-review.png'), fullPage: true});
    await page.locator('#review-safe-defaults').click();
    await page.locator('#finalize-knowledge-review').click();
    await page.locator('#knowledge-review-desk').waitFor({state: 'hidden'});
    await page.waitForFunction(() => !document.querySelector('#run-commissioning').disabled);
    await page.locator('#commission-agent-name').fill('Ava Studio Test');
    const buildReply = page.waitForResponse(response => /\/api\/chassis\/[^/]+\/commission$/.test(response.url()));
    await page.locator('#run-commissioning').click();
    await buildReply;
    assert.equal(interceptedBuilds.length, 1);
    assert.equal(interceptedBuilds[0].path, '/api/chassis/role-reception-intake/commission', 'Manual override reaches the actual commissioning request');
    assert.equal(interceptedBuilds[0].payload.client_name, 'Studio Test Services');
    assert.equal(interceptedBuilds[0].payload.purpose, reviewed.draft.fields.purpose);
    assert(interceptedBuilds[0].payload.knowledge_package_id, 'Only reviewed knowledge is attached');
    await page.locator('[data-studio-target="recent"]').click();
    assert(await page.locator('#studio-recent').isVisible(), 'My builds must be reachable');
    await page.locator('[data-studio-target="hunter"]').click();
    await page.locator('#hunter-inbox').waitFor({state: 'visible'});
    assert(!await page.locator('#idea-start-panel').isVisible());
    await page.locator('[data-studio-target="create"]').click();
    await page.setViewportSize({width: 390, height: 844});
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: path.join(out, 'studio-mobile.png'), fullPage: true});
    await page.screenshot({path: path.join(out, 'studio-mobile-viewport.png')});
    await checkNoOverflow('mobile');
    await page.locator('#commissioning-form').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(out, 'studio-personalization-mobile.png')});
    assert.deepEqual(errors, []);
    assert.deepEqual(externalRequests, [], 'The regression must never fetch external resources');
    assert.equal(posts.filter(route => /\/research-jobs$/.test(route)).length, 1);
    console.log('PASS: seven-role choice; explicit no-fit; edit/reopen; async research; source evidence review; direction is not fact approval; website capture/review; selected-role commissioning request intercepted; desktop/mobile; navigation; zero real build/provider calls.');
    console.log('Screenshots: ' + out);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
