# SOTA Research — Open Questions Log

Resolutions for the 5 open questions in the research design spec
`docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md`
(§Open questions, lines 308-323).

Resolved 2026-04-22 at Task 0 start.

---

## Q1 — Team member for manual competitor scraping

**Assigned:** Vino (Bali Zero team)
**Availability window:** 25h total across 5 working days = Fase 0 Days 2-6,
5h/day.
**Runbook:** `docs/runbooks/competitor-scrape-manual.md` (produced in Task 11).
**Daily check-in:** Telegram to Zero at 18:00 WITA with row count + blockers.
**Deadline:** EOD Fase 0 Day 6 (Gate 3 blocking).

If Vino falls behind: fallback to Playwright MCP automation for missing
accounts (Risk #1 in spec).

---

## Q2 — Grafana instance

**Decision:** Use existing Grafana Cloud account (no new signup needed).
**Tenant endpoint:** `prometheus-prod-01-eu-west-0.grafana.net`
**OTEL exporter:** `https://otel-collector.grafana.net/v1/traces` (already wired)
**Secrets location:** Fly.io on `nuzantara-rag` app:
- `GRAFANA_REMOTE_WRITE_URL`
- `GRAFANA_REMOTE_WRITE_USER`
- `GRAFANA_REMOTE_WRITE_TOKEN`
- `GRAFANA_ZAN_TOKEN`
- `OTEL_EXPORTER_ENDPOINT`, `OTEL_EXPORTER_HEADERS`, `OTEL_SERVICE_NAME`, `OTEL_ENABLED`

**For Task 31 (dashboard JSON):** the Grafana instance data source will
be PostgreSQL (Fly `nuzantara-postgres`), not Prometheus — the SOTA
dashboard queries `post_metrics_history` + `clients` + `war_room_posts`
directly. A new read-only user needs to be created on the Fly Postgres
(documented in `docs/runbooks/grafana-sota-setup.md` at Task 31 time).

**Subdomain:** `grafana.balizero.com` CNAME to be added to the Cloud tenant.

---

## Q3 — Instagram Graph API token

**Status:** RESOLVED — live smoke test passed 2026-04-22.

**Path that worked:** Meta User Access Token (previously known as
`WHATSAPP_TOKEN` in our secrets file) is a full user token with these
scopes: whatsapp_business_management, pages_read_engagement, pages_show_list,
instagram_basic, instagram_manage_insights, plus task `ANALYZE` on the
Bali Zero Page.

**Facebook identity:** user `Zero` (id `122148657428965177`).
**Bali Zero Page id:** `105001911737692`.
**Instagram Business Account id:** `17841403587118874`.
**Handle:** `balizero0`.

**Live baseline (captured now):**
- followers_count: 10,346
- media_count: 245
- biography: "Est. 2003 — Visas & Immigration / Company setup / Tax / Real estate. Top rated on Google ★"
- most recent post (2026-04-21): CAROUSEL_ALBUM, 108 likes, **146 saves**,
  9,836 reach. Engagement rate ~2.6% on reach basis.

**Secrets written to `~/.nuzantara-secrets.env`:**
```bash
export IG_GRAPH_API_TOKEN="EAAPQ8uMcmEMBRfx...8oz0jMIcZD"  # Page Access Token, long-lived
export IG_BUSINESS_ACCOUNT_ID="17841403587118874"
export IG_BUSINESS_HANDLE="balizero0"
```

**Deprecated:** The old `INSTAGRAM_LONG_TOKEN` (`IGAAS9eDW1oc...` format from
`graph.instagram.com`) was invalidated — likely password change or Meta
session revoke. The token still deployed on Fly is dead; production IG
bot may be silently failing on reads. Out of SOTA scope to fix, but
flagged here for Zero awareness.

**Token validity:** Page Access Token from long-lived Facebook User Token
+ `/me/accounts` never expires unless user changes password or revokes
app permission. No renewal needed unless those trigger.

**Call endpoints:** use `graph.facebook.com/v21.0/` (not
`graph.instagram.com`) with this token.

---

## Q4 — CRM UTM fix scope

**Decision:** C (expanded scope, ~6h Day 1 of Fase 0 total).

**Sub-scope:**

1. **UTM builder fix** — enforce non-null source/medium/campaign/content_id
   in `apps/mouth/src/lib/` (exact file to be identified during Task 6
   Step 2).
2. **Backfill script** — `scripts/sota_utm_backfill.py` marks `clients.
   utm_source = 'unknown-legacy'` for NULL rows in last 90d so Grafana
   can track pre-fix vs post-fix coverage.
3. **CRO cron validator** — weekly check of UTM coverage percentage;
   emits alert if coverage drops >10%.
4. **Bait-and-switch fix at `apps/mouth/src/app/v2/_components/FunnelFeature.tsx:
   382`** — the secondary CTA labeled "See transparent pricing" currently
   uses `href={FUNNEL_HREF[funnel]}` which points to the funnel landing
   page, NOT a pricing page. Fix: add `FUNNEL_PRICING_HREF` constant and
   change `href`. Verified all 4 pricing destinations exist:
   - visa.balizero.com/pricing → 302 redirect (OK)
   - tax.balizero.com/pricing → 200
   - kita.balizero.com/kbli/pricing → 200
   - balizero.com/pricing → 200

**Budget:** 6h Day 1 (was 4h, +2h for bait-and-switch).

**Reference:** `docs/cro/2026-04-19-funnel-audit.md`.

---

## Q5 — Phyllo substitute for audience demographics

**Decision:** C (deferred to Cycle 2, gg 91+).

**Rationale:**
- Budget target $0 out-of-pocket (only DeepSeek ~$1.30 tolerated).
- Combo arsenale (Playwright → Socialblade + NotJustAnalytics free tier
  + NotebookLM comment inference) covers 3/5 dimensions: engagement rate,
  growth trend, qualitative persona.
- Missing: precise age / gender / geo breakdown of Tribe 2 influencers.
- If Fase 0 playbook shows demographics-precision meaningfully changes
  tone/format recommendations, Cycle 2 (starting day 91) can re-open
  Phyllo for 1 month at $30.

**Impact on Fase 0:** persona inference for the 3 expat personas
(Days 4-5, Task 15) relies on qualitative inference from comments
rather than hard demographic data. Personas will note this as
"inferred" vs "verified" confidence where applicable.

---

## Summary

All 5 open questions resolved. Fase 0 ready to begin Day 1 (Task 1)
immediately.

**Total budget Fase 0 + Loop 90d:** ~$1.30 (DeepSeek Reasoner only).

**Human time commitment:**
- Zero: 20-30 min/day Telegram approvals (~50h over 100 days)
- Vino: 25h spread across Days 2-6 (manual scraping)
- Dev time (Claude-driven): ~8-10h Day 1 for IG sensor + Brevo client +
  UTM fix + baseline driver
