# X-Factory Mission Control · Hosted Preview

This directory is a Vercel-safe, read-only packaging of the Mission Control cockpit.

It intentionally exposes the committed role/chassis reference data and the owner workflow UI, but it does not pretend that an ephemeral web deployment can safely replace the local Factory. Research, owner approval, Knowledge Bank compilation, candidate builds, Dojo runs, and release actions stay on the local server at `http://127.0.0.1:8877/` until a separately governed persistent backend and authentication layer are added.

The `hosted-mode.js` adapter returns deterministic reference data for the UI and turns mutation requests into an explicit read-only response. This keeps a hosted link useful for orientation and review without silently creating missions, approving knowledge, calling providers, or writing client data.

For an owner-visible smoke test, append `?mode=ephemeral-test` to the hosted URL. That mode runs the Prepare → Review → Approve → Build → Test → Dojo rehearsal in browser memory only. The exact candidate is carried into the generated app link so a new tab can be tested; use fictional data only because the snapshot appears in that test URL. Refreshing the Factory tab resets its working session. No Vercel, GitHub, ANAM, Hermes, provider, or local-repository writes occur. It is a visual/e2e rehearsal, not a replacement for the local Factory's persistent workflow.
