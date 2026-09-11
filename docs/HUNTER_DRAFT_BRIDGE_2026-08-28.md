# Hunter → Factory: review-only bridge v0.1

## Owner use

Open http://127.0.0.1:8877/ and expand **Review a Hunter prospect** in Step 1.
Choose one company. Read the dated sources, review the proposed job and exclusions,
choose a name, role and appearance, then select **Use reviewed draft**.

That action saves a review receipt and fills the normal form. It does not build,
create a mission, approve knowledge, fetch sources, invoke a model, select extra
modules, activate an avatar, or contact anyone. Existing saved agents/KB stay intact.
The explicit replacement checkbox authorizes clearing only the unsaved form state.
After a refresh, choose the same company and use **Reopen saved draft** to restore
the saved values. Changing the form later does not rewrite the original receipt.

## Implemented boundary

- One fixed local checkpoint is allowlisted: Hunter audit v0.7.1, source SHA-256
  `00263873dffc429fed208d922475b82e78363f8e75acced7438c555daa07621e`.
- Source observations remain dated August 25, 2026; the August 28 rebrief is not a
  new hunt. First-version freshness window: seven days; stale/future dates block.
- Hunter run/scoring v0.4 and brief v0.7 validation functions are frozen under
  `x_factory/hunter_contracts/`. No external Hunter code is loaded at runtime.
- No arbitrary upload, source path, URL fetch, script, module, persona, approval,
  or lifecycle field is accepted from an import request. A changed checkpoint
  requires a separately reviewed binding, not merely a caller-supplied hash.
- Millers remains HOLD: August 28 timeout followed by a robot challenge. This
  does not redate or promote the historical record.
- Research snapshot and owner-edited fields are stored separately. Company
  research does not populate `client_context` or any Knowledge Bank input.
- Actual fields: purpose, client_name, target_users, personality,
  additional_requirements, additional_boundaries; name/appearance are owner choices.
- The only catalog role currently supported is the locally resolved Operational
  QA Concierge. Its current hash is checked again at acceptance. No live features
  or integrations are inferred from Hunter's fit assessment.
- Purpose now consistently caps at 2,000 characters in owner UI and both request
  schemas. Additional rules are checked WITH the unchanged chassis baseline.
- Receipts use exclusive creation in `drafts/hunter/`, with source, snapshot,
  chassis and receipt digests. Duplicate acceptance never overwrites. Reopening
  is explicit/read-only and rechecks freshness, HOLD and integrity gates.
- `/api/hunter/prospects`, `/review`, `/accept-draft`, `/reopen-draft` have no path
  to commissioning, KB approval, provider transport, CRM, or outreach functions.

## Lead inbox handoff v0.1

The Factory now exposes a **Hunter → Factory · Controlled Inbox** at the top of
Mission Control. It is populated only from an intact owner-reviewed receipt; a
Hunter score or research record alone never enters the queue. **Send to Factory**
creates one hash-bound `drafts/hunter-inbox/<prospect-id>.json` handoff with
`UNAPPROVED_RESEARCH`, zero knowledge approvals, zero missions, zero provider
calls and zero outreach. It is a durable transfer record, not an automatic build.

The separate **Use in Factory** action remains owner-controlled and runs the same
source, chassis, freshness and integrity checks as the original review bridge.
Stale research is shown in the inbox and is rechecked when the draft is used;
importing a lead never renews its observation date. The handoff contract is
`contracts/hunter_factory_lead_handoff.v0.1.schema.json` and requests accept only
the selected `prospect_id`.

When the inbox marks a lead as stale, **Prepare Hunter Refresh** creates an
idempotent `hunter.factory-refresh-request.v0.1` packet under
`drafts/hunter-refresh/requests/` and copies its bounded prompt when the browser
allows clipboard access. The owner runs that one-prospect, read-only request in
the separate Hunter Hermes profile, exports a new owner-reviewed result to the
declared `drafts/hunter/incoming` dropbox, then returns to Mission Control and
refreshes the inbox. The Factory does not launch Hermes, make provider calls, or
accept an unvalidated file merely because a refresh was requested.

## Verification performed

- `python -B scripts/verify_hunter_draft_v0_1.py -v`: 9 tests PASS, including
  schema/authority injection, unknown paths, missing evidence, score drift,
  source/chassis drift, freshness, HOLD, duplicates, recovery, receipt tampering,
  effective lengths and HTTP execution tripwires. All receipt writes use temporary
  synthetic fixtures, not real prospects.
- Existing grounded matcher regression: PASS.
- Existing preview state/correction/session-isolation regression: PASS.
- `python scripts/verify_hunter_inbox_v0_1.py`: 2 provider-free tests PASS,
  including exclusive hash-bound handoff creation, idempotent reuse, guardrail
  defaults, source binding and rejection of extra request fields.
- In-app browser: fictional Test Leroy accepted into form; Text only preserved;
  no approved knowledge selected; no build; no console errors. Refresh and reopen
  saved fixture PASS. Real list renders; Millers HOLD disables acceptance.
- Windows server startup now uses an exclusive port binding. Two old/current
  Factory processes were replaced by one current server; Hermes was not restarted.

## Hunter web repair and limitations

The prior failure was an external Parallel extraction timeout, not evidence of a
Desktop restart problem. A bounded retest reached the company but got a Robot
Challenge Screen with five characters of content. It is not valid business evidence.
No bypass was attempted.

Existing Parallel free search and extraction both succeeded against public Hermes
documentation, including through the installed Hermes web-tool dispatcher in an
isolated credential-free home. Zero model calls. Hunter-only config now explicitly
pins Parallel for both operations and disables rotation/rescue to other anonymous
vendors. Other vendor tiers are set paid solely to exclude their anonymous paths;
no credentials, billing, account, or subscription was added.

Hunter's installed SOUL and source SOUL now explain blocked/empty/challenge pages,
HOLD handling, correct Factory field mappings, and research/KB separation.
These are instructions, not a claim that a new deterministic native webpage filter
was installed. A fresh Hunter conversation must load them.

Remaining gates: reliable real-company retrieval, rendered-intake qualification,
native model obedience to the new instructions, and native-result export ingestion.
One working reference test does not certify unattended sourcing. No real prospect
was newly qualified or owner-approved. Scheduling and outreach remain inactive.

## Recovery

Factory code changes are uncommitted and scoped to this bridge, UI, schema length
alignment, tests and server binding. Prior missions and evidence were not rewritten.
Hunter config/SOUL pre-change copies are in the parent task's
`outputs/hunter-web-backup-20260828-124213/`. Restore only those two Hunter files
if reverting web routing; never replace shared credentials or other profiles.
Native tool-test evidence is in the parent task's
`outputs/hunter-native-web-check-20260828.json`.
