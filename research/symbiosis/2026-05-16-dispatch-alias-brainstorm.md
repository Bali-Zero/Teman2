---
date: 2026-05-16
domain: symbiosis
client_case: 4-LLM brainstorm — fix dispatch envelope drift OSINT-Nexus → mata-garuda
sources: 7
status: COMPLETE
parent_doc: research/symbiosis/2026-05-16-reflection-regression-2026-05-08.md
panelists: Codex GPT-5.5 (xhigh) + Gemini 3.1 Pro + DeepSeek V4 Pro (high) + NB-1 SKIPPED
verdict: OPTION C (rafforzare gap_legacy.py esistente) — 3/3 convergente
nb1_status: SKIPPED — pattern bipolar verifier non applicabile (domanda è codice live, non ground-truth dominio); 3-panel quorum sufficiente
---

# 4-LLM brainstorm — Fix dispatch envelope drift

## Verdict

**Opzione C — Anti-Corruption Layer translator** è la scelta convergente di tutti e 3 i panelisti (Codex, Gemini, DeepSeek). NB-1 saltato come da nota frontmatter.

**Twist importante scoperto durante il brainstorm**: l'Opzione C **esiste già** parzialmente come `apps/mata-garuda/mata_garuda/workers/gap_legacy.py:_TRANSLATION` (8 entries hardcoded). Il vero fix non è "creare un nuovo translator", ma **estendere quello esistente** con i mapping mancanti + aggiungere alert su `unmapped` rate.

## Empirical breakdown of `nexus:gaps` (live 2026-05-16)

| (gap_type, attribute)                                             | count | mappato in `_TRANSLATION` esistente?                | dispatched a                              |
| ----------------------------------------------------------------- | ----: | --------------------------------------------------- | ----------------------------------------- |
| `missing_attribute / nip`                                         |  1180 | ✅                                                  | `gap.missing_nip` → lhkpn_harvester       |
| `missing_relation / officials_or_documents`                       |   886 | ❌                                                  | DRAINED                                   |
| `stale_attribute / profile`                                       |   885 | ✅ wildcard                                         | `gap.stale_official` → regulation_watcher |
| `missing_relation / procurement_link`                             |   580 | ❌                                                  | DRAINED                                   |
| `missing_relation / WORKS_AT:Kanim Kelas I Khusus TPI Ngurah Rai` |   177 | ❌                                                  | DRAINED                                   |
| `missing_attribute / lhkpn`                                       |   177 | ✅                                                  | `gap.missing_lhkpn` → lhkpn_harvester     |
| `missing_relation / officials_struktur`                           |   116 | ❌ (key in TRANSLATION ma per `missing_attribute`!) | DRAINED                                   |
| `missing_attribute / angkatan`                                    |    58 | ✅                                                  | `gap.missing_angkatan` → lhkpn_harvester  |

**Mappati**: 2300 (56.7%) — 1180 + 885 + 177 + 58
**Drained "unmapped"**: 1759 (43.3%) — 886 + 580 + 177 + 116

→ Quasi metà dello stream finisce in "no canonical mapping" log warning, no agent dispatched.

## Convergent reasoning across 3 panelists

| Criterio                           | DeepSeek                                    | Gemini                                                    | Codex                                                                           |
| ---------------------------------- | ------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Verdict                            | **C**                                       | **C**                                                     | **C, rafforzando gap_legacy.py esistente**                                      |
| Law 4 graceful degradation         | ✅ ACL isola, dead-letter su unknown        | ✅ Schema firewall, dead-letter                           | ✅ Mappings noti continuano, valori nuovi → unmapped/DLQ                        |
| Law 7 numeri prima                 | ✅ `translator.mappings.{found,unknown}`    | ✅ `gaps.translated_successfully` + `gaps.unmapped_tuple` | ✅ `mapped_total{type,attr,to}` + `unmapped_total{type,attr}` + `drained_total` |
| Future "stale_relation" / new attr | ✅ Single line addition                     | ✅ ACL catches at boundary                                | ✅ Aggiunge mapping o fallisce forte                                            |
| Loud failure 6mo                   | ✅ Translator alerts on unmapped            | ✅ `UnmappedGapTranslationError` Sentry                   | ✅ Se unknown non ACK-drained in silenzio                                       |
| LHKPN feasibility                  | ✅ Translator emits exact `gap.missing_nip` | ✅ Agent contract preserved (zero internal change)        | ✅ Ma A non basta — agent non sa demux phone/procurement                        |

