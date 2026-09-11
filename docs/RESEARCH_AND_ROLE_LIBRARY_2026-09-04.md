# Factory Studio v1.1 — research and role selection

## What the owner can test

Open http://127.0.0.1:8877/ and refresh the page.

1. Start with **My idea** or **Website or X post**. Include the company website for the most reliable current test.
2. **Shape my idea** saves a local brief. Edit the job in your own words.
3. Choose a starting role directly, or click **Research & recommend a role**.
4. Hermes investigates public sources, compares the actual role catalog to the customer job, and proposes a direction. Read its sources, uncertainties, and reason. Change the role if appropriate, then **Use this direction**.
5. Personalize the agent. Capture/review company knowledge separately. Only the owner's finalized fact review approves Knowledge Bank facts; research alone never does.
6. Use the existing explicit build, preview, and complete-local-app flow.

The brief is input to Troy's System Prompt work, not the entire finished System Prompt. Research recommendations are not proof that an agent is ready for deployment.

## Seven selectable starting roles

- Reception & Intake
- Lead Qualification
- Support Triage
- Client Onboarding
- Product & Service Guidance
- Internal Knowledge
- Operational Concierge (the existing chassis)

The six new roles are distinct local recipes: operating methods, required knowledge, work products, scenario assertions, and generated prompt sections. They are not clones with different dropdown labels. They share the existing local runtime and do not inherit the original concierge's Luna certification. Every client-specific agent still needs its own knowledge review and behavioral checks.

Before research, role fit uses a transparent local rules-based suggestion. Native Hermes R&D compares the full available catalog and supplies a strategic choice and explanation. Invalid IDs are rejected; unsupported actions can force **No fit**. Explicit owner selection remains the final choice.

## What is live, and what is still limited

The Research button now starts real Hermes execution using the installed Hermes harness and `openai-codex / gpt-5.6-luna` at low reasoning. It is not a dormant activation packet. Runtime state is isolated inside that research job's workspace folder. No Hermes profile or update is installed.

Website-led research has passed live public-source tests. The final Python Software Foundation example returned five captured official pages, exact source-bound findings, and an owner-review result using three model calls and five web-tool calls. Hermes compared all seven roles and recommended Operational Concierge, explaining why the job was not sales qualification, client onboarding, or troubleshooting. The runtime auth check reported unchanged credentials and no guard events. Final evidence: `verification/live-research-8gtx2_te/jobs/research-95e4cef56edf9951ef6127ab/`; result SHA-256 `5304efb3a1e8aa945a7de5bd24bdc30b1eb58b76c9525a191f50b0518bbf15fd`. Earlier four-page citation proof: `verification/live-research-3evoq0et/jobs/research-2af3d34c8fe3129b79e57e79/`.

**Name-only discovery is not yet dependable on this machine.** No supported search API key is configured. The worker can use key-free public search, but that service returned an access challenge during testing. It stops safely and reports the limitation. A company website can still be read directly. X may require owner-pasted post text when its public page is unavailable. Do not represent missing search results as completed research. No access-challenge bypass, anonymous Parallel/Exa proxy, or new paid service was activated.

Hunter remains an optional GTM sidecar. This Factory R&D worker does not start Hunter's refresh jobs, use Hunter's lead records without review, or alter Hunter's profile.

## Research boundaries

- Explicit owner start; at most 8 model calls, 12 web-tool calls, 8 distinct attempted source URLs, 80,000 accepted source characters, and 3 minutes per job.
- Web search and public-page extraction only. No command/file/repository tools, MCP, memory, outreach, build, installation, deployment, or automatic knowledge approval.
- Actual model requests are counted at transport; identical request retries are blocked. Failed source URLs are not automatically retried. **Research again** explicitly creates a new draft/job, rather than silently restarting a consumed job.
- Public-address checks, bounded downloads and decompression, same-origin page redirects, bounded search metadata, and strict source-citation validation.
- Hermes-owned authentication is read-only. Refresh/import/mutation is blocked; Codex CLI authentication is nonparticipating. Sign in through Hermes Desktop if credentials need renewal.
- The Windows asyncio socketpair exception permits only the exact standard-library in-process loopback pair, not ordinary localhost requests.
- Source facts are assembled from captured passage IDs. The model selects passages; code copies the exact text. Inferences stay in the summary/proposed job/role requirements and remain owner-reviewed research context.
- Ambiguous identity needs owner selection. No-source results retain uncertainty and approve nothing.
- Cancellation, invalid evidence, interrupted server, and transport failures cannot promote a late result or trigger an automatic restart.

## Local records and compatibility

New drafts: `drafts/ideas`; research jobs: `drafts/idea-research`. Results, source evidence, draft hashes, reviewed-direction receipts, job-local runtime, exact model prompt, and authentication-integrity hashes stay local. Credentials are never placed in these records.

Existing user missions, previous approvals, the original chassis, and live repositories are preserved. The common website reader now safely decodes bounded gzip/deflate pages, so Knowledge Bank capture receives readable text too.

## Verification

- Idea intake: 11 cases.
- Async research/evidence boundary: 12 cases.
- Research direction/public reader/compression: 15 cases.
- Role library: 10 cases, including strategy over keyword overlap and explicit no-fit.
- Citation assembly: 7 cases, validated against the unchanged strict quote-evidence rules.
- Native runtime guard tests: 21 isolated cases against actual worker guard functions, without credentials/providers.
- Two actual isolated generated-role builds: Lead Qualification and Internal Knowledge, with generated unit tests and prompt artifacts.
- Real Chromium UI over isolated HTTP/fake research: all seven choices, persistent owner selection, no-fit, source review, no implicit fact approval/build, separate Knowledge Bank review, commissioning's selected role, and desktop/mobile overflow checks. Screenshots: `outputs/studio-qa-2026-09-04/async-rd-roles`.

Use `python -B scripts/verify_idea_studio_browser.py` only with the isolated wrapper. The separate live-canary script requires its explicit `--run-public-canary` flag and is not part of the ordinary offline test suite.
