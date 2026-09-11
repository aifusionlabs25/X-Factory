# Prepared-agent integration — owner testing checkpoint

September 5, 2026. Status: **ready for local owner testing, not production certification**.

## What to test

Open http://127.0.0.1:8877/ and refresh the page. Start with an opportunity and a public company website. Shape the starting point, then choose **Prepare my agent**. That explicitly starts bounded research and the three specialist drafts; it does not approve knowledge or build anything.

The new review package should contain the proposed job and role, relevant sourced Knowledge Bank answers, visible gaps, and a complete System Prompt drafted by Troy. Expand the answers to check their sources. Edit if needed, save, and refresh affected drafts when prompted. Then approve the reviewed package and separately choose **Build this reviewed agent**.

The built-candidate button opens the existing provider-free local preview. The separate **Test the reviewed System Prompt with Luna** section exercises the actual reviewed prompt and approved Knowledge Bank through Hermes. Start a fresh text session, then send a question. Each Send uses one model call; seven calls maximum per session. The optional Dojo button uses a separate five-call regression on the same frozen text runtime.

Preparation: up to eight research calls plus one each for Aria, OMNARA and Troy, using openai-codex / gpt-5.6-luna at low reasoning. Specialist tools are disabled. Authentication remains read-only. Failures do not automatically retry. These calls are not claimed to be unlimited or free.

## Implemented

- Existing Atlas/broker and builders retained; no historical repository copied into the Factory.
- One project ID with immutable, hashed revisions, distinct preparation/approval/build states, and source/output receipts.
- Actual Hermes execution for Aria's design, OMNARA's selection of relevant source passages and Troy's tailored prompt/style. Deterministic source copying, binding compilation and local builds are labeled separately.
- Draft preparation is automated. Knowledge approval and build remain separate owner actions.
- Reviewed prompt bytes and reviewed knowledge are preserved in the build. Edited inputs invalidate dependent approval/candidate evidence. Unsaved UI edits cannot be approved as though saved.
- Source answers retain URLs, dates and source text. Owner changes remain labeled as owner changes, not original website quotations.
- Reopen saved work, collapsible source answers, readable controls, no forced scroll when preparing. Seven role recipes remain available; Aria recommends one rather than always using the original chassis.
- Optional Hunter adapter starts fresh company research from the selected receipt's website/owner goal. It neither imports old research as approved facts nor claims Hunter's sales qualification was refreshed.
- Shared candidate-bound text runtime for owner testing and Dojo, strict output schema, preserved raw response evidence, no response sanitizer or hidden evaluator goals.
- Missing evidence, interrupted runtime, changed candidate or incomplete scorecard cannot pass. Corrected details are checked in the returned handoff, not merely mentioned in a visitor message.

## Evidence and limits

- Eight prepared-agent integration fixtures pass, including two populated role builds, edits/reopen, source rejection, Hunter handoff, interrupted Dojo and exact candidate binding.
- Six Dojo gate tests and 22 research/runtime guard tests pass.
- Desktop/mobile browser regression passes preparation → edit → reopen → approval → real local build → candidate, plus text-test controls and fresh UI session. Model responses in this browser test are explicit fixtures; it uses no provider calls.
- Actual public research + Aria + OMNARA + Troy produced 16 sourced draft answers and a full prompt in `verification/prepared-live-20260905-132548`. Six model calls total. A prompt-ID formatting incompatibility was repaired by a deterministic binding index before review, using saved responses and no repeated call. The recovered project remains unapproved with no mission. This is a recovered live proof, not a fresh uninterrupted post-fix run.
- The first isolated native text canary stopped before worker execution because of a long Windows working directory. Its failure is retained. The launcher now uses the repository root as its working directory while retaining the bounded evidence-write directory.
- The latest five-call native text canary is `verification/candidate-text-live-20260905-135507`. All nine state/handoff assertions passed. Its overall decision is **REVIEW_REQUIRED**, not PASS: the pinned legacy hard rule flags a denial that repeats the visitor's hypothetical $7 price. Both raw and delivered findings remain visible. No rule was silently waived, and no release clearance was granted.
- Dojo is a focused five-call regression, not complete semantic/source-entailment certification. Role-specific held-out coverage, all output channels, ANAM delivery and production integration remain additional work. A browser-fixture PASS does not certify model behavior.
- Full company/job changes require fresh dependent drafting; fine-grained per-section regeneration is not implemented. Older revisions remain preserved. Research access failures remain actionable gaps, not invented knowledge.
- Text testing is currently in the Factory's prepared-agent panel; it is not an automatic live-provider connection inside every exported application. Existing export/repository flows remain in place.
- External pinned X-LINK hard-rule code must remain present and match its recorded hash. Missing or changed source blocks the gate.

## Recovery

Before implementation, the complete Factory tree, including `.git`, ignored durable state, uncommitted and untracked source, was captured in:

`C:\Users\AI Fusion Labs\Documents\Codex\2026-08-18\okay-hermes-desktop-agent-just-had\checkpoints\factory-20260905-131530`

The DPAPI-encrypted archive contains 11,170 files and 6,806 directories. Every archived entry was decrypted and hash-verified in memory against a second unchanged-source scan. This was not a restored-app boot drill. Recovery requires this Windows account's DPAPI keys. Originals were left intact; no reset, checkout, stash or commit was used. External Hermes credentials were not copied or modified. Do not restore old authentication during an application rollback.

Implementation sources and testing records remain uncommitted in the working tree. Preserve the encrypted baseline and current working files before any subsequent migration.
