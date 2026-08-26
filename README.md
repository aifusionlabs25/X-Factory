# Hermes X-Agent Factory

## Current owner surface

Mission Control v1.9 is the working local Factory surface. It builds immutable named X-Agent candidates, preserves their evidence, previews governed presence, includes **Troy Prompt Forge**, **Rook Independent Review**, and **Porter Repo Foundry**, and connects the **Chassis Depot**, **Commissioning Bay**, **Knowledge Loading Dock**, **Owner Review Desk**, **Instance Knowledge Builder**, and **Runtime Foundry**.

The v1.9 local preview uses `GROUNDED_MATCHER_V0_2`: normal customer phrasing is matched conservatively to exact owner-approved statements, generated apps inherit the same versioned contract, unsupported primary requests remain visible in the staff handoff, and the UI states plainly that Hermes/Luna is not active during provider-free testing. Capturing a company website pauses Build until that website review is finalized or explicitly discarded. Advanced source-package history, source-file ledgers, and optional capabilities stay collapsed until the owner asks to inspect them. A final owner-facing knowledge receipt is rendered from the exact selected package used by the mission payload, showing source, reviewed-page/file count, approved-fact count, and explicit exclusions immediately before Build.

The owner begins with a **System Prompt Brief**, written in ordinary language. Atlas normalizes the intent, Aria designs the X-Agent, and Troy operates as Aria's specialist Prompt Forge sidecar. Troy compiles a complete `SYSTEM_PROMPT.md`, assumptions record, prompt test pack, owner receipt, and hash-bound manifest for every candidate. The Chassis Depot stores versioned, hash-bound, identity-free role foundations. The first validated chassis is `Operational QA Concierge v1.0.0`. The Commissioning Bay combines that reusable role logic with a separate X-Agent name, client, personality, target users, client context, additional requirements, additional boundaries, and presence selection. It then runs the existing deterministic Factory build and test path.

Client source files can be sealed, hashed, deterministically compiled into source-linked proposals, and reviewed entry by entry. During Personalize, the owner may also explicitly capture up to six public pages from one same-origin website. The capture rejects private/local targets, cross-site redirects, non-text responses, credentials in URLs, nonstandard ports, and raw pages over 1 MB; extracted readable text remains capped at 48 KB per page and 512 KB per package. It records exact page provenance and hashes, removes navigation and call-to-action boilerplate, groups related fragments, deduplicates repeated facts, and starts website proposals unselected. Approved website content is bound only into the separate Knowledge Bank; it cannot become behavioral system-prompt instructions or change identity, purpose, authority, tools, or boundaries. Commissioning with a completed review automatically creates the named candidate's readable KB, personalized system prompt, traceability map, deterministic knowledge tests, build report, Hermes profile blueprint, and inactive one-call Luna canary. Mission Control includes a provider-free local boundary console for testing approved and unknown questions. Profile installation, provider transport, deployment, and production remain gated.

After the deterministic build, Rook independently rechecks the evidence chain and reruns the generated tests without a model call. A passing review automatically releases the mission to Porter, which creates and verifies a new runnable local staging repository under `repos/local/`. When reviewed knowledge is present, Porter also carries the exact KB, system prompt, traceability, and tests into the staging repo. Porter never overwrites an existing repo, copies no populated environment file, and does not install, deploy, release, or promote anything to production. Hermes `/review` is prepared as a future governed audit option but is not invoked by the automatic local route.

Owner Control prepares exact plans and records one-click owner execution requests. Requesting does not itself call a provider or copy files. A separate guarded executor revalidates the immutable plan and request hashes, blocks duplicate semantic reviews and existing repository targets, and requires explicit activation outside the interface. Production remains locked.

Start Mission Control with `START_X_FACTORY.cmd` or `python -B scripts/mission_control_server.py --open`.

## Phase 0 dispatch rule

Kanban state is not execution authority. Only `ROUTE_TO_ARIA` and
`ROUTE_TO_VERA`, combined with an explicit authorization record, may dispatch a
profile. All owner-decision, blocked, revision, specification-ready, and closed
states are non-runnable. Generic `blocked` is forbidden; owner decisions use the
typed Hermes `needs_input` block kind. See
`contracts/kanban_policy.v0.1.json`.

Hermes Desktop is the factory surface and profile runtime. This directory is the authoritative, deterministic contract and artifact store.

Phase 0 lifecycle: `SPECIFICATION_ONLY`.

## Crew

- Atlas: intake, routing, workflow, and owner summaries.
- Aria: evidence-backed X-Agent specification design.
- Troy: Aria-controlled Prompt Engineering Lead; compiles the governed System Prompt package without inventing client facts or approving his own work.
- Vera: independent frozen-candidate evaluation.
- Rook: provider-free independent evidence and test review before packaging.
- Porter: complete local application repository packaging and verification.

## Authority

No profile in Phase 0 may build, deploy, mutate a production repository, use credentials, call a provider, create a cron job, or claim production readiness. Rob is the build/release authority. Codex may receive an implementation mission only after Vera returns `SPECIFICATION_READY_FOR_BUILD` and Rob approves.

## Truth model

Kanban cards display workflow. Versioned run artifacts and their hashes are authoritative. Profile memory is never cross-bot truth.

## Directories

- `contracts/`: immutable v0.1 JSON Schemas.
- `profiles/`: version-controlled role instructions and permission contract.
- `evidence/`: curated evidence records; no broad repository mount.
- `catalog/`: reusable component records derived from evidence.
- `fixtures/`: frozen positive and negative test inputs.
- `runs/`: generated run artifacts.
- `archive/`: rollback and superseded artifacts.
