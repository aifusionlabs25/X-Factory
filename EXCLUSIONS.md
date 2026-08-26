# Owner-Testing Baseline Exclusions

The Mission Control 1.9 checkpoint is intentionally a product baseline, not a copy of mutable desktop or provider state.

## Never included

- API keys, passwords, tokens, credentials, or `.env` files
- Hermes OAuth/authentication files or locks
- Codex authentication or credential stores
- Browser profiles, cookies, history, or session state
- Hermes chats, sessions, memories, caches, logs, locks, heartbeat files, WAL files, or local databases
- Provider runtime state or installed Hermes profile state
- Temporary directories, Python bytecode, build caches, and local server logs
- Deployment credentials, production configuration, or production approval

## Historical Factory-floor material excluded from canonical source

- prior interactive `runs/`
- prior generated `repos/`
- prior `knowledge-packages/`
- historical `reviews/`, `approvals/`, `disclosures/`, and `canaries/`
- generated `builds/`, install images, and bulk `verification/` output

These directories remain untouched in the working area. They are excluded only from the canonical Git baseline and rollback bundle.

## Explicit exception: reproducibility fixture

The exact Ava/Summit proof selected for this checkpoint is copied into `examples/ava-summit-golden-path/`. It is evidence that the Factory works; it is not canonical Factory identity and does not authorize provider calls, installation, deployment, or production use.
