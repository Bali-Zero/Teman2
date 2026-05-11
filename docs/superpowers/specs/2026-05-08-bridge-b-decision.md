# FASE 6 — Bridge B (Fly→Mini KG read access): Architecture decision

**Date:** 2026-05-08
**Owner:** sub-session executor (autonomous, L2)
**Tracking:** PR #489 deferred §"Future Bridge B" → this decision
**Outcome:** **Option D — Defer indefinitely.** No code work in this PR.
**Next action:** Zero ratifies (or rejects) this decision in the consolidation issue. Reopen with a doctrine-extension PR if Bridge B is to proceed.

---

## 1. Executive summary

Bridge B's stated goal — let end-user Zantara on Fly.io read mata-garuda KG metadata — is **not achievable today without amending the explicit `apps/mata-garuda/CLAUDE.md` §1.4 deroga**. The deroga as written 2026-05-06 (in the same PR #489 that shipped Bridge A) authorizes KG metadata export only "verso organi locali Pro via Tailscale loopback (NO Fly, NO cloud, NO frontend, NO team)". Bridge B's target — backend-rag on Fly — falls under each of the four explicit exclusions.

Sub-session autonomy contract (`AUTONOMOUS_OPS.md` L2) does not cover doctrine mutations; mata-garuda CLAUDE.md §1 declares Lamarckian rule: "Le mutazioni al GENOME richiedono review umana (Zero) — **NO auto-apply**". The §1.4 deroga is itself a labelled "Deroga esplicita autorizzata da Zero 2026-05-06". Extending its scope to permit Fly export is structurally outside L2 autonomy.

The brief author anticipated this in §0b ("Pillar 3 §1.4 mata-garuda compliance: **hard constraint**") and made Option D ("Defer") an explicit choice in §2. The reality-check at the brief head was based on outdated entity counts (it claimed 6 entities; live verification at spawn shows 409/1549/622, matching the W2 design doc). The doctrine and the data are both in the state W2 documented; the deroga did not silently widen between 2026-05-06 and 2026-05-08.

**Recommendation:** ratify Option D, document the constraint explicitly in this spec, and gate any future Bridge B work behind a separate Zero-approved doctrine PR that updates §1.4 with verbatim Fly-allowed language.

---

## 2. Pre-spawn reality check (verified 2026-05-08 by orchestrator)

| Item | Brief assumed | Actual |
|---|---|---|
| Bridge A (Mini side) | Live, port 8990 | ✅ Live, PID 71339, `/health` returns 200 |
| KG content (entities/relations/observations) | 6 / 4 / 6 | ❌ **409 / 1549 / 622** (W2 design figures hold) |
| Backend-rag on Fly | 2 machines (api, rag) sin region | ✅ Confirmed, image `01KR1MWKES8BXE8NM14CTJ1D5V` |
| Tailscale tailnet | Pro+Mini, Fly NOT enrolled | ✅ Confirmed (4 devices: nuzantara/iphone175/Air-offline/mini-pro2) |
| backend-rag existing tailnet/proxy infra | Pure greenfield | ✅ Zero hits for `100.93.236.6`/`tailscale`/`mini-pro2` in `apps/backend-rag/backend/**.py` |
| Tigris (FYI for Option C) | (not in brief) | Already wired: `nuzantara-warroom-images.fly.storage.tigris.dev` referenced in Canva renderer + LinkedIn/blog publisher tests |
| `mata_garuda` PG schema (FYI) | (not in brief) | Exists on `nuzantara-postgres` but only carries `tag_intel_finding` PG function (migration 156); KG entities/relations/observations remain SQLite-only on Mini |

The brief's reality-check note "Mini KG SQLite 6 entities / 4 relations / 6 observations" appears to have been a copy-paste from a freshly-seeded test DB or a confused memory; live KG matches the W2 design figures and the 2026-05-06 audit.

---

## 3. The hard constraint — verbatim doctrine text

### `apps/mata-garuda/CLAUDE.md` §1 OSINT blindato (current)

