# Hunter refresh connection status

The Factory supports the original, hash-pinned Hunter checkpoint and the saved owner-review receipts created from it. The lead inbox is optional. Owner ideas, company names, and websites do not require a Hunter record.

## What a refresh currently does

**Prepare Hunter Refresh** prepares one prospect's research request and displays the text for copying into Hunter. It does not run Hunter. Existing request files remain unchanged. The response and interface state that the return path requires manual review and a new reviewed source binding.

`drafts/hunter/incoming` is a reserved research dropbox, not an import authority. Files there are not accepted into the lead inbox. A result's self-calculated hash, changed source hash, current date, or `OWNER_REVIEWED_DRAFT_ONLY` label cannot establish that the owner reviewed new research. Earlier descriptions of an automatically validated return overstated this connection.

## Current checks

- Inbox receipts must match the pinned source, prospect snapshot, expected receipt filename, canonical form fields, and saved record hash.
- Existing handoffs must still match their originating reviewed receipt and fields.
- **Use in Factory** delegates to the original draft-reopening flow, preserving source freshness, qualification, rendered-source evidence, source URLs, and chassis checks.
- Stale records display **Needs fresh research**. Preparing a request does not clear this status.

Implementing automatic refresh execution and return still requires a source registration and owner-review flow. It must preserve the prior research and review history, validate actual observation evidence, and record a new owner decision before a result can populate the Factory form.

## Verification

The inbox suite covers existing handoff reuse, stale research, missing rendered evidence despite a fresh date, a rehashed handoff with changed fields, a rehashed receipt with changed source content, forged owner-review claims in incoming research, and invalid saved refresh-request hashes. Tests use isolated synthetic records and make no provider or outreach calls.
