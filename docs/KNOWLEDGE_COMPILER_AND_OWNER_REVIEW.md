# Knowledge Compiler and Owner Review Desk

Mission Control v0.9 turns an owner-approved source package into a reviewable, source-linked knowledge proposal without calling a model or treating extracted text as runtime truth.

## Owner workflow

1. Seal local TXT, Markdown, JSON, CSV, YAML, or YML files in the Knowledge Loading Dock.
2. Inspect the package filenames, byte counts, and hashes, then approve the exact package.
3. Click **Compile for Review**.
4. Inspect every proposed FAQ, policy, capability, or reference statement in the Owner Review Desk.
5. Approve or reject every entry. Each row shows its source filename, line range, file hash, and extraction method.
6. Resolve red conflict groups by approving at most one conflicting answer, or reject all answers in that group.
7. Finalize the review. The resulting review record is immutable and hash-bound to the exact compilation.
8. Select the reviewed package and commission the client-specific X-Agent.

## What compilation means

The compiler performs deterministic extraction only:

- `Q:` / `A:` pairs and structured question/answer objects become FAQ proposals.
- JSON and YAML scalar fields become source-linked field proposals.
- CSV rows become FAQ or structured row proposals.
- Text and Markdown paragraphs become exact paragraph proposals.
- Policy and capability labels use visible keyword rules; they are not model inferences.

The compiler caps a compilation at 200 entries and records discarded-entry counts. It detects different answers to the same normalized FAQ question and creates explicit conflict groups.

## State and authority

The relevant states are:

- `COMPILED_PENDING_OWNER_REVIEW`
- `OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD`
- `OWNER_REVIEW_COMPLETE_NO_APPROVED_KNOWLEDGE`

Commissioning with a knowledge package requires the ready state and preserves the package, compilation, and review hashes in the mission's knowledge reference. The reviewed entries are still not installed runtime knowledge. The next Factory slice must convert approved entries into the instance's tested KB and system-prompt knowledge layer.

Compilation and review authorize no provider call, Hermes inference, ANAM action, credential access, external transmission, repository mutation, deployment, or production action.

## Storage

The immutable source package remains under:

`knowledge-packages/<package-id>/`

Derived compilations and revision-safe reviews are stored under:

`knowledge-packages/<package-id>/derived/compilations/<compilation-id>/`

Each finalized review is a new record under the compilation's `reviews/` directory. Previous reviews are preserved.

## Verification

Run:

```powershell
python -B scripts\verify_knowledge_dock_and_options_v0_1.py
```

The verification proves source-file integrity, compilation and review hashes, source anchors, mandatory conflict resolution, commissioning gating, client isolation, and generated candidate tests.
