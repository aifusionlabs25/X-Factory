# Factory control-plane integration v0.1

This phase adopts the architecture-reset contracts without creating a second
project manager. `x_factory/prepared_agent_v0_1.py` remains the authoritative
append-only project history (`drafts/prepared-agents/project-*/revisions`).

After an approved local candidate is built and frozen, the Factory now emits a
strict, pending `accepted-package-draft` envelope under the candidate's
`input/control-plane/` directory. The envelope points to the exact prompt,
approved knowledge snapshot, runtime contract, runtime settings, candidate
binding, and existing evaluation evidence. Every path is contained by the
candidate and every referenced SHA-256 is checked before the project revision
records the link.

This is a handoff boundary, not an acceptance or release. `accepted_by` and
`accepted_at` remain null, the evaluation verdict remains `pending`, and no
ANAM/provider/profile/deployment action is performed. A later phase can turn a
passing, owner-accepted draft into an `accepted_package` using the explicit
`promote_package_draft` gate, and then a separate `release_record`. The gate
requires a passing evaluation bound to the exact content-manifest hash and the
named release authority; it is not called by the normal local build.

Phase 3 adds `prepare_preview_release_record`. Given an already accepted
package and explicit local artifact bindings, it records a `prepared` preview
release with verification still pending. It does not start a server, activate
ANAM, install a profile, deploy an application, or mark anything live.

Phase 4 adds `verify_preview_release_record`. It checks observed configuration,
verification evidence, and rollback-test evidence by exact hash, then writes a
new immutable `verified` preview record. The original `prepared` record is
retained. A verified local preview is still not a production release.

Phase 5 adds the read-only registry projection at
`/api/control-plane/registry`. It is derived from prepared-agent revisions and
candidate control-plane artifacts, and reports the current lane without adding
another writable status store.

Phase 6 adds a locked production-promotion plan and preflight. It requires a
verified preview, rollback proof, and an explicit Rob approval receipt. The
plan always starts with execution disabled and zero provider actions; the local
Factory intentionally has no production executor wired into it.

The three adopted schemas are vendored byte-for-byte in
`contracts/control_plane/`; `adoption-manifest.v1.json` records their source
and hashes. Runtime implementation details are captured by the existing frozen
`text-runtime-candidate.v0.1.json`, so the candidate runtime file itself is
not modified and existing candidate hashes remain valid.
