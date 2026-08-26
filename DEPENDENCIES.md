# Baseline Dependency Record

Verified on Windows NT 10.0.26200.0 with:

- Python 3.11.9
- `jsonschema` 4.25.1
- Node.js 24.19.0
- Git for Windows 2.52.0

Mission Control is a local Python HTTP service with a static browser UI. The core restore smoke test does not require provider access, Hermes authentication, ANAM, deployment credentials, or network access beyond localhost.

The wider development machine may contain other Python and Node runtimes. Those are not included in the rollback bundle.
