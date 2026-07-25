---
date: 2026-07-24
domain: visa
client_case: none
adversarial_review: kimi
---

Ignoring 51 permissions.allow entries from .claude/settings.json: this workspace has not been trusted. Run Claude Code interactively here once and accept the trust dialog, or set projects["/Users/nuzantara"].hasTrustDialogAccepted: true in /Users/nuzantara/.claude-zero-team/.claude.json.
Fatto. Ecco il verdetto finale.

---

# Verifier — Visa Oracle v2, merge round 4

Repo corretta: `Balizero1987/Teman2`. `git fetch origin` eseguito. Cure note (`5065322278`) letta per prima.

## PR #3060 — visa-category-257 — ✅ GIÀ MERGIATA (nessuna azione da parte mia)

**Stato:** `MERGED` — l'owner `Balizero1987` l'ha squash-mergiata alle 2026-07-24T02:37:34Z. Merge commit **`35da9284091959111ae987befc518be6e000dcbf`**. Head SHA della PR = `4142cc6da77b`, coincide con quanto delegato. CI verde al merge (0 fail, 0 pending). `35da928` è ancestor di `origin/main` — confermato in main.

**Gate cure-1 (migration 257 rollback, HIGH) — SOLIDA** (verificata nel tree di `main`):
- Sequenza `DISABLE TRIGGER visa_decisions_immutable` → `DROP CONSTRAINT IF EXISTS` → `DO $$` guarded (relabel `business`/`diaspora`→`other` solo se la colonna esiste via `information_schema`) → `ADD CONSTRAINT` con CHECK a **8 valori** (`business`/`diaspora` rimossi, verificato) → `ENABLE TRIGGER`.
- Trigger handling corretto: DISABLE ed ENABLE nello stesso script; in Postgres il DDL è transazionale, quindi la transazione per-migration re-arma il trigger su successo e fa rollback della DISABLE su qualsiasi failure → il guard non può mai restare disarmato. Deviazione documentata giustificata e sound.
- Test `test_shadow_evidence.py:1092` presente nel merge commit.

**Summary:** #3060 già mergiata dall'owner con CI verde; la cura del rollback (trigger disarm transazionale + relabel guarded + CHECK a 8 valori) è corretta — nessuna azione richiesta.

## PR #3061 — visa-evaluate-endpoint — 🚫 LASCIATA APERTA (non mergiata)

**Merge SHA: nessuno.** Due blocker indipendenti, entrambi ostativi al merge:

1. **Conflitto con main** (`mergeable: CONFLICTING`, `mergeStateStatus: DIRTY`). Lo squash-merge di #3060 ha portato in main gli stessi 3 file (`257_...sql`, `shadow_evidence.py`, `test_shadow_evidence.py`) che questo branch include via il commit cure-1 `26933e1a5b`; uno squash non è ancestor del branch → conflitto. Serve rebase su main.
2. **`inventory-check` ROSSO** — `docs/DOCS_INVENTORY.md` out of date (date-drift su `AI_ONBOARDING.md`/`bali-zero-magazine.md` dopo che il branch ha toccato `AI_ONBOARDING.md`). Non è un difetto di codice ma è un check rosso → fix `bash scripts/docs_inventory_regen.sh` + commit.

**Gate delle 4 cure contro il codice del branch (`0cc06f5940`) — tutte 4 SOLIDE:**
- **Cure 2 (OOM, HIGH):** `_read_capped_body` streamma con `request.stream()` e aborta 413 appena `received > 32KB`; Content-Length solo pre-check; nessun `request.body()` altrove. ✅
- **Cure 3 (allowlist armata, HIGH):** gate richiede allowlist AND `verify_driver_token`; token fail-closed su env unset/header assente, `secrets.compare_digest`, `TypeError` catchato; 400 generico unico. ✅
- **Cure 4 (echo enum, MEDIUM):** param `str` grezzi validati in-route con messaggi statici, nessun echo; gli `Enum` costruiscono solo il vocabolario. ✅
- **Cure 5 (hint cieco, MEDIUM):** `derive_request_category` onora l'hint solo quando i fatti derivano `other`; purpose singolo mappabile vince. ✅

Findings postati come commento: https://github.com/Balizero1987/Teman2/pull/3061#issuecomment-5066223719

**Summary:** #3061 lasciata OPEN — codice read-path e tutte e 4 le cure verificate corrette, ma bloccata da conflitto post-merge di #3060 e da `inventory-check` rosso; sbloccabile con rebase su main + rigenerazione del DOCS_INVENTORY, poi è mergiabile.
opus exit=0

## Adversarial review

Orchestrator verified: (#round3) #3028 merge SHA on main; #3034 CONFLICTING was cured and re-pushed; (#round4) #3060 owner-merge SHA on main, the 4 cure verifications match the code. None survived, 0 raised.
