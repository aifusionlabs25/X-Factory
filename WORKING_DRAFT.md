# X-Factory Mission Control v1.9 — Operational Working Draft

## v1.9 Owner Progressive Disclosure

- Source-package history is closed by default and shows only the selected or newest package when opened.
- Older packages remain available behind `SHOW PACKAGE HISTORY`; nothing is deleted.
- Each package's file ledger is independently expandable.
- Optional capabilities are closed by default because the essential behavior is already included.
- A required owner review automatically opens the source section so the next action cannot be hidden.
- The pre-Build knowledge receipt is bound directly to `selectedKnowledgePackageId`; it shows the owner the source, reviewed pages/files, approved-fact count, and excluded content while keeping IDs and hashes in Factory Details.
- Unsupported preview questions are labeled as a passed safety check: no approved evidence was found, so the agent escalated instead of guessing.

## v1.8 Website-Knowledge Build Interlock

- A successful website capture pauses commissioning until the captured website review is finalized.
- The previously selected package is deselected during review so a sample pack cannot be packaged silently.
- The owner may explicitly discard the website capture and restore the previous reviewed package.
- Commissioning also enforces the interlock at submit time, not only through the disabled button.

## v1.7 Grounded Preview Repair

- Factory Preview and newly generated Porter apps share the versioned `GROUNDED_MATCHER_V0_2` contract.
- Natural questions can retrieve exact approved capability, service, policy, and location statements without a provider call.
- Certification must prove a non-title natural-language question; exact-title shortcuts no longer satisfy the first assertion.
- An unsupported primary service request still captures its problem, service, city, and urgency, then routes to `URGENT_HUMAN_REVIEW` when appropriate.
- Secondary unknown questions remain separate from the primary request.
- Local preview labels explicitly disclose that no language model or Hermes session is active.

## Start it

Double-click `START_X_FACTORY.cmd`, or run:

```powershell
python -B scripts\mission_control_server.py --open
```

Mission Control binds only to `http://127.0.0.1:8877/`.

## What works now

- One-screen owner brief with purpose, identity/client, target users, personality, required behavior, prohibited behavior, and primary output.
- Presence choice for an existing ANAM persona, a new ANAM creation brief, a stock image, or text-only.
- Mia from ANAM's stock catalog is the default Factory recommendation, with her captured avatar and voice identifiers.
- A real seven-stage contained build:
  1. Atlas normalizes and bounds the brief.
  2. Aria creates a schema-valid X-Agent blueprint and selects reusable modules.
  3. Vera validates the blueprint and authority boundary.
  4. Mason compiles the candidate twice and compares every output byte.
  5. Vera runs the generated acceptance test and writes final certification.
  6. Knowledge Forge either builds the exact owner-reviewed entries into the named instance or proves that client knowledge remains gated.
  7. Runtime Foundry seals the personalized prompt and KB into a named Hermes profile blueprint plus an exact inactive one-call GPT-5.6 Luna canary.
- Every successful submission creates a new immutable directory under `runs/interactive/`.
- Any completed mission can be loaded back into the owner brief with **Revise this agent**. Running the revision creates a new immutable mission and preserves the source mission.
- The completed screen links to fifteen artifacts: the owner brief, full blueprint, Mason compatibility input, agent instructions, agent specification, bundle manifest, generated test, certification, persona binding, Control Center handoff, X-Link candidate package, X-Link registry entry, X-Link scenario pack, contained ANAM canary plan, and sealed Hermes/Luna review packet.
- The local ledger lists recent Factory missions.
- Ledger missions can now be opened directly inside Mission Control without rebuilding them.
- The finished-candidate screen includes a large, readable **Meet this agent** presence preview using the mission's bound persona, voice style, purpose, and visible text fallback.
- Presence readiness is evaluated through four visible gates: local build, Hermes/Luna semantic review, ANAM transport proof, and an unused one-session activation packet.
- Certified missions can copy their exact activation approval from the screen. The live-launch control remains physically disabled until the matching governed localhost runtime is running.
- Uncertified missions remain usable as static previews but cannot copy or launch a live activation.
- Unsafe secret-like or path-like input is rejected before mission creation.
- Porter Repo Foundry can turn any locally certified mission into a complete runnable local staging repository.
- Repo Foundry includes a localhost preview, agent and X-Link configuration, persona binding, tests, start scripts, README, full Factory evidence, and the sealed Runtime Foundry package when reviewed knowledge exists.
- Repo creation is idempotent for the same mission, refuses overwrite, copies no real credentials, and performs no provider, installation, deployment, or production action.

