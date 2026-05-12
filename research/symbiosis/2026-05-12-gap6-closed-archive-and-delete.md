---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS Gap 6 CLOSED — Opzione B (delete + archive) executed
sources: 4
status: closed
authorization: user explicit consent 2026-05-12 14:43 WITA "attacca Gap 6 — decisione B delete"
---

# Gap 6 — MATA GARUDA Gov 313 sources: APOPTOSI EXECUTED

**Empirical closure time**: 2026-05-12 14:54 WITA
**Decision**: Opzione B per NB-1 audit ("export 313 in Drive bucket + delete da NLM. Recupera quota.")

## Target verified

- NB ID: `0fc0de09-d6f3-47d5-9ac1-75cdb66907bf`
- Title: MATA GARUDA — Indonesia Gov Data Sources
- Source count pre-delete: **313** (matching NB-1 audit verbatim)
- Last updated: 2026-04-10 (32 giorni idle)
- Type distribution: 264 web_page + 49 pdf

## Archive cold storage

- Locale: `~/Desktop/nuzantara/research/nb-archive/matagaruda-gov-archived-2026-05-12/` (rebuilt from Drive after branch-hijack)
- Drive: `gdrive:nuzantara-osint-archive/matagaruda-gov-archived-2026-05-12/` https://drive.google.com/open?id=1s10v8lYK57nsrZyTmgLhNlFhAgpLOnQV
- 3 files, 209 KB: INDEX.md + sources-manifest.json + sources.jsonl

## Delete executed

```
$ nlm delete notebook 0fc0de09-d6f3-47d5-9ac1-75cdb66907bf --confirm
✓ Notebook 0fc0de09-d6f3-47d5-9ac1-75cdb66907bf has been permanently deleted.
```

Post-delete: `nlm notebook list` returns 45 NBs (was 46), 0 gov-matching.

## Hijack-resistance lesson

Drive archive survived branch-hijack at 14:55 WITA when working-tree wiped. Local archive rebuilt from Drive at 14:58 WITA. **Pattern recommendation**: for destructive irreversible ops, push rollback artifact to Drive BEFORE executing destructive command. Local working tree is hijack-volatile, Drive is durable.

## Compliance

- OSINT Law 2 preserved (private repo + private Drive)
- Symbiosis Law 5 destructive consent recorded (frontmatter)
- VADEMECUM Sec 11 audit trail in frontmatter

## Status post Gap 6

Gap 1, 2, 4, **6** closed empirically. Gap 3, 5, 7 deferred.

## Sources

1. `nlm notebook list` 2026-05-12 14:48 WITA
2. Drive archive https://drive.google.com/open?id=1s10v8lYK57nsrZyTmgLhNlFhAgpLOnQV
3. Local archive rebuilt from Drive 14:58 WITA
4. `nlm delete notebook --confirm` execution log
