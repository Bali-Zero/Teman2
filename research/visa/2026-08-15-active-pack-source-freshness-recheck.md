---
date: 2026-08-15
domain: visa
client_case: none — active RulePack source-freshness recheck handoff
sources:
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.signed.json
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
  - apps/backend-rag/backend/services/visa_engine/evaluate_path.py
  - apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py
adversarial_review: kimi-k3
status: BLOCKED — legal source re-verification and signed successor pack required
---

# Active RulePack source-freshness recheck handoff

## Result

At `2026-08-14T18:24:38Z` (`2026-08-15 02:24:38 WITA`), the repository's
signed RulePack sequence 7, marked `PRODUCTION` in its artifact metadata
(`2026.8.11`, payload SHA-256
`3d068aef2dca40f1efb74bdd3f8859e767c000282ab8299ac7f277b0b9719f82`)
contains 20 `OFFICIAL_PORTAL` source records subject to a seven-day
maximum-age policy:

- 19 records were verified at `2026-08-06T06:19:49Z` and became stale after
  `2026-08-13T06:19:49Z`;
- the VoA-country-list record was verified at `2026-08-08T00:00:00Z` and is
  current through exactly `2026-08-15T00:00:00Z` (08:00 WITA), then becomes
  stale.

This recheck did not query which pack was active in the deployed service. In
the exact checkout pinned to
`4367d2c7aa2739011a7bedadb46d374424b6041a`, a local replay of the signed
sequence-7 artifact at `2026-08-14T22:21:37Z` ran through
`apply_public_policy_adapters`, the same adapter function called by `/evaluate`
in that checkout. This is code-level parity only, not a claim about deployed
production behavior. It produced 5/20 fixture matches and 15 divergences; the
matching personas were 3, 4, 12, 13 and 18. All 15 divergences remain
`unexplained` in the G-b ledger because no accepted-explanation file was
supplied. Separately, the replay establishes the proximate decision cause
for nine of those divergences: personas that the pure evaluator gave supported
candidates (7, 8, 9, 10, 11, 14, 16, 17 and 19) were converted to
`HUMAN_REVIEW_REQUIRED` by source-freshness holds. This is operationally safer
than returning stale-source candidates, but it means the current pack is not a
fresh G-b evidence basis and remains **SHADOW / ENFORCE NO-GO**.

Throughout this artifact, a source verified at time T with a seven-day maximum
age is `CURRENT` at T+7 days and `STALE` at every instant after T+7 days.
Accordingly, the VoA record is still current at exactly 08:00 WITA and all 20
records are stale from the first instant after 08:00 WITA on 2026-08-15.

This artifact does not change a source record, claim that an HTTP response is a
legal verification, sign a RulePack, activate a pack, or authorize ENFORCE.

## Read-only reachability probe

Between `2026-08-14T18:21Z` and `18:24Z`, a redirect-following read-only probe
fetched every canonical URL with a 25-second per-request timeout. All 20
returned HTTP 200. That establishes current reachability only. It does not
establish unchanged legal meaning, source authority, applicability, or content
equivalence to the stored `content_sha256`.

| Source group | Count | Pack freshness at measurement | Probe |
|---|---:|---|---|
| Calling-visa list, bridging press/service pages, immigration-stay index, eVisa student FAQ, E31A/B/C/D/E/F/G/H/J, D1/D2/D12, E30A/B | 19 | `STALE` | 19/19 HTTP 200 |
| VoA country list | 1 | `CURRENT` at and before `2026-08-15T00:00:00Z`; `STALE` immediately after | HTTP 200 |

Canonical URLs requiring article-by-article re-verification:

