# Hunter to Knowledge Bank — explicit preparation handoff

## Owner experience

Reopen/use one reviewed Hunter draft. In Step 2, under **What should this agent
know?**, choose **Prepare Knowledge Bank from Hunter's sources**. Sources and the
reviewed job are expandable; the normal owner view stays simple.

That separate click reads at most six public pages on the company origin,
prioritizes Hunter's cited company links, and prepares source-linked proposals.
The fact-review panel opens without exposing Factory Details. All new website
facts start unchecked. The owner selects accurate, relevant facts and finalizes
the review. Only the later Build packages approved Knowledge Bank files through
OMNARA and the System Prompt through Troy. No agent mission is created by import
or preparation.

This is local deterministic extraction/organization, not an autonomous LLM
researcher or a guarantee of a complete client Knowledge Bank. The outline shows
proposal counts and missing sections, not inferred facts. Intake/escalation
policies still need owner input. Hunter remains a research source; Scout remains
the Hermes intelligence watcher.

## Boundary and mapping

- `/api/hunter/knowledge-plan`: read-only, requires the existing accepted draft
  receipt and unchanged source, role, age and HOLD checks. Returns reviewed job,
  company URLs, exclusions and a digest-bound plan. No source fetch or files.
- `/api/hunter/prepare-knowledge`: exact request fields `source_id`, `prospect_id`,
  `plan_sha256`, `owner_requested: true`; same-origin JSON only. Revalidates the
  plan. No browser-supplied URLs, filesystem paths, approval flags or authority.
- Public capture stays on one origin, standard ports, bounded bytes/timeouts and
  redirects. Six attempted pages maximum, including empty pages. A 404/410 on a
  Hunter-reviewed source stops. A 404/410 on an optional link discovered from a
  readable reviewed page is skipped and recorded in `skipped_pages`. Access
  challenge, timeout, private address or cross-origin redirect stops; no
  bypass/fallback.
- This explicit click authorizes source-file PROCESSING, using the existing raw
  package approval record needed by the compiler. This is NOT compiled-fact
  approval: no `review_compilation`, commissioning, build, model, ANAM, outreach,
  profile or credential action occurs in preparation.
- Fresh fetched source text goes under `knowledge-packages/<id>/files/`. Hunter's
  synopsis, proposed behavior and old research claims are NOT inserted there or
  into the compiled proposals, client_context, or System Prompt instructions.
- The original draft review is unchanged. Separate preparation receipts live in
  `drafts/hunter-knowledge/<plan-digest>.json`; a matching provenance binding lives
  outside `files/` at the package root. Neither is treated as KB source text.
- Successful repeated preparation of the same plan/day reuses the exact hashed
  package and compilation, not another fetch. Concurrent preparation is blocked.
  Changing source/job/date requires a new reviewed plan; corrupt bindings stop.
- Canonical compilation/review schemas and `additionalProperties: false` remain
  unchanged. The outline references canonical entry IDs; it does not mutate them.
- UI and commissioning reject a Hunter-prepared package after company or job
  changes. Existing manual/website packages keep their current contracts.
- Build remains paused for a pending review. Owner rejection/discard and existing
  manual website/document/fact entry paths remain available.

## Verification

- Hunter preparation suite: 28 test executions PASS (includes repeated baseline
  import tests). Covers explicit request, receipt/source drift, HOLD, private and
  cross-site targets, challenge/timeout, six-attempt ceiling, no research leakage,
  no automatic fact approval or mission, reuse, company/job binding, HTTP guards.
- Existing website capture, grounded matcher, preview state/corrections/isolation,
  OMNARA, and Knowledge Dock/options/Porter regressions PASS.
- In-app browser synthetic test: import -> optional preparation -> visible fact
  review (zero selected) -> explicit selection/finalization -> Build enabled.
  Changing the company then disables preparation AND Build. No Build was clicked.
- The owner-requested Joe Rushing retry captured five readable public pages and
  recorded one discovered retired link (`/air-conditioning`, HTTP 404). It
  prepared 99 source-linked proposals with zero selected, zero approved, zero
  provider calls, and no mission/build. Live site readability remains determined
  by each requested capture.

Existing missions, approved packages and Hunter's accepted source record were
not regenerated. No Hermes update or configuration change was needed.