## Mission Control v1.1 Runtime Foundry

- A knowledge-ready commissioned candidate receives a unique, named Hermes profile blueprint using `openai-codex / gpt-5.6-luna` at low reasoning.
- The blueprint disables memory, tools, fallbacks, external actions, and retries. It is an artifact only and is not installed automatically.
- The local Runtime Console exercises the sealed approved knowledge deterministically and makes zero model calls.
- Runtime Foundry prepares exact hash-bound prompt and payload artifacts for one later governed live canary. The canary is inactive by default.
- Unknown local questions visibly escalate for human review instead of inventing client facts.
- Verification is recorded in `verification/mission-control/runtime-foundry-v1.1.json`.

## Mission Control v1.2 Local Behavior Certification

- Every knowledge-backed named instance now runs a provider-free, two-session behavior harness during the Factory build.
- Seven assertions cover approved-source grounding, unknown escalation, current-session correction handling, identity continuity, structured module handoff output, zero prohibited side effects, and fresh-session non-persistence.
- A passing local harness is recorded as `LOCAL_BEHAVIOR_HARNESS_PASS`; it never substitutes for the later contained Hermes multi-turn proof.
- Porter carries the hash-bound local certification into the staging repository, while official-repository promotion remains locked until `RUNTIME_BEHAVIOR_VERIFIED` is produced by the guarded live-runtime gate.

## Mission Control v1.3 Owner Experience

- The default experience is now five plain steps: Describe, Personalize, Build, Preview, Release.
- Technical departments, hashes, raw artifacts, lifecycle internals, model configuration, and evidence remain available through one `Factory details` control instead of competing with the owner workflow.
- A quick-knowledge action turns owner-provided facts and Q&A into a reviewed local package; genuine conflicts alone open the detailed review desk.
- The local preview supports known answers, unknown escalation, current-session corrections, a visible structured handoff, and an explicit fresh-session reset.
- Primary language is owner-oriented and the default type scale is enlarged for readability.
- Owner Control replaces technical copy/paste packets at the preparation stage with two plain-English controls: prepare a three-call Hermes review and prepare a new-directory-only official repo handoff.
- Both Owner Control plans are hash-bound and idempotent. Mission Control v0.5 intentionally exposes preparation only; provider transport and external repository writes remain unavailable.

## Mission Control v1.4 Automatic Local Finish

- One owner Build action now continues through the deterministic Atlas → Aria → Vera → Mason → Vera route, Rook's independent provider-free review, and Porter's verified local repository packaging.
- Rook independently checks required artifacts, build repeatability, declared evidence, credential-like content, authority boundaries, and reruns the generated test suite before Porter can package the candidate.
- The owner sees one readable seven-station Mission Runner and a final `LOCAL X-AGENT BUILT` state that explicitly directs them to preview before any governed runtime or release action. Manual preview and Factory Details remain available but are not a hidden prerequisite for obtaining the local app.
- The complete repo includes Rook's review record and keeps the commissioned X-Agent identity separate from the internal chassis name.
- Hermes `/review verify every requirement was completed and look for anything that could break` is prepared but not invoked. The default route makes zero provider calls and zero network attempts.
- A second golden path, `Nora — Employee Policy Guide`, passed the automatic browser flow, independent review, repo tests, identity checks, and provider/network boundary checks.

## Mission Control v1.5 Website Knowledge Intake

