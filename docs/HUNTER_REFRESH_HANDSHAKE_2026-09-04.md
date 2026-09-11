# Hunter refresh handshake v0.1

The Factory does not launch or control the Hunter Hermes profile. When a lead is
stale, Mission Control's **Prepare Hunter Refresh** action creates one bounded
request at `drafts/hunter-refresh/requests/<prospect-id>.json`.

The request contains:

- the original source and receipt hashes;
- one prospect and up to six already-cited public URLs;
- a read-only re-verification prompt;
- the fixed return contract `drafts/hunter/incoming`;
- guardrails requiring zero Knowledge Bank approvals, missions, provider calls,
  and outreach.

The owner runs that request in the separate Hunter profile. A validated
`OWNER_REVIEWED_DRAFT_ONLY` result may be placed in the declared incoming
dropbox using `contracts/hunter_refresh_result.v0.1.schema.json`; the Factory
validates the result hash, refresh-id binding, and newer source-run hash before
showing it as a fresh lead. A refresh request alone never renews evidence, clears
a HOLD, or changes the existing receipt.

This is intentionally a handshake rather than an implicit Hermes bridge: Hunter
remains the research sidecar, the Factory remains the build system, and the owner
decides when a fresh result is allowed back into the queue.