> **MAI esportare verso:**
> - `apps/mouth/` o qualsiasi frontend
> - clienti, team Bali Zero, utenti esterni
> - **Fly.io**, Vercel, Google Cloud, AWS, qualsiasi cloud
> - Repo pubblici, gist, pastebin

### `apps/mata-garuda/CLAUDE.md` §1.4 Eccezione Pillar 3 SYMBIOSIS (current)

> Deroga esplicita autorizzata da Zero 2026-05-06: il KG SQLite locale (~/.agent/mata-garuda/kg.db) può esporre metadata operativi (entity names, type, neighbor list, observation_count) verso **organi locali Pro via Tailscale loopback (NO Fly, NO cloud, NO frontend, NO team).**

### `apps/mata-garuda/CLAUDE.md` §1 Lamarckian mandatory

> Le mutazioni al GENOME richiedono review umana (Zero) — **NO auto-apply**.

### `apps/mata-garuda/CLAUDE.md` §2 Comportamento Claude Code

> Chiedi SOLO per: **decisioni architetturali**, cancellazioni git, **modifiche GENOME.md senza review**.

The §1.4 deroga is part of `apps/mata-garuda/CLAUDE.md`, the project-level GENOME-class instruction file for the mata-garuda app. Extending it to authorize Fly export is a "modifica GENOME.md" that §2 explicitly requires Zero review for.

---

## 4. Options scored

Brief §2 enumerates A / B / C / D. Each is scored against brief §0b weighting: (1) §1.4 compliance — HARD; (2) reversibility; (3) attack surface; (4) implementation cost; (5) latency target.

### Option A — Tailscale subnet router on Mini exposing 8990 to Fly

| Criterion | Verdict |
|---|---|
| §1.4 compliance | ❌ Violates "NO Fly". Requires deroga rewrite. |
| Reversibility | ⚠️ Medium: roll back Dockerfile + revoke Tailscale auth key + Fly secrets rotation. ~1-2h. |
| Attack surface | New: `tailscaled` daemon in every Fly container, persistent Tailscale auth key in Fly secrets (rotation = redeploy), subnet router config on Mini affects whole tailnet. |
| Implementation cost | 8-12h (Dockerfile, init script, auth-key persistence, deploy testing) + 24h canary. |
| Latency | p50 ~200-300ms cross-region; cold-start adds Tailscale handshake ≥3s on Fly auto-stop wake. |
| AUTONOMOUS_OPS L2 fit | Editing Dockerfile is allowed; **adding a new external provider integration (Tailscale on Fly cluster) requires confirmation**; doctrine mutation requires Zero. |

**Verdict: NOT VIABLE today.** Two separate Zero-only gates (§1.4 doctrine + new-external-provider).

### Option B — Backend-rag proxy via Mini public exposure

The brief itself notes "B without infrastructure addition is dead — same gap as A." Variant requiring Cloudflare tunnel or public HTTPS endpoint on Mini.

| Criterion | Verdict |
|---|---|
| §1.4 compliance | ❌❌ Violates `apps/mata-garuda/CLAUDE.md` §1 "MAI esportare verso ... qualsiasi cloud" + §1.4 "NO cloud". Also conflicts with W2 design §5 "Bind only to Tailscale interface or 127.0.0.1. Refuse 0.0.0.0/::". |
| Reversibility | ⚠️ Medium: tunnel teardown + DNS revert. |
| Attack surface | **Largest of all options**: public HTTPS edge to mata-garuda KG, even if behind auth. Explicit §1.2 violation (no public exposure). |
| Implementation cost | 6-8h + 24h canary + ongoing tunnel ops. |
| Latency | p50 ~400-500ms (extra HTTPS hop). |
| AUTONOMOUS_OPS L2 fit | New paid external provider (Cloudflare tunnel if not already in use) requires confirmation; doctrine mutation requires Zero. |

**Verdict: NOT VIABLE.** Adds the largest attack surface for the smallest doctrine win. Strictly worse than A on both compliance and security axes.

### Option C — Tigris snapshot mirror (Mini publishes; Fly reads)

