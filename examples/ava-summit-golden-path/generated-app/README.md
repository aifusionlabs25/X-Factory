# Ava — Home Services Concierge

This repository was created by the X-Factory Porter Repo Foundry from the certified local mission `draft-ava-home-services-concierge-20260826-014140-bb4a8c`.

## Purpose

Help prospective customers understand Summit Home Services, answer common questions, qualify their service needs, and prepare a clean handoff for a human team member. Do not invent pricing, promise appointment availability, or claim services that are not in the approved knowledge.

## Start the contained local preview

```powershell
python -B -m src.x_agent_runtime --port 8787
```

Then open `http://127.0.0.1:8787/`.

## Verify the repository

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
```

## Repository status

- Repo ID: `ava-home-services-concierge-16ca9753`
- Mode: local staging preview
- Hermes provider transport: not connected
- ANAM provider transport: not connected
- Credentials: not included
- Deployment: not authorized
- Production: not approved
- Instance knowledge: LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED
- Hermes runtime package: LOCAL_RUNTIME_PACKAGE_READY_CANARY_INACTIVE

The browser preview is deterministic and provider-free. When present, `runtime/` contains the sealed Hermes profile blueprint and inactive one-call Luna canary. No profile is installed and no provider is contacted by this repository.
