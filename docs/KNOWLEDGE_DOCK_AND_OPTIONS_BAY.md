# Knowledge Loading Dock and Module Options Bay

Mission Control v0.8 adds the first two post-chassis commissioning departments.

## Plain-English flow

1. Choose a validated role chassis in the Chassis Depot.
2. Give the commissioned X-Agent its name, client, personality, audience, and presence.
3. Load a small client document package in the Knowledge Loading Dock.
4. Review the visible label, filenames, byte counts, and short hashes, then approve that exact hash-bound package.
5. Choose compatible options in the Module Options Bay.
6. Commission the local X-Agent candidate through the existing Atlas → Aria → Vera → Mason → Vera pipeline.

The Commissioning Bay is the primary path and its final button always names the target agent (`RUN FACTORY FOR LEROY`). The older blank-brief path is closed by default, contains no demo values, and is labeled as an advanced alternate entrance for roles that do not match any validated chassis.

## Knowledge boundary

Accepted in v0.8: TXT, Markdown, JSON, CSV, YAML, and YML; at most 8 files, 256 KB per file, and 512 KB total.

Every file is stored locally with its original name, byte count, media type, and SHA-256 digest. The package manifest is itself hash-bound. Owner approval is a separate immutable record bound to that manifest.

The states are intentionally separate:

- `INGESTED_PENDING_OWNER_APPROVAL`
- `OWNER_APPROVED_FOR_COMMISSIONING`
- `ATTACHED_FOR_SEMANTIC_COMPILATION_NOT_RUNTIME`

v0.8 does not convert document text into runtime answers. Semantic compilation, conflict resolution, citations, retrieval, and client-specific knowledge tests remain a later stage. This prevents an upload from silently becoming authoritative agent behavior.

Credential-like content, binary data, unsafe filenames, oversized packages, mutated files, and unapproved packages fail closed.

## Module boundary

The six chassis modules are visible and locked. Three allowlisted commissioning options are available:

- Approved client knowledge pack
- Appointment request packet
- Lead qualification scorecard

The external-action runtime remains visible but prohibited. No option authorizes sending, booking, provider mutation, installation, deployment, or production.

## Local storage

Knowledge packages are stored under `knowledge-packages/<package-id>/`. Commissioned missions store only the hash-bound package reference under `input/knowledge-package-reference.v0.1.json`; one client's source files are not copied into another client's mission.

## Verification

Run:

```powershell
python -B scripts\verify_knowledge_dock_and_options_v0_1.py
```

The verification covers file and manifest hashes, approval binding, secret rejection, allowlist enforcement, external-action rejection, knowledge-module gating, client isolation, and generated candidate tests. It makes zero provider calls and writes only to the dedicated verification sandbox.