- Website ingestion now appears during **Personalize**, after Atlas recommends a chassis and before commissioning.
- The owner sees one company-website field and one **Capture for review** action. The Factory captures at most six readable public pages from that same website.
- Private, local, reserved, and link-local targets are rejected before fetching. Cross-site redirects, credentials in URLs, nonstandard ports, non-text responses, oversized pages, and excessive redirects are blocked.
- Every captured page retains its exact URL, title, source-body hash, stored-file hash, capture time, and same-origin scope in the immutable knowledge manifest.
- Capture never becomes runtime truth. The owner must explicitly prepare the captured package for review and approve or reject every extracted entry before it may attach to a commissioned instance.
- Website capture is the only new outbound network surface and occurs only after the owner presses the capture button. It makes zero model/provider calls and authorizes no login, tool use, deployment, release, or production action.
- The capture transport explicitly ignores ambient `HTTP_PROXY` / `HTTPS_PROXY` values so a temporary developer-shell proxy cannot hijack or break the owner-requested direct fetch. The URL still passes the same public-address, same-origin, redirect, content-type, and size guards before every request.
- Provider-free regressions prove the approval gate, source provenance, deterministic compilation, private-address block, and cross-site redirect block. A headless owner-flow test verifies the simple UI and its visible “nothing is approved yet” boundary.

## Mission Control v1.7 Website Knowledge Quality

- Website extraction now removes common navigation, CTA, store, and image-viewer boilerplate before owner review.
- Related same-section fragments are grouped, exact repeated facts are deduplicated, and every retained proposal receives a constrained owner-facing relevance category.
- Website proposals start unselected and are labeled **Knowledge Bank only**. Selection is an owner decision; “selected” is not presented as “approved” before finalization.
- Website-derived facts are excluded from behavioral system-prompt prose. The system prompt binds the separate approved Knowledge Bank but does not let website content alter identity, purpose, boundaries, tools, or authority.
- Legacy website compilations are immutable but cannot be finalized; Mission Control offers **Capture clean copy** to create a fresh relevance-aware package.

## Output compatibility

Each mission preserves:

- The canonical HERMES X-Factory blueprint v0.2.
- An explicit v0.1 Mason generator projection required by the sealed Phase 1.3 acceptance fixture.
- A founder-facing handoff aligned to the existing `x-agent-control-center` vocabulary.
- An X-Link/ANAM persona binding with provider mutation disabled.

## Current boundary

This is a real local compiler and evidence workflow. Its default Run button intentionally performs zero model calls and zero ANAM provider actions. Mission Control now recognizes the completed Hermes/Luna semantic certification and successful Mia transport proof for the certified Operational QA Concierge.

The visual layer remains governed. Opening **Meet Mia** is provider-free. A live launch becomes available only when the exact prepared canary server is separately approved and running; opening that canary still leaves its provider Start action explicit and visible.

Deployment and Production approval remain false.

## v0.2 semantic review checkpoint

- Original reviewed mission: `draft-operational-qa-concierge-20260821-060040-8c8ea9`.
- Review: `review-20260821-062902` completed three Luna calls with zero retries, zero tool attempts, and unchanged authentication.
- Atlas, Aria, and Vera all returned `REVISION_REQUIRED` for the same bounded specification defects.
- The Factory compiler was corrected globally and produced immutable revision `draft-operational-qa-concierge-20260821-063232-b915d1`.
- That revision passed the real X-Link registry schema, X-Link reverse compiler, and eval-plan generation in an isolated fixture with zero repository writes.
- Second reviewed mission: `draft-operational-qa-concierge-20260821-063232-b915d1`; Atlas and Aria passed, while Vera requested five final specification corrections.
- Final immutable revision: `draft-operational-qa-concierge-20260821-064103-a3e197`.
- Final review: `review-20260822-001005` completed three Luna calls with zero retries, zero tool attempts, and unchanged authentication.
- Atlas, Aria, and Vera unanimously returned `PASS`. The result is recorded in `verification/mission-control/hermes-semantic-certification.v0.1.json`.
- The revised candidate also passes the real X-Link registry schema, reverse compiler, and isolated eval-plan generation.
- At the semantic-certification checkpoint, ANAM remained untouched and the Mia/Luna visual canary was the next gate.

## Mia/Luna visual canary checkpoint

- `mia-luna-visual-canary-005` completed its one Luna call successfully. The exact spoken response passed its schema and matched the visible text fallback.
- ANAM rejected the single session-token request before issuing a token or opening a stream. The no-retry policy correctly stopped the run terminally.
- No talk command, microphone capture, persona mutation, X-Link write, deployment, or production action occurred.
- Read-only ANAM Lab inspection showed no new session and no API-key last-used update corresponding to the request. This is evidence, with medium confidence, that the local ANAM credential was not recognized or accepted.
- The next gate is an owner-authorized active ANAM API key, followed by a fresh ANAM-only continuation that reuses the already accepted Luna response.

