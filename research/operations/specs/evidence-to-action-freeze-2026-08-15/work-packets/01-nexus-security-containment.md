---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 01 — NEXUS Security Containment (Wave 0, P0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this packet task-by-task. Steps use checkbox syntax for tracking. Run the implementation on the authoritative Pro; Air-M5 is a thin client.

**Wave:** 0

**Priority:** P0

**Depends on:** Packet 04 before Task 7 live cutover; Tasks 1–6 may prepare, test, and shadow in parallel.

**Goal:** Contain NEXUS to the Pro loopback boundary, remove secret material from source and service definitions, and prevent precise private-location fields from leaving the restricted graph through the operator UI or its APIs.

**Architecture:** Keep the raw, source-backed graph local and restricted. Apply defense in depth at four boundaries: host binding, runtime secret injection, API projection, and operational verification. Do not remodel or bulk-rewrite the graph in this wave.

**Tech Stack:** macOS launchd, Docker Compose, Neo4j 5 Community, Next.js 16, TypeScript, Python 3.11+, pytest, macOS Keychain.

**Primary repository:** /Users/nuzantara/Desktop/OSINT-Nexus on Pro.

**Binding policy input:** /Users/nuzantara/Desktop/nuzantara/docs/mata-garuda/04-SECURITY-FIREWALL.md. This file is read-only for this packet.

## Mission

Execute an emergency containment pass without destroying data or broadening access:

1. Make the NEXUS UI and Neo4j listen only on loopback.
2. Remove every tracked or deployed plaintext Neo4j credential discovered by the audit, rotate the credential through an operator-held ceremony, and make missing credentials fail closed.
3. Keep raw source evidence in the restricted graph while returning only redacted property-location projections from the UI and API.
4. Expose the legacy Neo4j label BankAccount to application consumers as DeclaredCashAggregate, with CashEquivalent accepted as the human-readable synonym.
5. Prove containment with automated tests and live socket checks before declaring Wave 0 complete.

LHKPN means Laporan Harta Kekayaan Penyelenggara Negara, the public wealth declaration filed through KPK/eLHKPN. It is not a bank statement, a transaction feed, or evidence of a private bank account. The existing BankAccount node is a synthetic representation of the declared aggregate Kas dan Setara Kas. This packet must not describe or expose it as an actual account.

## Live Baseline to Re-Verify

The following was observed on Pro on 2026-08-15 WITA. Treat it as the frozen comparison baseline, not as permission to skip a fresh preflight:

- Runtime repository: /Users/nuzantara/Desktop/OSINT-Nexus at short commit c4a619d.
- The runtime checkout was substantially dirty and its branch was ahead of its tracked peer. Preserve that state before creating an implementation worktree.
- com.osint-nexus.h24 and com.osint-nexus.ui were running.
- The active UI was ui-v2 on TCP port 3333.
- The UI listened on all interfaces.
- Neo4j exposed host ports 17474 and 17687 on all interfaces.
- The entity API had no application-level authentication middleware.
- The UI returned precise property location and dimension fields.
- Secret values existed in tracked or deployed configuration. Never print, copy, diff, or quote those values in an artifact.
- Graph baseline: 23,559 nodes and 16,648 relationships, including 48 Official, 44 LhkpnReport, 32 Property, 25 Vehicle, 11 legacy BankAccount nodes, 5,011 SourceDocument, and 16,152 Claim nodes.

The implementation session must capture a new sanitized baseline containing only commit IDs, dirty-file names, process states, bind addresses, counts, and hashes. It must not contain names of officials, addresses, public-identifier values, source bodies, or credentials.

## Explicit Scope and File Ownership

Create a dedicated OSINT-Nexus worktree from an operator-approved snapshot of the current Pro runtime. Never edit the dirty runtime checkout directly.

The implementation session owns only these source paths in /Users/nuzantara/Desktop/OSINT-Nexus:

- docker-compose.yml
- launchd/com.osint-nexus.ui.plist
- ui-v2/src/lib/neo4j.ts
- bridge/consumer.py
- ui-v2/src/lib/data/entity.ts
- ui-v2/src/lib/queries.ts
- ui-v2/src/app/api/graph/entity/[label]/[name]/route.ts
- ui-v2/src/lib/security/redaction.ts, new
- scripts/nexus_security_doctor.py, new
- scripts/run_nexus_ui_secure.sh, new
- tests/test_nexus_security_doctor.py, new
- tests/test_nexus_secret_boundary.py, new
- ui-v2/src/lib/security/redaction.test.ts, new only if the existing package can execute it without adding an unreviewed framework
- docs/runbooks/nexus-security-containment.md, new

The operational cutover may update the deployed copy:

- /Users/nuzantara/Library/LaunchAgents/com.osint-nexus.ui.plist

That deployed plist is not a source-of-truth substitute. It must be byte-derived from the reviewed repository template after environment-specific paths are resolved, and its installed hash must be recorded.

No file in /Users/nuzantara/Desktop/nuzantara is owned by this packet. The firewall document there is a frozen policy input. Do not edit Mata Garuda, NAGA, Intel Lake, WR2, WR3, blog, Magazine, or SEO code.

If implementation requires a path outside this ownership list, stop and request a scope amendment. Do not silently expand the packet.

## Frozen Contracts

### Local-only service boundary

- The production UI must bind to 127.0.0.1:3333. Binding to 0.0.0.0, an empty host, or the Pro Tailscale/LAN address is a hard failure.
- Neo4j Browser and Bolt must publish only as 127.0.0.1:17474 and 127.0.0.1:17687.
- No reverse proxy, tunnel, share link, public hostname, Vercel deployment, or Fly deployment is allowed.
- If loopback containment cannot be proven, keep the affected service stopped.

### Secret boundary

- No password, token, API key, credential URI, or secret-shaped fallback may exist in tracked files, plist values, command arguments, test fixtures, logs, reports, or screenshots.
- ui-v2/src/lib/neo4j.ts and bridge/consumer.py must require runtime configuration and fail closed when it is absent.
- The launchd path must obtain the Neo4j password at process start from an operator-approved macOS Keychain item through scripts/run_nexus_ui_secure.sh. The wrapper may export the secret only into the child process environment and must never echo it.
- A secret rotation is an operator-gated action. The implementation session prepares and verifies the mechanism; it does not display the old or new value.
- Rollback must never restore a known-exposed credential.

### Read-only UI boundary

- Neo4j sessions created by the UI remain READ mode.
- API routes must not add graph mutation capabilities.
- The security doctor must reject any UI query module that creates a WRITE session.

### Location-redaction boundary

- The raw source-backed location may remain in restricted Neo4j evidence when legally collected, but the UI/API projection must not return street, banjar, village, parcel, house number, coordinates, dimensions tied to a location, or a verbatim lokasi value.
- The default display value is the coarsest already-structured public region, such as province or regency. If no safe coarse field exists, return the literal value Location withheld.
- Redaction happens before serialization, not only in React presentation.
- The route must use an allow-list response serializer. Passing through arbitrary Neo4j properties is forbidden.

### LHKPN cash semantics

- Preserve the current Neo4j label during Wave 0 to avoid a risky live migration.
- The API and UI must map legacy BankAccount to type DeclaredCashAggregate and label Declared cash and cash equivalents.
- The object may contain the declared aggregate amount and report year when source-backed.
- It must never expose or imply bank name, account number, holder number, transaction, or statement.

### Promotion and downstream boundary

- Claim promotion remains fail closed: verified review state, confidence at or above the canonical threshold, non-private PII class, exact source-document reference, and an explicit future apply operation governed by the canonical `ActionIntent` -> exact `ApprovalReceipt` -> immutable started `ExecutionAttempt` -> typed `OperationalReceipt` chain.
- This packet does not enable a promoter.
- NEXUS dossier data never flows directly to blog, Magazine, SEO, WR2, WR3, WhatsApp, email, or any public surface.
- Any later downstream product receives only an independently approved, sanitized brief.

## Deliverables

1. A sanitized preflight receipt with source commit, worktree commit, dirty-path inventory, active service paths, listener addresses, aggregate graph counts, and hashes of reviewed configuration files.
2. Loopback-only Docker Compose port publication.
3. A reviewed launchd template and secure UI launcher with no secret values in either file.
4. Fail-closed Neo4j configuration in the UI and bridge.
5. A location-redaction and allow-list serialization layer used by the entity API.
6. A conceptual API/UI alias from legacy BankAccount to DeclaredCashAggregate.
7. A deterministic security doctor that reports PASS or non-zero failure without revealing sensitive values.
8. Unit, static, build, shadow, and live containment evidence.
9. A concise operator runbook for credential rotation, cutover, verification, and rollback.
10. An independent-review packet containing only the diff, test results, sanitized doctor output, socket matrix, graph count comparison, and deployed-template hash.

## Non-Goals

- Do not redesign NEXUS authentication or introduce a remote login service.
- Do not expose NEXUS through a VPN proxy, browser relay, public URL, Vercel, or Fly.
- Do not rename or delete live Neo4j labels in this wave.
- Do not change LHKPN parsing, entity resolution, bridge message semantics, gap handling, anomaly scoring, or promotion logic.
- Do not ingest new records, repair the KPK collector, drain Redis streams, or run a bulk graph rewrite.
- Do not copy the OSINT database, graph export, or source documents to Air-M5 or any cloud service.
- Do not touch editorial publishing.

## Dependencies and Stop Conditions

- Work must execute on Pro. Air-M5 may edit the worktree, initiate explicit SSH control commands, and inspect aggregate sanitized health/status receipts only. It must not open or proxy the NEXUS UI, query Neo4j or person-specific endpoints, receive dossier/entity results, or host Neo4j, Docker, rendering, or raw OSINT data.
- Before worktree creation, the owner must choose how to preserve the dirty OSINT-Nexus runtime state. A source snapshot or commit is required; do not reset, stash, or overwrite it autonomously.
- The operator must be present for credential rotation and the production service restart.
- Docker volume identity and mount state must be recorded before any container recreation.
- If Keychain is not readable in the launchd user context, stop. Do not fall back to a plist secret, shell history, plaintext env file, or source constant.
- If remote reachability cannot be tested without disclosing data, test only TCP connection refusal; never request a dossier remotely.

## Implementation Sequence

### Task 1: Freeze and prove the pre-change state

- [ ] Record the OSINT-Nexus source commit, branch, dirty-path list, and active launchd program paths without reading secret values.
- [ ] Record Docker container identity, named volume identity, aggregate graph counts, and current listeners.
- [ ] Hash the source and deployed plist after redacting values from any human-readable report.
- [ ] Create the isolated implementation worktree from the operator-approved source snapshot.
- [ ] Run the existing OSINT-Nexus unit suite relevant to UI data, graph loading, and provenance. Preserve failures as baseline rather than fixing unrelated debt.

Expected evidence: a sanitized baseline receipt that contains no entity names, locations, source text, or credential material.

### Task 2: Write failing containment tests

- [ ] Add tests proving Compose rejects host-wide publication and accepts only explicit loopback mappings.
- [ ] Add tests proving the UI and bridge raise a configuration error when the Neo4j password is absent.
- [ ] Add tests proving no tracked or deployed template contains a secret-shaped literal or password fallback.
- [ ] Add a synthetic entity fixture whose raw graph record contains a precise address and dimensions; assert the serialized API projection contains neither.
- [ ] Add a synthetic legacy BankAccount record; assert the API projection emits DeclaredCashAggregate and no bank-account semantics.
- [ ] Run the focused tests and preserve the expected RED output.

The synthetic fixture must use invented names, invented addresses, and invented identifiers.

### Task 3: Implement secret and listener containment

- [ ] Change Docker Compose mappings to explicit 127.0.0.1 host binds.
- [ ] Remove credential fallbacks from ui-v2/src/lib/neo4j.ts and bridge/consumer.py.
- [ ] Implement scripts/run_nexus_ui_secure.sh so it reads one named Keychain item, validates non-empty output, exports it only to the child Next process, and exits non-zero without starting Next when unavailable.
- [ ] Update the repository launchd template to call the secure wrapper, bind Next explicitly to 127.0.0.1, and contain no secret value.
- [ ] Ensure logs report only error class and configuration key name, never secret length, prefix, suffix, hash, or value.
- [ ] Re-run the focused tests until GREEN.

### Task 4: Implement safe API projection

- [ ] Add ui-v2/src/lib/security/redaction.ts with an allow-list serializer for entity dossiers.
- [ ] Make the entity data layer and route serialize through that function before returning data.
- [ ] Remove exact property locations and location-linked dimensions from the response contract.
- [ ] Map the legacy BankAccount graph label to DeclaredCashAggregate in the application response.
- [ ] Keep evidence identifiers, source titles, and safe aggregate values only when they already pass the frozen policy.
- [ ] Run the redaction tests, TypeScript typecheck, and Next production build.

### Task 5: Build the deterministic security doctor

- [ ] Implement scripts/nexus_security_doctor.py using the Python standard library only.
- [ ] Make it inspect Compose host mappings, repository plist arguments, deployed plist arguments, source secret fallbacks, active socket listeners, UI read-mode configuration, and presence of the allow-list serializer.
- [ ] Make every failure produce a non-zero exit status and a reason code without content payloads.
- [ ] Add tests for PASS, all-interface bind, missing Keychain wrapper, secret literal, write-mode UI session, and absent redaction serializer.
- [ ] Run the doctor against the worktree before touching live services.

### Task 6: Shadow validation

- [ ] Build ui-v2 from the worktree.
- [ ] Start the candidate UI on 127.0.0.1:3334 using the secure wrapper and the read-only graph connection.
- [ ] Query only aggregate stats and synthetic fixture routes. Do not log real dossier bodies.
- [ ] Compare aggregate counts and response schemas between current and shadow UI.
- [ ] Verify the shadow process is unreachable through the Pro LAN/Tailscale address while loopback remains healthy.
- [ ] Keep the production service unchanged until independent review passes this shadow gate.

### Task 7: Effect-authorized production cutover

- [ ] Obtain an independent **pre-cutover verification PASS** over the source diff, tests, build, doctor output, and shadow evidence, and materialize it as an exact canonical `VerificationReceipt`. This makes the candidate eligible; it does not authorize a live effect.
- [ ] Stop before every live effect unless Packet 04's canonical repository, validators, and independently reviewed containment/manual authority adapter are available in the target environment. Do not invent an emergency schema or wait on the later Packet 12 runtime service.
- [ ] Before creating an action spec, bind the secret-free, location-redacted pre-cutover artifact to one exact durable source-document revision `{document_id, document_version_id, document_content_hash}` in protected storage; create one canonical sanitized `IntelEvent` whose `payload_ref` points to that exact revision; create canonical `Evidence` whose `source_event_ref` binds the exact event and whose document fields bind the same revision; then create an exact `Claim` bound to that evidence. The event, evidence, and claim retain the component-wise maximum risk and sensitivity inherited from their inputs—redaction alone never lowers either axis. Create one exact `WorkflowRun` snapshot whose inputs include the event, evidence, claim, source revision hash, and pre-cutover `VerificationReceipt`; then create one sanitized, operator-authored containment `DecisionPacket` that references the exact claim, evidence, source revision, and run. Because the packet derives from restricted NEXUS work and is the only lower-sensitivity projection in this chain, require a valid `SanitizationReceipt` indexed by the exact packet hash before materialization.
- [ ] For each live effect—Neo4j credential rotation, launchd-template installation, Neo4j host-binding mutation, UI restart, and H24-consumer restart—create a separate exact `RequestedActionSpec` whose `decision_packet_ref` binds that containment packet and whose lineage binds that exact `WorkflowRun`; use only the narrowly scoped Packet 04 adapter to atomically materialize its `ActionItem` and `ActionIntent`; then obtain a separate, unexpired owner `ApprovalReceipt`. The adapter performs no effect and accepts only these five enumerated containment action types with exact target and argument hashes. A tightly coupled maintenance window may share one operator session, but its five authorities remain independently hash-bound and revocable.
- [ ] Have the operator rotate the Neo4j credential into the approved Keychain item without exposing it to the session transcript. At start, append the immutable `ExecutionAttempt`; at completion, append its typed `OperationalReceipt`.
- [ ] Install only the exact reviewed launchd-template hash under its own approved intent, attempt, and terminal receipt.
- [ ] Change only the exact approved Neo4j host-binding configuration while preserving the named data volume; bind the attempt and result to the pre-change and post-change hashes.
- [ ] Restart the UI and H24 consumer only under their respective exact approvals, attempts, and terminal receipts in the bounded maintenance window.
- [ ] Run local health, remote refusal, aggregate graph-count, and log-redaction checks as post-cutover evidence.
- [ ] Keep services stopped if any P0 check fails; rollback actions that themselves change production state require their own exact authority chain unless the approved intent explicitly and narrowly pre-authorized that rollback target and argument hash.

### Task 8: Close with evidence

- [ ] Run the complete focused test set, typecheck, production build, security doctor, socket matrix, and graph-count comparison.
- [ ] Confirm no secret-shaped value or precise property location appears in git diff, plist, process arguments, logs, screenshots, or review artifacts.
- [ ] Write the runbook and the final sanitized containment receipt.
- [ ] Commit atomically on the feature branch. Do not merge, deploy beyond the operator-gated Pro cutover, or push to main.

## Golden Set and Baseline

Use a committed synthetic golden set containing:

- one Official with a precise raw property address and dimensions;
- one Official with only a safe province field;
- one LhkpnReport with a synthetic legacy BankAccount aggregate;
- one SourceDocument and Claim with public-role classification;
- one private/sensitive location classification that must be suppressed;
- one record containing unknown optional properties to prove the serializer drops unlisted fields.

Required expectations:

- Precise address tokens and dimensions are absent from serialized responses.
- A safe coarse province or regency may remain.
- Missing safe geography produces Location withheld.
- BankAccount is never emitted as an application type.
- DeclaredCashAggregate contains only source-backed aggregate amount and report year.
- Unknown properties never pass through.
- Aggregate graph counts are identical before and after Wave 0.

## Tests and Evaluations

Run from the OSINT-Nexus worktree with its existing virtual environment:

    PYTHONPATH=. .venv/bin/python -m pytest \
      tests/test_nexus_security_doctor.py \
      tests/test_nexus_secret_boundary.py \
      tests/test_graph_provenance_loader.py \
      tests/test_provenance_gate.py \
      tests/test_lhkpn_loader.py -q

Run the UI checks:

    cd ui-v2
    npm run typecheck
    npm run build

Run the security doctor:

    PYTHONPATH=. .venv/bin/python scripts/nexus_security_doctor.py --source-root /absolute/worktree/path

Run live socket verification only after pre-cutover independent verification, effect-specific owner approvals, and the recorded operator cutover attempts. Report endpoint, address family, bind address, and result; do not request dossier content from a remote interface.

## Shadow and Canary

Shadow:

- Candidate UI on 127.0.0.1:3334.
- Read-only graph session.
- No write query and no public proxy.
- Compare only health, schema shape, aggregate counts, and synthetic redaction.
- Minimum observation: 30 minutes with no restart loop and no credential or payload leakage in logs.

Canary:

- Production UI moves to the reviewed secure launcher.
- Neo4j host binding changes without deleting or recreating the data volume.
- From Pro loopback: UI health and aggregate stats succeed.
- From Air-M5 to the Pro Tailscale/LAN address: TCP connection to 3333, 17474, and 17687 is refused or times out.
- Any unexpected remote success is a hard rollback trigger.

## Metrics and Exit Criteria

Wave 0 passes only when all conditions are true:

- Zero listeners on 0.0.0.0 or non-loopback addresses for ports 3333, 17474, and 17687.
- Zero secret values or credential fallbacks in owned source files, deployed plist, command arguments, logs, and artifacts.
- Missing Keychain credential causes a clean non-zero startup failure.
- UI Neo4j sessions remain read-only.
- One hundred percent of synthetic precise-location cases are suppressed before serialization.
- One hundred percent of synthetic legacy BankAccount records are projected as DeclaredCashAggregate.
- Node and relationship counts match the pre-change snapshot exactly.
- Local health checks pass and remote refusal checks pass.
- No editorial, communication, or public publishing action occurred.

## Rollback

- Preserve the pre-change source commit, deployed-plist hash, service state, and Docker volume identity.
- Revert the feature commit or reinstall the previously reviewed non-secret template if application behavior fails.
- Do not restore an exposed credential; use the newly rotated credential or keep the service stopped.
- Do not delete, rename, prune, or recreate the Neo4j data volume.
- If precise locations leak after cutover, stop the UI immediately while leaving the database local and intact.
- If only the UI fails, keep Neo4j loopback-only and roll back the UI binary/template.
- Record every rollback action in a sanitized receipt.

## Security and Privacy Review

The reviewer must explicitly verify:

- local-only binding at source and runtime;
- no credential material in any diff or artifact;
- no raw OSINT copied to Air-M5, cloud storage, prompts, or public logs;
- precise-location suppression occurs before API serialization;
- LHKPN cash is described only as a declared aggregate;
- no dossier row reaches editorial or messaging surfaces;
- fail-closed promotion remains unchanged.

## Independent Reviewer Handoff

The implementer must stop after preparing the feature branch and shadow evidence. A reviewer who did not write the changes performs two distinct reviews.

Pre-cutover review inputs:

1. source and worktree commit hashes;
2. exact owned-file diff;
3. RED then GREEN focused-test output;
4. UI typecheck and build output;
5. sanitized security-doctor result;
6. shadow listener matrix and aggregate graph-count baseline;
7. explicit confirmation that no secret or PII was included.

A pre-cutover PASS establishes technical eligibility only. The separate effect-specific owner `ApprovalReceipt` records described in Task 7 authorize the live actions; reviewer verification never does.

Post-cutover review inputs:

1. exact pre-cutover `VerificationReceipt`, durable source-document revision tuple, canonical `IntelEvent`, `Evidence`, `Claim`, `WorkflowRun`, containment `DecisionPacket`, and packet-bound `SanitizationReceipt` references, with proof that intermediate classification was not lowered;
2. exact `RequestedActionSpec`, atomically materialized `ActionItem`, `ActionIntent`, owner `ApprovalReceipt`, immutable started `ExecutionAttempt`, and terminal `OperationalReceipt` references for every live effect;
3. pre/post listener matrix;
4. pre/post aggregate graph-count comparison;
5. proof that the deployed template hash matches the reviewed template;
6. rollback or stopped-service receipts for any failed check;
7. repeated confirmation that no secret, private location, or dossier payload entered an artifact.

The reviewer returns a separate post-cutover PASS or FAIL with findings by severity. A FAIL triggers the already authorized narrow rollback or a new owner-authorized rollback action; it never retrospectively approves the cutover. The implementer never self-approves, merges to main, publishes, or weakens a failed check.