| Criterion | Verdict |
|---|---|
| §1.4 compliance | ❌ Violates "NO Fly, NO cloud, NO frontend". Snapshot to Tigris is "esportare verso Fly.io / cloud" by definition (Tigris IS Fly's S3-compatible object storage). |
| Reversibility | ✅ High: stop publisher LaunchAgent + delete bucket. <30 min. |
| Attack surface | Bucket access requires Tigris credentials (already wired in backend-rag); credentials in Fly secrets; snapshot world-cred-readable to all `nuzantara-rag` machines. Defensible IF every snapshot row is metadata-only and the test suite enforces forbidden-key absence. |
| Implementation cost | 6-8h (publisher + reader + snapshot integrity tests + LaunchAgent + Tigris bucket setup) + 24h canary. |
| Latency | <50ms p50 (in-region read on Fly). Best of all options. |
| AUTONOMOUS_OPS L2 fit | Tigris already in use → no new-external-provider gate. Still requires §1.4 doctrine mutation. |
| Side-effect | New snapshot artifact at-rest: every Fly machine reads a structured JSONL of every entity name + type + neighbour list + last_seen + source_url. Even with `observation.value` excluded, this is the operational graph of Bali Zero's KG sitting in object storage with the same trust boundary as the KG itself. |

**Verdict: NOT VIABLE today.** Best technical fit, but still doctrine-non-compliant. Would be the recommended option in a hypothetical doctrine-extension PR.

### Option D — Defer Bridge B indefinitely

| Criterion | Verdict |
|---|---|
| §1.4 compliance | ✅ |
| Reversibility | ✅ Pure docs PR. Trivial revert. |
| Attack surface | None. |
| Implementation cost | 30 min (this doc). |
| Latency target | n/a (no path exists). |
| AUTONOMOUS_OPS L2 fit | Pure docs. Fully autonomous. |
| User-facing cost | End-user Zantara on Fly cannot answer "what does our KG say about X?". Fallback today: Zero queries Bridge A manually via Pro-side stdio MCP and shares the answer. |

**Verdict: ✅ Selected.**

---

## 5. Why sub-session cannot extend the §1.4 deroga itself

The brief §0b says "decision is taken by sub-session autonomously". For an architecture pick among compliant options, this is correct. But every compliant Bridge B implementation requires first extending §1.4 to authorize Fly export. That extension is:

1. **A `apps/mata-garuda/CLAUDE.md` edit.** §2 of that file requires Zero review for "modifiche GENOME.md senza review".
2. **Inverts an explicit "MAI esportare verso ... Fly.io" rule** from §1 OSINT blindato.
3. **Removes a "NO Fly, NO cloud, NO frontend" guardrail** from the deroga that Zero spelled out verbatim 2 days ago. The current §1.4 wording is itself the result of Zero's deliberate scope-narrowing during PR #489 review.
4. **Has business-rule consequences** that sub-session cannot verify alone: who at Bali Zero is authorized to ask the KG about which entities; whether end-user-facing KG access changes Mata Garuda's "Owner: Zero (esclusivo, nessun team member)" identity declaration in §0; whether `kita.balizero.com` users (5000+ Bali Zero clients) seeing entity names from the OSINT graph creates legal exposure (per `apps/mata-garuda/CLAUDE.md` §0 the OSINT data is "proprietà Zero").

A doctrine extension that addresses (1)-(4) cannot be drafted by sub-session and merged via L2 auto-merge. It is a Zero-only decision document.

---

## 6. What "Defer" means concretely

Defer is not "pretend nothing happened". It means:

1. **This spec is the artifact** that the W2 design's §14 Open Question 5 ("Future Bridge B ... Decision deferred") was waiting for. The decision is now on file.
2. **End-user Zantara on Fly does NOT have KG access today.** If a user on `kita.balizero.com` asks "what does our knowledge graph say about Imigrasi?", backend-rag responds with the existing RAG path (Qdrant + KBLI KB), not the mata-garuda KG.
3. **Pro-side organs (Claude Code stdio, OpenClaw, Cowork) still have full Bridge A access.** Zero, working from the Pro, can query the KG via the existing `kg_intel_*` MCP tools and relay findings to a client conversation manually if required.
4. **No code lands in this PR.** No `apps/backend-rag/backend/app/routers/kg_intel_proxy.py`, no `kg_snapshot_publisher.py` LaunchAgent on Mini, no Dockerfile change, no Fly secret addition.
5. **The W2 design `§14 Open Questions item 5` text** can be tightened in a follow-up to "Decision: deferred per docs/superpowers/specs/2026-05-08-bridge-b-decision.md" — but that update is also out of scope for this PR (it touches `apps/mata-garuda/`-adjacent doctrine cross-references and is best done with the eventual doctrine PR).

---

## 7. What a future Bridge B PR would need (not in scope here)

Documented for the next agent (Zero or sub-session under a new brief that includes a Zero-signed doctrine extension):

1. **Doctrine PR first.** A standalone PR amending `apps/mata-garuda/CLAUDE.md` §1.4 with verbatim Zero-approved language widening scope. Suggested template (NOT Zero-approved, illustrative only):

   > §1.4-bis Eccezione Pillar 3 SYMBIOSIS — KG metadata sharing su Fly.io
   >
   > Deroga esplicita autorizzata da Zero <DATA>: il KG SQLite locale può esporre metadata operativi (sottoinsieme strettamente ridotto: name, type, source_count, last_seen, neighbor_names, observation_count) verso `apps/backend-rag` su Fly.io tramite **<MECCANISMO>** (Option C Tigris snapshot / Option A Tailscale on Fly). Sono ammessi solo gli stessi campi consentiti dal §1.4 originale. Restano **VIETATI** observation.value, evidence_url, aliases_json, content/title/body/excerpt/summary/field — verifica enforced via test unit `test_no_forbidden_fields_in_payload`.

2. **Architecture choice** between A (Tailscale on Fly) and C (Tigris snapshot). Recommended: **Option C** because (a) lowest attack surface — no new daemon in Fly containers, (b) Tigris already in use, no new external provider, (c) lowest latency, (d) most reversible, (e) snapshot ⊆ metadata-only is easiest to enforce in CI via key-presence test.

3. **Audit fields beyond §1.4 compliance:**
   - **Per-request audit log** on backend-rag side (which user/session asked which entity, retention 30d, surfaced to Zero on Telegram weekly).
   - **Rate limiting** per session ID — KG queries are not free conversation.
   - **End-user UX gating** — should `kita.balizero.com` clients see entity names at all, or only Bali Zero team logged in via SSO? Today's RBAC (`zero@`, `antonellosiano@`, `asya@balizero.com` admin; team scoped to assigned_to; clients see only own data) does not yet have a "KG metadata read" permission.

4. **Snapshot sanitisation guarantees (Option C):** the Mini-side publisher must run the same `_assert_no_forbidden_keys()` that the Mini-side HTTP API runs (W2 design §5 "Forbidden in any payload"). Failure mode: publisher refuses to upload, alerts Zero on Telegram. Snapshot reader on Fly runs the same assertion on read as defense-in-depth.

5. **Operational safety nets:**
   - Tigris bucket ACL: read-only credentials on Fly, write-only on Mini. Different credential pair.
   - Snapshot freshness budget: 30 min staleness target. Reader returns `kg_unavailable` if snapshot timestamp > 2h.
   - Rollback drill: documented script that empties the bucket and removes the LaunchAgent in <30s.

6. **Cross-LLM review** via federation_orchestrator with `redteam` prompt before merge — required for any change to KG export surface (precedent: PR #489 had tri-LLM review per W2 §9).

---

## 8. Decisions taken without Zero (for consolidation issue)

Per brief §0b and §"Final gate — Zero review consolidation (post-merge)", the following autonomous decisions are recorded for Zero's asynchronous review:

| # | Decision | Rationale |
|---|---|---|
| 1 | Selected Option D (Defer) | Options A/B/C all violate `apps/mata-garuda/CLAUDE.md` §1 + §1.4 verbatim; doctrine mutation is Zero-only per §1 Lamarckian rule + §2 review requirement. Brief §0b makes §1.4 compliance a hard constraint. |
| 2 | Did not write any code | Brief §3 stipulates code only after decision phase ratified. Decision phase concludes "no code". |
| 3 | Did not edit `apps/mata-garuda/CLAUDE.md` §1.4 | §2 "Chiedi SOLO per modifiche GENOME.md senza review". §1 OSINT blindato is "ENFORCE STRICTLY". |
| 4 | Did not draft a §1.4-bis template inline | A non-binding template is offered in §7.1 for the next agent's reference, clearly marked illustrative only. Zero authors the binding text. |
| 5 | Did not update W2 design `§14 Open Questions item 5` | Cross-app doctrine reference; best done bundled with the actual doctrine PR. Out of scope for "Defer" decision. |
| 6 | Confirmed brief reality-check entity counts were wrong | Brief said 6/4/6; live KG is 409/1549/622. W2 design figures hold. Surfacing the discrepancy because it would have skewed Option C's snapshot-size estimate. |
| 7 | Did not contact Zero mid-wave | Per §0b "sub-session does NOT ask Zero anything". Zero reviews this spec post-merge. |

---

## 9. Cross-review notes for FASE 4 + FASE 5 (per brief §0b)

Brief asks FASE 6 to cross-review FASE 4 (HGT) and FASE 5 (Supervisor). Sub-session reviewed both briefs as supplied.

- **FASE 4 — HGT activation:** if HGT skill data ever surfaces in the KG (entities like `skill:foo`), the §1.4 "name + type + neighbor_names" payload could leak skill identifiers. **Action item for FASE 4:** verify that HGT writes to `apps/mata-garuda/data/knowledge.db` (the catalog DB at 304 entries per `test_migrate_skills_to_qdrant_local.py` source comment) **NOT** to `~/.agent/mata-garuda/kg.db` (the OSINT KG that Bridge A serves). If they share the DB, the §1.4 deroga as written may already over-share skill data — needs Zero review separately. *Out of scope for FASE 6 to fix; flagging only.*

- **FASE 5 — Supervisor auto-recovery:** Bridge B publisher does not exist (Defer), so there's nothing for Supervisor to auto-recover. If a future Bridge B (Option C) ships, the LaunchAgent `com.matagaruda.kg-snapshot-publisher.30min` should be enrolled in `apps/organism/organism/organs_registry.yaml` (renamed 2026-05-08 IG-3 from `genome.yaml`) with a circuit-breaker policy: 3 publish failures within 1h → STOP auto-recovery, alert Zero, do not restart. Otherwise Supervisor risks wedging publisher in a loop while Tigris is rate-limiting. *Action item documented for the future Bridge B PR; not actionable today.*

---

## 10. References

- `docs/superpowers/specs/2026-05-07-symbiosis-w2-kg-mcp-bridge-design.md` (W2, Bridge A) — especially §2 Non-Goals item 2, §3 Doctrine, §14 Open Questions item 5
- `apps/mata-garuda/CLAUDE.md` — §1 OSINT blindato, §1.4 Eccezione Pillar 3, §2 Comportamento Claude Code
- `SYMBIOSIS.md` — Pilastro 3 Condivisione (allows operative knowledge sharing between organs; OSINT body excluded)
- `AUTONOMOUS_OPS.md` — L2 contract; "new external provider" + "guardrail changes" require confirmation
- `apps/nuzantara-mcp/nuzantara_mcp/tools/kg_intel.py` — Bridge A implementation, the canonical pattern for any future Bridge B client code
- `apps/mata-garuda/mata_garuda/api/kg_query.py` — Bridge A server, pattern for forbidden-key enforcement
- PR #489 (`62c7d634a feat(symbiosis): KG → Pro MCP tool (Bridge A, Pillar 3 doctrine)`) — merged 2026-05-06, established §1.4

---

## 11. Closing

Bridge B as scoped in the brief is currently doctrine-non-compliant for all three implementation options. Defer is the only path that respects `apps/mata-garuda/CLAUDE.md` §1 + §1.4 as Zero wrote them 2 days ago. A future Bridge B requires a Zero-authored doctrine extension to §1.4, after which Option C (Tigris snapshot) is the recommended technical path.

This spec is the docs-only first commit on `feat/symbiosis-fase6-bridge-b-2026-05-08`. No further commits will follow on this branch.