1. [Calling-visa country list](https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa)
2. [Bridging-visa press release](https://www.imigrasi.go.id/siaran_pers/2024/04/23/izin-tinggal-peralihan-jembatani-proses-transisi-izin-tinggal-wna-di-ri)
3. [ITK-to-ITAS service page](https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian/izin-tinggal-kunjungan-menjadi-izin-tinggal-terbatas)
4. [Immigration-stay index](https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian)
5. [eVisa student FAQ](https://evisa.imigrasi.go.id/front/faq/08cdfd2e-873e-4de7-9eeb-8f485828c155)
6. [E31A](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31A)
7. [E31B](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31B)
8. [E31C](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31C)
9. [E31D](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31D)
10. [E31E](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31E)
11. [E31F](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31F)
12. [E31G](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31G)
13. [E31H](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31H)
14. [E31J](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31J)
15. [D1](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D1)
16. [D2](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D2)
17. [D12](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D12)
18. [E30A](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30A)
19. [E30B](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30B)
20. [VoA country list](https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival)

## Exact decision impact

| Personas | Raw evaluator result | Public policy result | Freshness reason and decisive records |
|---|---|---|---|
| 7, 8 | E31-family candidates | `HUMAN_REVIEW_REQUIRED` | `DECISIVE_SOURCE_STALE`; E31A/E31B/E31D as used by each decision |
| 9, 10, 16, 17 | D12 | `HUMAN_REVIEW_REQUIRED` | `DECISIVE_SOURCE_STALE`; D12 and immigration-stay index |
| 11, 14, 19 | supported candidates | `HUMAN_REVIEW_REQUIRED` | `SAFETY_CRITICAL_SOURCE_STALE`; active safety floor includes calling-visa list, E31E, D12 and E30A |

The minor privacy hold separately changes persona 6 and is not a source-
freshness effect. Personas already in review or input states are not overwritten
by the global freshness adapter, by design.

## Replay audit anchors

- Fixture corpus: the 20 canonical personas in
  `backend/tests/services/visa_engine/test_evaluator_gold.py`, using expectations
  from `backend/tests/services/visa_engine/_gold_fixtures.py`.
- Adapter implementation under review: commit
  `4367d2c7aa2739011a7bedadb46d374424b6041a` (PR #4200), specifically
  `evaluate_path.apply_public_policy_adapters` and the offline caller in
  `gold_replay_driver.py`.
- Command: from `apps/backend-rag`, run
  `PYTHONPATH=. python -m backend.scripts.visa_engine.gold_replay_driver --offline
  --out /tmp/visa-gold-replay-policy-parity-4367d2c7.json` in that exact
  checkout.
- Captured report: generated `2026-08-14T22:21:37.736863+00:00`, local path
  `/tmp/visa-gold-replay-policy-parity-4367d2c7.json`, SHA-256
  `520d1205735edb0955aed337196fbcdcd21809c5b20690458a9c03bea7ee2d58`.
  This handoff summarizes the report; it does not treat the temporary path as a
  durable evidence store or claim production-path equivalence.

This final-candidate replay supersedes the preliminary 4/20 run performed on
`ff05743d930d068ff57dc5b92478658c20854eb2`. The later #4200 fix makes the
offline caller use the request's effective review flags, the same accessor
used by both public endpoint paths in that checkout. This establishes
code-level parity for the reviewed paths, not production equivalence; the
replay evidence is pinned to the corrected SHA rather than blended with the
preliminary observation.

## Current family-source finding

The live E31 pages remain sufficient to keep the family refuter blocked, not to
clear it:

- E31B is titled for a spouse of an ITAS/ITAP holder, while its application
  section asks for a letter from a spouse who is an Indonesian citizen. This
  internal inconsistency cannot justify the current fail-open E31B predicate.
- E31D asks for an application from an Indonesian father or mother plus birth,
  parental-marriage and Indonesian family-card evidence. Generic family intent
  without the named relationship evidence cannot justify an E31D candidate.

These are source-review observations only. The accountable legal reviewer must
decide the normative interpretation and whether the portal inconsistency needs
escalation to another primary authority.

## Successor-pack acceptance contract

The freshness blocker closes only when all of the following are recorded:

1. A named legal reviewer re-fetches and semantically reviews all 20 canonical
   sources, including country-list membership and every product requirement.
2. The reviewer records the retrieval bytes or reviewed extract using a
   documented canonicalization procedure. The existing pack does not document
   enough here to infer that raw HTTP bytes equal `content_sha256`; do not
   fabricate comparability.
3. Every changed source becomes a new version with correct
   `supersedes_source_record_id`, legal and recorded periods, content hash,
   `retrieved_at`, `verified_at` and `verified_by`. Merely advancing
   `verified_at` is forbidden.
4. An unsigned successor source pack compiles and passes positive, sibling-
   negative, source-freshness and full gold replay checks. E31B/E31D defects,
   D12 route semantics and the G-b disposition matrix remain independent
   blockers even if freshness is restored. The D12 issue is the still-open
   owner/legal decision over whether the visit route may substitute for the
   requested direct-onshore, status-bridging or investor-status route in
   personas 9, 10, 16 and 17; it is tracked in PR #4199 and is not resolved by
   a freshness refresh.
5. A different-family reviewer grades the exact diff and replay, then Fable 5
   supplies the final Gear-3 verdict on the exact SHA.
6. Signing, activation and any ENFORCE decision happen in separate audited
   steps with the required owner/legal authorization. No agent may infer those
   approvals from a green probe or green CI.

Until this contract is complete, the correct disposition is: **sources reachable
at the bounded probe time, repository pack freshness expired, offline adapter
fail-safe observed, live deployment state not established by this artifact,
G-b RED, SHADOW retained, ENFORCE NO-GO**.

## Adversarial review

Kimi K3 reviewed a prior non-PII draft pinned to the preliminary
`ff05743d930d068ff57dc5b92478658c20854eb2` replay through the repository's
pinned no-tools wrapper and returned **SHIP-WITH-FIXES** for that draft. That
review confirmed its 20-source arithmetic, seven-day boundary, WITA conversion,
HTTP-versus-legal distinction, nine-persona freshness-conversion tally and
separation of signing, activation and ENFORCE authority. Its required and
recommended findings were adopted:

- the preliminary 16 G-b ledger divergences were no longer mislabeled as causally
  unexplained; the text distinguishes the absent accepted-explanation ledger
  from the nine observed freshness conversions;
- the inclusive freshness boundary is defined consistently;
- the exact fixture, code revision, command, report timestamp and report hash
  anchor the replay without claiming that a temporary local report is durable;
  and
- the previously orphaned D12 blocker now states its route-semantics question
  and points to the dedicated disposition artifact.

A fresh full-document Kimi pass then reviewed the non-PII final-candidate text
with its evidence manifest and returned **SHIP-WITH-FIXES**. It identified
three scope defects, all adopted here: the draft no longer implies that the
offline replay established the active production pack or live runtime state;
the earlier review is explicitly pinned to the preliminary SHA; and adapter
parity is described as code-level parity rather than production equivalence.

The wrapper refused a subsequent full-document rereview locally because its
numeric-shape PII guard triggered before transmission; that attempt produced no
review verdict and was not bypassed. A PII-safe projection limited to the
corrected passages returned **SHIP-WITH-FIXES** for two non-blocking wording
findings: describe the source records as subject to the seven-day maximum-age
policy and repeat the final SHA in the result paragraph. Both were adopted. A
final bounded projection returned **SHIP**, closed both findings and reported
no new contradiction. That final verdict covers only the projected corrected
passages; it supplements, but does not replace, the required exact-SHA Fable
gate before merge.