## ANAM-only continuation checkpoint

- The updated credential was accepted in `mia-anam-continuation-007`: ANAM issued a session token and the browser recorded a connection event.
- The canary client sent its talk command before the SDK's connection event arrived. ANAM rejected that command locally because the peer connection was still null.
- The no-retry policy stopped the proof after one session slot. Zero Luna calls were made, no talk command was accepted, and the browser stream and local server were closed.
- The client now waits for the actual connection event before speaking, closes an active stream during any failure, preserves terminal status against late callbacks, and displays the correct zero-call Luna budget.
- Corrected continuation `mia-anam-continuation-008` passed local preflight with zero provider calls and zero ANAM sessions. Its activation remains pending owner approval.

## Mia visual transport proven

- `mia-anam-continuation-008` completed successfully with status `CANARY_PASS_SESSION_CLOSED`.
- ANAM issued the ephemeral session, Mia's stream connected, and the exact accepted Luna text was accepted as the single talk command.
- The session then closed normally and recorded the explicit user-stop event.
- The continuation made zero Luna or other model calls and zero retries.
- No credential or session token was persisted. Microphone capture, persona mutation, X-Link writes, deployment, release, and production all remained disabled.
- The result is sealed in `verification/mission-control/anam-continuation-live-008.v0.1.json`. The X-Factory now has a proven contained path from a certified Luna response to a visible ANAM stock persona.

## Mission Control v0.3 presence integration

- The finished Operational QA Concierge now opens directly from the local ledger and exposes **Meet Mia** without rebuilding the mission.
- The integrated presence panel displays Mia, the bound Dana voice style, the certified question, and the identical 25 px visible fallback text.
- Local build, Hermes/Luna review, ANAM transport, and activation-packet gates all show `PASS` for the certified mission.
- Fresh inactive packet `mia-mission-preview-009` passed preflight with manifest `35db2e07b5cc64a85e501439e12157e0c31c3e419044bd0590ef457816a78a5c`.
- Mission Control can copy the exact approval for that packet, but its live-session button stays disabled until the matching localhost canary runtime is present.
- An earlier uncertified revision was also checked: it remains in static-preview mode, cannot copy activation approval, and cannot launch a live session.
- The visible v0.3 server is running on `http://127.0.0.1:8877/`. No ANAM session, credential read, or model call occurred during this integration.
- Verification is recorded in `verification/mission-control/mission-control-presence-v0.3.json`.

## Mission Control Live Mia proof

- The owner launched `mia-mission-preview-009` from the governed local preview after a computer restart.
- Mia's stream connected and accepted the exact bound sentence: `Create a contained operational concierge that answers approved questions and prepares a structured local review handoff.`
- The owner ended the session; the connection closed normally and the explicit user-stop event was recorded.
- The proof reused the previously accepted Luna response and made zero new Luna or other model calls.
- The single authorized ANAM session slot was consumed with zero retries. No credential or session token was persisted, and microphone capture, persona mutation, X-Link writes, deployment, release, and production remained disabled.
- The result is sealed in `verification/mission-control/mission-control-live-mia-009.v0.1.json`.

## Porter Repo Foundry proof

- Mission Control v0.4 adds Porter as the final local handoff station after candidate certification.
- Certified mission `draft-operational-qa-concierge-20260821-064103-a3e197` produced repo `operational-qa-concierge-52bcb031` under the Factory-owned `repos/local/` yard.
- Porter generated 27 hash-bound application files plus the repo record: a zero-dependency localhost preview, agent instructions and specification, X-Link files, ANAM binding, tests, scripts, README, and the complete Factory record.
- All four generated repository tests passed. Mission Control and the generated preview returned HTTP 200, the preview interaction returned the correct approved purpose, and browser inspection found no console errors or horizontal overflow.
- A second create request returned the same sealed repo record and digest; no overwrite occurred.
- Zero model or provider calls were made. No credentials, existing-repository writes, X-Link installation, deployment, release, or production actions occurred.
- Verification is sealed in `verification/mission-control/porter-repo-foundry-v0.1.json`.

## Mission Control v0.5 owner checkpoint

