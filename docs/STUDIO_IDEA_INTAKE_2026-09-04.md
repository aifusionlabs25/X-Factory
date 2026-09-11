# Factory Studio: owner ideas and optional research sources

> Historical v1.0 implementation record. The v1.1 Hermes research and seven-role catalog now supersede the research limitations below. See `RESEARCH_AND_ROLE_LIBRARY_2026-09-04.md` for the current workflow and remaining search-availability gate.

## Owner workflow

The Factory now has three starting choices: **My idea**, **Website or X post**, and **Hunter prospects**. Hunter is an optional lead source, not the prerequisite for creating an X-Agent.

1. Enter an idea, company name, company website, or X-post link. Optionally add the company name, its website, and pasted post text.
2. **Shape my idea** saves a local starting draft and proposes an editable System Prompt Brief. No website, Hermes bot, provider, mission, or build runs at this step.
3. Edit **What should this X-Agent do?** The final wording feeds the existing local Atlas/chassis recommendation and commissioned-instance purpose.
4. Either continue to personalization with owner documents, or **Read website & prepare facts**. The latter requires a company/project name and public company website, captures up to six same-site pages with the existing guarded importer, and opens the Knowledge Bank fact-review desk.
5. Choose and finalize the facts, name the agent, and use the existing explicit Build, Preview, and local-app packaging workflow.

Reopening the last idea restores the saved brief, including edits made before continuing. It does not resume a build, approve facts, or run research automatically. Applying an idea fills a fresh unsaved form; prior saved agents and source packages remain unchanged.

## Research and authority boundary

An X link is not fetched in this version. Owner-provided wording around that link and pasted post text can shape the proposed job, explicitly marked as unverified design inspiration. They never become Knowledge Bank facts. A link without context produces a clearly labeled generic brief and asks for the intended use case. A company name alone needs the public website before source-based research can proceed.

Website preparation reuses the existing capture and relevance-filtered compilation flow. Processing a captured package is not approval of its claims: the initial website fact selection is empty and commissioning is blocked until review is finalized or that capture is discarded. The reviewed source remains bound to the exact prepared company and purpose. Changing either blocks reuse until the owner restores the brief or prepares/reviews appropriate knowledge.

Drafts and research receipts are hash-bound under `drafts/ideas`. Source packages keep their existing evidence and schema. The API accepts only defined fields, rejects cross-origin browser writes, and carries through the importer’s public-address, same-site, size, and no-login boundaries.

This is local deterministic preparation, not autonomous Hermes-led prospect discovery. Scout remains the Hermes-update watcher. Hunter remains the GTM researcher. Automatic Hunter execution and reviewed result registration are still separate unfinished integration work; see `HUNTER_REFRESH_BOUNDARY_2026-09-04.md`. No Hermes profile, model, authentication, outreach, deployment, or production change was made for this feature.

## Interface changes

A separate `studio.css` layer provides the ivory/forest workspace, readable form text, permanent navigation, compact progress display, three entry choices, responsive cards, and calmer review/preview surfaces. Technical details remain optional. Build history appears when **My builds** is selected; crew descriptions are collapsed until requested. Existing visibility and release gates are preserved.

## Verification

- `verify_idea_intake_v0_1.py`: 11 isolated tests, including edited purpose, X inspiration isolation, SSRF guard, receipt reuse, changed company/job/source rejection, review-required commissioning, and no implicit mission creation.
- `verify_idea_studio_browser.py` + `.cjs`: real local HTTP and Chromium browser flow with temporary drafts/knowledge and synthetic company pages. Covers idea editing/reopen, X context, fact review, empty initial selection, build blocking, identity drift, navigation, desktop/mobile, and browser errors. No live website or provider is called by this test.
- Existing checks passed: Hunter inbox/refresh 9, Hunter draft 9, Hunter knowledge 28 (including inherited cases), grounded matcher questions/suggestions, 37 preview-state assertions, website-ingestion safety cases, four isolated chassis builds, 25 knowledge-pipeline checks, 7/7 local behavior, and 7/7 generated Porter application tests.
- Browser screenshots are saved in `outputs/studio-qa-2026-09-04`. Test builds use isolated verification directories; user missions were not rebuilt or rerun.

The optional Playwright executable override is `STUDIO_TEST_CHROMIUM`; `NODE_PATH` can point to the bundled runtime’s node_modules. Use `python -B scripts/verify_idea_studio_browser.py` for isolated browser testing, not a live user server.