**Twist Codex**: ha verificato direttamente il codice e ha visto che `gap_legacy.py:_TRANSLATION` esiste. La sua frase chiave: _"Raccomando C, ma usando/rafforzando l'adapter già esistente, non alias piatti in GAP_DISPATCH"_.

**Punti minori divergenti**:

- DeepSeek + Gemini hanno suggerito un nuovo file `gap_envelope_translator.py`
- Codex ha visto che esiste già e propone di estenderlo
- Codex ha distinto `procurement` vs `procurement_link` (attribute name drift OSINT→mata-garuda) e `phone`/`officials_or_documents` come gap senza agent target → DLQ esplicita

## Risk-adjusted spec di fix

### Fix C.1 — Estendere `_TRANSLATION` (~1h)

File: `apps/mata-garuda/mata_garuda/workers/gap_legacy.py:54`

Add 4 new mappings:

```python
_TRANSLATION: dict[tuple[str, Optional[str]], str] = {
    # Existing (live)
    ("missing_attribute", "nip"):                "gap.missing_nip",
    ("missing_attribute", "lhkpn"):              "gap.missing_lhkpn",
    ("missing_attribute", "angkatan"):           "gap.missing_angkatan",
    ("missing_attribute", "officials_struktur"): "gap.kanim_struktur",
    ("missing_attribute", "procurement_link"):   "gap.missing_procurement",
    ("stale_attribute",   None):                 "gap.stale_official",
    # NEW — covers 1759 currently-drained entries
    ("missing_relation",  "officials_struktur"): "gap.kanim_struktur",
    ("missing_relation",  "officials_or_documents"): "gap.orphan_org",
    ("missing_relation",  "procurement_link"):   "gap.missing_procurement",
    # WORKS_AT:* uses prefix match, not exact tuple — needs slight refactor:
    # if legacy_attr.startswith("WORKS_AT:"):
    #     canonical = "gap.kanim_struktur"
}
```

**Decisione bocciata da Codex**: NON aggiungere alias piatti `"missing_attribute": "lhkpn_harvester"` direttamente in `GAP_DISPATCH`. Manterrebbe semantica ambigua (`missing_attribute` con `attribute=phone` finirebbe a `lhkpn_harvester` → spam errati al KPK).

### Fix C.2 — Loud unmapped alert (~30min)

`gap_legacy.py:coerce_to_canonical` già logga `WARNING Legacy gap drained ...`. Aggiungere counter persistente in `~/.cell-observatory/observatory.db` o tabella `unmapped_gaps_audit`:

```python
def _record_unmapped(legacy_type: str, legacy_attr: Optional[str]):
    """Persist for daily audit; trigger Telegram if rate >100/h."""
    # Insert into mata_garuda/data/knowledge.db or new table
    # Daily cron checks total > threshold → hotfix-notify.sh
```

E un cron daily `~/scripts/matagaruda-unmapped-gap-audit.sh` 09:00 WITA che alza alert se "Legacy drained" ultimi 24h > 50% del totale processato.

### Fix C.3 — `WORKS_AT:*` prefix routing (deferred)

177 entries con attribute `WORKS_AT:Kanim Kelas I Khusus TPI Ngurah Rai` (e simili future). Sono `missing_relation` di tipo "questo Official lavora a quel Kanim?". Routing a `regulation_watcher` per arricchimento Neo4j. Richiede modifica `coerce_to_canonical` per supportare prefix match, non più solo tuple exact match. Effort separato (~2h spec + impl + test).

