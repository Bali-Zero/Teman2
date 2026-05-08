# Phase 2 — Setup Team Extend (Property + Labor)

> **Prerequisiti**: Phase 1 mergiata (PR #534 + #536 + #540). Cron `com.balizero.setup-team.daily` attivo.
>
> **Stima**: 5-7 giorni solo-dev.

---

## PROMPT (drop-in)

Continuiamo il Domain Mesh. Phase 2: estendi il dominio Setup Team aggiungendo i 2 sub-stream INTEL mancanti (Property + Labor) che erano stati deferred in Phase 1.

Prima di tutto, leggi:

1. `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` §2 B1 (genesi Setup Team con tutti 4 NB-INTEL)
2. `docs/superpowers/plans/2026-05-08-domain-mesh-phase1-setup-team.md` (pattern Phase 1)
3. `apps/mata-garuda/mata_garuda/domains/setup_team/feeders/` (3 feeder esistenti come reference)

Poi invoca `superpowers:brainstorming` per confermare l'approccio (sub-domains Property/Labor sono identici come pattern a Regulation/Immigration?), poi `superpowers:writing-plans` per il plan.

### Scope

**In**:

- `feeders/nb_intel_property.py` con sources:
  - atrbpn.go.id (BPN nazionale)
  - Pemkab Badung DPMPTSP, PUPR
  - Bali property tier-1 (Bali Realty, Exotiq, Property Bali Indo)
- `feeders/nb_intel_labor.py` con sources:
  - kemnaker.go.id/berita
  - bpjsketenagakerjaan.go.id
  - BNP2TKI / BP2MI
  - Hukumonline labor tag
  - Twitter @KemnakerRI (RSS via nitter mirror, fallback)
- Scorer fast-path:
  - Property: `PBG|HGB|HGU|hak ?pakai|hak ?milik|sertifikat|ATR|BPN|land ?cert|tanah ?cert|villa|properti`
  - Labor: `RPTKA|IMTA|BPJS ?(TK|Kesehatan)|UU ?13|UU ?6\/2023|cipta ?kerja|kemnaker|tenaga ?kerja|TKA`
- Estendere il cron `setup-team-cron.sh` per chiamare anche Property + Labor feeders
- Aggiornare obligation_engine + client_match per supportare i nuovi domain types
- Test: stesso pattern di Phase 1 (mock httpx, mock subprocess, verify regex)

**Out**:

- Skill graduation pipeline (Phase 8)
- Cross-domain alert dispatcher (Phase 8)

### Pattern da seguire

I 3 feeder Phase 1 sono il template. Ogni feeder:

1. Definisce `*_BERITA_URL` constants
2. `TRUSTED_TIER1_HOSTS` set (gov direct hosts)
3. `*_REGEX` con scorer fast-path
4. `_LIFESTYLE_BLOCKLIST` per skip rumore
5. `async def fetch_recent_*(days=30, http_client=None) -> list[Regulation]`
6. Try/except per layer in modo che 1 fonte morta non kill gli altri
7. Dedup by `(domain, source_id)`

Test pattern in `tests/domains/setup_team/test_feeders.py` — copia struttura.

### Regole forti

- Niente Anthropic SDK. `claude --print` subprocess.
- Lazy imports.
- Cron LaunchAgent PATH include `/Users/nuzantara/.local/bin`.
- Atomic mv snapshot.
- TDD per ogni nuovo file: scrivi test prima.
- Branch hijack: `git push` dopo ogni commit.
- mata-garuda CLAUDE.md: deps minimal (no nuovi pesanti).

### Output finale

PR auto-merge ON con:

- 2 nuovi feeder
- ~20 nuovi test (feeder pattern di Phase 1)
- Cron wrapper aggiornato
- Plist invariato (stessa LaunchAgent — solo lo script Python aggiunge i 2 layer)

Quando finito, una verifica live:

```bash
launchctl kickstart gui/$(id -u)/com.balizero.setup-team.daily
sleep 10
tail -50 ~/logs/setup-team/setup-team-daily-$(date +%Y%m%d).log
```

Atteso: nuovo summary con `feeders=` aumentato (era 1 in Phase 1, ora dovrebbe essere fino a 5 con i 2 nuovi se i portali rispondono).

Procedi.
