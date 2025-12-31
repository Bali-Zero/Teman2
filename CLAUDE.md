# CLAUDE.md - Istruzioni Persistenti per AI

## LEGGE ZERO - REGOLA FONDAMENTALE

**Se non sai o non capisci qualcosa del sistema — come è stata fatta, come si usa, dove si trova — NON PRESUMERE.**

1. **STOP** — Non inventare. Non assumere. Non "intuire".
2. **SEARCH** — Usa `Grep`, `Glob`, `Read` per trovare il codice esistente.
3. **STUDY** — Leggi la documentazione obbligatoria.
4. **ASK** — Se dopo lo studio rimane ambiguità, chiedi all'utente.

---

## DOCUMENTAZIONE OBBLIGATORIA

Prima di qualsiasi operazione significativa, leggi:

| Doc | Path | Quando |
|-----|------|--------|
| AI Onboarding | `docs/AI_ONBOARDING.md` | Sempre all'inizio |
| System Map | `docs/SYSTEM_MAP_4D.md` | Per capire architettura |
| Living Architecture | `docs/LIVING_ARCHITECTURE.md` | Prima di modificare codice |
| **Agentic RAG Fixes** | `docs/operations/AGENTIC_RAG_FIXES.md` | **Prima di toccare reasoning.py** |
| AI Handover | `docs/ai/AI_HANDOVER_PROTOCOL.md` | Per context su fix recenti |
| Deployment | `docs/DEPLOYMENT.md` | Prima di deployare |

---

## CRITICAL KNOWLEDGE (Dec 2025)

### Evidence Score System
Il file `reasoning.py` contiene logica critica per decidere quando rispondere:
- **evidence_score < 0.3** → ABSTAIN (rifiuta)
- **trusted_tools_used = True** → Bypass ABSTAIN per calculator/pricing/team

### NON TOCCARE senza leggere `docs/operations/AGENTIC_RAG_FIXES.md`:
- `calculate_evidence_score()`
- `trusted_tools_used` check
- Policy enforcement blocks