### Fix C.4 — DLQ esplicita per gap senza agent target

Tipi come `missing_attribute / phone` non hanno agent designato (nessun `phone_harvester` esiste). Drain corrente è silenzioso. Spec: aggiungere terzo valore canonical `"gap.dlq:phone"` con `GAP_DISPATCH["gap.dlq:phone"] = None` MA con metric counter dedicato. Antonello decide se merita un `phone_harvester` futuro.

## Effort + risk profile (totale)

| Fix                                     | Effort | Risk                                    | Reversibilità          | Autonomous?                                                             |
| --------------------------------------- | ------ | --------------------------------------- | ---------------------- | ----------------------------------------------------------------------- |
| C.1 estendere \_TRANSLATION (4 entries) | 1h     | LOW (additivo, no break)                | Alta (revert 1 commit) | NO (tocca codice live mata-garuda — needs PR + 4-LLM spec already done) |
| C.2 loud unmapped alert                 | 30min  | LOW                                     | Alta                   | NO (operator script + cron install)                                     |
| C.3 WORKS_AT prefix routing             | 2-3h   | MEDIUM (refactor `coerce_to_canonical`) | Media                  | NO (separate PR)                                                        |
| C.4 DLQ esplicita                       | 1h     | LOW                                     | Alta                   | NO (separate PR)                                                        |

**Sequenza raccomandata**: C.1 (sblocca 1759 entries immediatamente) → C.2 (previene future regression silente) → C.3+C.4 (consolidamento, non urgente).

## Refusals enforced by Autonomous Ops L2

- **NO autonomous edit `gap_legacy.py`** — code live mata-garuda, modifica `_TRANSLATION` cambia routing in produzione → PR formale necessaria.
- **NO autonomous install nuovo cron `matagaruda-unmapped-gap-audit.sh`** — operator-side script outside repo, install plist hardened 0444 (cf. cicatrix-scars.md 2026-04-29 plist corruption).
- **NO autonomous fix Docker Desktop / Neo4j restart** — separate decisione (Layer 2 del root cause doc).

## NB-1 verifier — SKIPPED rationale

Pattern bipolar verifier (CLAUDE.md): "1 LLM main + 1 NB ground truth specialistico". NB-1 è "Nuzantara architecture knowledge base" — utile per domande tipo "qual è il design canonico del Pilastro X?", non per "come fixo questo bug di routing". Il bug è puramente codice live (gap_legacy.py + GAP_DISPATCH + nexus:gaps stream content). 3-panel convergence (Codex+Gemini+DeepSeek) + lettura diretta del codice da parte di Codex coprono già il gap epistemico.

Se in futuro serve verificare che il design Pilastro 1 Riflessione preveda un translator a `_TRANSLATION` (vs uno standalone middleware), allora NB-1 query mirata: "qual è il design canonico del consumer pattern in Symbiosis Pilastro 1?". Per ora non blocca.

## Sources

1. Codex GPT-5.5 brainstorm output `/tmp/brainstorm-codex.out` (52240 tokens, ~3min runtime)
2. Gemini 3.1 Pro brainstorm output `/tmp/brainstorm-gemini.out`
3. DeepSeek V4 Pro brainstorm output `/tmp/brainstorm-deepseek.out` (~10KB JSON)
4. `apps/mata-garuda/mata_garuda/workers/gap_legacy.py:54` `_TRANSLATION` table (existing partial Opt C)
5. `apps/mata-garuda/mata_garuda/workers/gap_consumer.py:51-60` `GAP_DISPATCH` table
6. `apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py:116-150` agent instructions
7. `redis-cli XRANGE nexus:gaps - + COUNT 10000` empirical (gap_type, attribute) breakdown
