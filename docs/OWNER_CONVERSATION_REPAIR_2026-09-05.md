# Owner conversation repair

## Scope

The prepared, built agent now opens with an always-visible **Talk to your agent** section. It uses the existing exact-candidate Hermes/Luna text runtime; there is no new model implementation, prompt rewrite, candidate rebuild, knowledge approval, ANAM action, deployment, or credential change.

- First Send starts the text session automatically. Opening the page and choosing a suggested question make no provider calls.
- Visible elapsed-time feedback, disabled input while awaiting a response, seven-message ceiling, and no automatic retry on failure.
- Fresh session clears the local transcript and starts a new server session on the next Send.
- The conversation DOM, session closure, unfinished message and transcript survive same-candidate project polling. A different candidate does not inherit them. Page reload intentionally starts a fresh conversation.
- Technical statement matching is a collapsed secondary tool, explicitly not the conversational model. Its no-match label no longer claims a quality pass or that anything was sent to staff.
- Existing Dojo verdict remains REVIEW_REQUIRED. No findings were waived.

## Verification

- `verify_joe_conversation.cjs` default mode: six mocked replies through the actual owner UI; automatic session start, progress, input lock, fresh session, desktop/mobile checks passed. Mock responses do not establish answer quality.
- `verify_prepared_disclosures.cjs`: repeated polling, owner collapse/reopen and final-result retention passed; includes preservation of unfinished chat input.
- `verify_prepared_agent_browser.py`: isolated synthetic preparation/edit/reopen/approval/build/conversation flow passed with fixture providers only. User candidate was not altered.
- JavaScript syntax and diff whitespace checks passed.

## Outstanding live verification

The attempted `verify_joe_conversation.cjs --live` launch was rejected by the execution approval layer before running. Zero new live model calls were made. Do not bypass the rejection.

Required owner permission: send the existing approved Joe Rushing candidate System Prompt and Knowledge Bank, plus fictional test messages/history, exclusively to openai-codex / gpt-5.6-luna through Hermes for up to six calls, no retries. Existing read-only authentication safeguards remain unchanged. No tools, rebuild, ANAM, deployment, or external delivery.

Planned checks: misspelled services question; agent purpose; unsupported pool-pump question; urgent AC request; Lubbock-to-Wolfforth correction/handoff; fresh-session isolation. The script records raw accepted responses for human review and performs bounded assertions; it is not full certification.

Candidate preserved: project-0b8e596080b7a6ee0bd97576, mission draft-rushing-emergency-intake-guide-home-services-con-20260906-003543-22f5d3. Existing candidate artifacts and prompt remain unchanged. Source worktree remains uncommitted; no reset, cleanup, stash or destructive rollback performed.
