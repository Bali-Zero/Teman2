---
name: wr3-brief-interpreter-nb-routing-domain-map
description: WR3 brief-interpreter domain → NotebookLM routing map (authoritative). Domain NBs only (NB-2..NB-7). NB-1 codebase and NB-INTEL OSINT family are OUT OF SCOPE for ground-truth regulatory grounding.
---

# NB Routing Domain Map (WR3 brief-interpreter)

Authoritative routing table. Sourced from `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/reference_notebooklm_arsenal_full.md`.

## Domain → NB mapping

| Domain keywords                                            | NB     | Notebook name                              | Sources |
| ---------------------------------------------------------- | ------ | ------------------------------------------ | ------- |
| visa, immigration, kitas, kitap, voa                       | NB-2   | Immigration & Visa Indonesia 2025          | 97      |
| company, pma, pt-pma, kbli, oss, nib, bkpm                 | NB-3   | Company Setup Indonesia 2025               | 183     |
| tax, spt, pph, ppn, kep71, kep-71, pmk, fiscal             | NB-4   | Tax & Fiscal Indonesia                     | 118     |
| property, real-estate, pbg, hak-pakai, hgb, sertifikat     | NB-5   | Property & Real Estate Indonesia 2025      | 117     |
| compliance, lkpm, operations, izin, reporting              | NB-6   | Operations & Compliance Indonesia          | 188     |
| editorial, brand-voice, ig-carousel, content-strategy      | NB-7   | Editorial & Content Strategy Bali Zero     | 89      |
| brand-identity, manifesto, mission                         | (none) | NO NB query → brand cortex (constitution)  | n/a     |

## Out of scope (DO NOT query for regulatory grounding)

- **NB-1** Nuzantara Codebase & Architecture — codebase only, not regulatory authority.
- **NB-INTEL family** (Immigration / Tax / Regulation / Property / Editorial) — daily OSINT cron feed. OSINT-only per Law 2. NEVER consumed by brief-interpreter for ground-truth regulatory grounding. brief.json must NOT cite NB-INTEL source_ids or synthesis.

## Cross-domain dossier

If a topic spans multiple domains (e.g. "tax implications of new KITAS rule for PT PMA"), query each relevant domain NB separately and combine claim_ids in brief.json. Do NOT fall back to NB-1.

## Brand-identity exception

For pure brand-identity / manifesto episodes (no regulatory claim): bypass NB entirely. Use `~/.claude/skills/bali-zero-brand/constitution.md` + `voice/on-tone-examples.md` only. brief.json regulatory_citations array remains empty `[]`.

Referenced by `~/.claude/skills/bali-zero-brand/wr3/brief-interpreter/SKILL.md`.
