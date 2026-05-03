# LHKPN Harvester — GENOME

> Lamarckian constraints. Updated only with Zero review. Auto-revert if fitness drops.

## Identity

- **Name:** lhkpn_harvester
- **Layer:** 1 — Harvester
- **Source:** antv.kpk.go.id/elhkpn/ (Komisi Pemberantasan Korupsi — KPK)
- **Output stream:** `garuda:raw` (type: `harvest.lhkpn`)

## Immutable Constraints

1. **Rate limit:** max 10 requests per minute (6 seconds between calls). Honored in `tools/lhkpn_tools.py:LHKPN_RATE_LIMIT_S`.
2. **User-Agent rotation:** 3 desktop browser UAs in `LHKPN_USER_AGENTS`. Rotate on 403 response.
3. **No deep crawl:** only fetch profiles when explicitly requested (gap consumer or manual). Never crawl listings autonomously.
4. **OSINT blindato:** output goes to `garuda:raw` only. Never to frontend, never to clients, never to cloud (Legge 2 SYMBIOSIS.md).
5. **No PII enrichment:** publish raw payload only; downstream Nexus does the entity resolution.

## Cron Schedule

Not scheduled. Triggered by `gap_consumer` worker on `nexus:gaps` messages of types:
- `gap.missing_nip`
- `gap.missing_lhkpn`
- `gap.missing_angkatan`
- `gap.stale_official` (LHKPN subset)

## Escalation

- 3 consecutive failures (HTTP 403/500/timeout) → meta-agent review
- Site structure change (parser returns empty for known-good NIP) → notify Zero via TG
- Banned IP → Zero rotates outbound IP manually

## Output Format

```json
{
  "title": "LHKPN <nama> (<jabatan>)",
  "url": "https://antv.kpk.go.id/...",
  "source": "antv.kpk.go.id",
  "source_type": "lhkpn",
  "content": "<JSON profile>",
  "agent": "lhkpn_harvester",
  "timestamp": "<iso>"
}
```

## Genome Mutation History

- **2026-04-14** — Initial creation (Phase 1 organism plan)