- The certified Operational QA Concierge now displays a single plain-English Owner Control panel after Repo Foundry.
- The Hermes lane prepared an inactive Atlas to Aria to Vera review plan capped at three GPT-5.6 Luna calls, zero retries, zero tools, and read-only authentication.
- The Porter lane prepared an inactive handoff plan targeting a new `C:\AI Fusion Labs\X AGENTS\REPOS\Operational QA Concierge` directory. The target was confirmed absent; no directory or file was created there.
- Both preparation requests are idempotent and return their existing hash-bound plans on repetition.
- Activation remains physically unavailable in v0.5. Preparation made zero provider calls and zero official-repository writes.
- Browser verification found the new panel readable, free of console errors, and without horizontal overflow.
- Verification is sealed in `verification/mission-control/owner-control-v0.1.json`.

## Mission Control v0.6 owner requests and guarded executor

- Owner Control now separates four states in plain English: prepare locally, record the owner's request, execute through a separate guard, and keep production locked.
- The certified Operational QA Concierge displays its existing unanimous Atlas, Aria, and Vera result and suppresses duplicate Hermes review requests.
- The official-repo lane exposes one owner request button only after Porter has produced a verified local repository and the target is confirmed absent.
- Clicking a request records an immutable, hash-bound local decision with zero provider calls and zero official-repository writes. It does not execute the action.
- The guarded executor independently validates plan and request hashes, source hashes, fixed target roots, no-overwrite rules, credentials, and destination tests before any activated action.
- Isolated verification proved request idempotency, tamper rejection, duplicate-review blocking, inactive preflight behavior, and zero external effects.
- Browser verification at 1280 × 720 found the v0.6 Owner Control panel readable, free of console warnings or errors, and without horizontal overflow.
- The official target `C:\AI Fusion Labs\X AGENTS\REPOS\Operational QA Concierge` remains absent. Production, deployment, X-Link installation, and provider execution remain inactive.
- Verification is sealed in `verification/mission-control/owner-execution-requests-v0.1.json`.

## Official local repository promotion

- The owner requested official repository creation from Mission Control for certified mission `draft-operational-qa-concierge-20260821-064103-a3e197`.
- The guarded executor validated request `f7f9a5150290195370a149819a6099c60dd97c518d167d69cdc36714fb387404` against plan `ad647ef369913d984b3a3b1dc961a9f62928027b5bb1b5db1a0171a7481dec8c` before writing.
- The sealed Porter repository was copied as the new directory `C:\AI Fusion Labs\X AGENTS\REPOS\Operational QA Concierge` with no overwrite.
- All 28 repository files were verified and destination tests passed. No credentials were copied and no existing repository was mutated.
- X-Link installation, deployment, release, and production remain inactive.
- Mission Control now displays `OFFICIAL REPO CREATED · TESTS PASS` for this mission.
- Execution evidence is sealed in `control/owner-gates/draft-operational-qa-concierge-20260821-064103-a3e197/repo-promotion-execution.v0.1.json` and summarized in `verification/mission-control/official-repo-promotion-v0.1.json`.

## Mission Control v0.7 Chassis Depot and Commissioning Bay

- The Factory now separates reusable role foundations from named client X-Agents.
- `Operational QA Concierge v1.0.0` is stored as the first identity-free, locally validated chassis with six reusable modules, a layered prompt contract, required client-material checklist, reusable evaluations, and explicit non-production authority.
- The Commissioning Bay separately captures X-Agent name, client, role, personality, target users, client context, additional requirements, additional boundaries, and presence mode.
- From-scratch Owner Briefs now also separate X-Agent name, client/company, and role/project instead of conflating all three.
- One chassis produced isolated local test candidates `Ava — Operational QA Concierge` for XYZ Data Company and `Leo — Operational QA Concierge` for Northstar Field Services. Both passed the deterministic build suite and neither specification contained the other client's identity.
- Existing legacy Owner Briefs remain compatible.
- Client context is preserved but is not yet runtime-authoritative. Document ingestion and knowledge testing are the next gated Factory department.
- Browser inspection found one visible chassis, a readable Commissioning Bay, working close/reopen controls, no console warnings or errors, and no horizontal overflow.
- Zero provider calls, external repository writes, deployments, or production actions occurred.
- Verification is sealed in `verification/mission-control/chassis-commissioning-v0.1.json`.
