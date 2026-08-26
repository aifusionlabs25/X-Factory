# Chassis Depot and Commissioning Bay

## Plain-English purpose

The Chassis Depot stores reusable X-Agent job foundations. A chassis knows how to perform a role, but it does not belong to a client and does not have a human identity, avatar, credentials, or production authority.

The Commissioning Bay turns one chassis into a named client-specific X-Agent. It never changes the stored chassis. Every commissioned instance records exactly which chassis version it came from.

## Current Factory flow

1. Select a locally validated chassis.
2. Supply the X-Agent name, client, users, personality, and client-specific additions.
3. Select a presence mode independently from the X-Agent's name.
4. Record client context for the later Knowledge Loading Dock.
5. Compile the instance through Atlas, Aria, Vera, Mason, and final Vera.
6. Preserve the commissioning record, chassis hash, candidate files, and tests.
7. Continue through Hermes review, presence proof, Repo Foundry, and owner-controlled release gates.

## The identity model

- **X-Agent name:** the person users meet, such as Mia or Ava.
- **Role title:** the reusable job, such as Operational QA Concierge.
- **Client name:** the organization the commissioned instance serves.
- **Visual persona:** an ANAM/avatar asset selected independently from the X-Agent name.
- **Display name:** `X-Agent name — Role title`.
- **Technical candidate ID:** a stable slug derived for local build addressing; future releases should add a permanent opaque ID for rename safety.

## What is reusable

- Role workflow and prompt foundation
- Notes, qualification, and handoff contracts
- Boundaries and escalation behavior
- Compatible feature modules
- Required knowledge-material checklist
- Reusable test scenarios

## What must be commissioned

- X-Agent and client identity
- Client-specific rules and claims
- Approved knowledge files
- Branding, avatar, and voice
- Credentials and integrations
- Final evaluation additions
- Deployment and production authority

## Current boundary

Version 0.7 records client context but does not ingest files or treat that context as runtime truth. The next department is the **Knowledge Loading Dock**, which will intake client documents, classify authority, detect contradictions and missing materials, build the knowledge manifest, and generate client-specific tests before the commissioned agent can claim domain knowledge.

## Disciplined path to a 36-chassis showroom

1. Prove two real commissioned agents from the first chassis.
2. Add the Knowledge Loading Dock and module configurator.
3. Build five high-demand chassis and measure repeatability.
4. Standardize chassis acceptance and upgrade rules.
5. Expand in controlled batches until the showroom has 36 validated roles.

No chassis is labeled production-approved. Only a fully commissioned and separately certified X-Agent may advance toward release.
