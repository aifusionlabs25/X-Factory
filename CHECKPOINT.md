# Mission Control 1.9 Owner-Testing Baseline

Lifecycle label: `OWNER_TESTING_BASELINE`

This repository is the canonical local development history for the X-Factory at the first working owner-testing checkpoint.

## Baseline claim

- Local deterministic Factory flow is working.
- Website-backed approved knowledge is bound visibly before Build.
- Factory Preview and the Porter-generated complete local app distinguish informational unknowns from captured service requests.
- Provider calls, installation, deployment, release, and production remain separate gates.

## Canonical tag

`x-factory-mission-control-1.9-owner-testing-baseline`

## Recovery model

- Git commit and tag: canonical development history and inexpensive rollback.
- Static ZIP: self-contained recovery artifact produced from the exact tag.
- `CHECKPOINT_FILE_SHA256.json`: SHA-256 inventory for every included file except the manifest itself.
- External checkpoint record: binds the Git commit, tag, ZIP hash, verification result, and lifecycle label.

## Restore

1. Extract the rollback ZIP into a new empty directory.
2. Verify every entry listed in `CHECKPOINT_FILE_SHA256.json`.
3. Read `EXCLUSIONS.md`; missing authentication and runtime-state directories are intentional.
4. Run `scripts/verify_checkpoint_restore.ps1` with suitable local Python and Node executables.
5. Confirm the script reports `CHECKPOINT_RESTORE_SMOKE_PASS` and `factory_version` 1.9.

Never restore this baseline over a live working directory. Restore to a clean sibling directory, verify it, and then deliberately choose whether to replace or compare the active tree.
