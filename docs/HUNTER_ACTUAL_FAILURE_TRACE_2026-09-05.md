# Actual Hunter/Factory failure trace

## Evidence, not a reconstruction of unrecorded mouse movements

The Factory server's request log, the current Chrome and Codex browser pages, and the nine immutable revisions of `project-0b8e596080b7a6ee0bd97576` were inspected. There is no complete click recorder; disabled-button clicks cannot be reconstructed from HTTP logs. No unrelated browsing content was inspected.

Observed paths:

1. Repeated `GET /api/hunter/inbox` succeeded. This reads the fixed historical Hunter source, not a new hunt. The pinned source is the August 28 checkpoint with earlier observations. Reloading does not update those dates or qualification scores.
2. `POST /api/prepared-from-hunter` succeeded repeatedly but correctly reused the same project. The UI incorrectly kept suggesting a fresh start rather than explicitly reopening that project.
3. The legacy `/api/hunter/review` succeeded, followed by `/api/hunter/reopen-draft` returning 400. That path applies the historical-source freshness gate and is a dead end for this stale lead.
4. Original research at 14:29 Phoenix time used three model calls and six tool calls. Retrieval succeeded, but the Factory rejected a combined legal-name / brand-name string because it did not occur as one exact name in a cited source.
5. Explicit refreshes at 16:59 and 17:00 each used three model calls and five tool calls. The native worker stopped at citation assembly. It discarded the raw response on that failure path, so the exact historical schema/passage violation cannot now be recovered. Calling this a confirmed connectivity failure would be incorrect.
6. The preparation wrapper masked all of these failures as “could not retrieve usable sources.” The worker also incorrectly recommended sign-in checks for citation parsing failures.

## Repairs

- Require a single evidence-exact company name in the researcher instructions, without accepting invented combined aliases or weakening the validator.
- Preserve raw non-secret-like responses and captured public-source records before citation assembly; keep a bounded validation diagnostic without copying credentials or provider exceptions.
- Distinguish output-validation failure from runtime/connection failure. Preserve the research job's actual safe failure message in the project.
- Expose saved preparation status on the lead and label its action Open saved preparation when one exists.
- Remove legacy send/use/review detours from the normal owner journey. Their backend records/contracts are retained, not deleted or silently approved.
- Rename the list reload control Reload saved leads. Historical sales scores remain explicitly historical.
- Opening preparation hides the competing stale lead card; running preparation shows actual stage messages and a last-checked indicator.

## Verification scope

A separate bounded live Joe Rushing diagnostic passed source validation using three model calls and five tool calls. The actual saved owner project was subsequently reopened through the Codex browser and explicitly refreshed once after the runtime fix. Previous failed attempts remain intact. No knowledge approval, build, outreach or production operation was authorized by this repair.

The seven citation fixtures, twelve research fixtures, eight preparation fixtures, nine Hunter inbox fixtures and 22 runtime guard fixtures passed. The old browser fixture success alone was insufficient evidence for this real lead.

The actual saved owner project subsequently completed at revision 16, status NEEDS_REVIEW: four research calls and one each for Aria, OMNARA and Troy, thirteen sourced Knowledge Bank draft answers, and an 8,271-character System Prompt. No approval or mission was created. The Codex browser was reloaded and the saved package reopened visibly; the approval checkbox remained unchecked and the approval button disabled. Previous failure records were not replaced or relabeled as successes. This proves draft preparation for the actual Joe Rushing project, not build, behavioral certification, or GTM requalification.

## Still not implemented

The Factory does not automatically re-run Hunter's full GTM sales qualification or refresh its historical prospect report. Fresh company research for an X-Agent is a separate operation. No stale lead was relabeled as newly qualified, and no new score was invented. This distinction remains a product limitation, not a user mistake.
