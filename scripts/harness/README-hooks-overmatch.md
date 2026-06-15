# fix_hooks_overmatch.py — cura 3 bug famiglia "Guard-over-match" (superscar #3)

> Genesi: opus-mythos TAC organo-immunità (2026-06-16). Mandato: "ripercorri tutta la pipeline hook
> in cerca di bug". Fan-out subagent + gate Opus su disco → 3 bug CONFERMATI (riprodotti), tutti
> della stessa malattia di 2° ordine: **match per substring senza confine semantico** = cicatrix #3.

## I 3 bug (tutti riprodotti su disco, poi fixati con test guiltiness+innocence)

| # | hook | bug | tipo | prova |
|---|---|---|---|---|
| 1 | `worktree_isolation.py` CPMV | `install` matcha dentro `npm/pip/brew install` → estrae il pkg-name come write-target; e il redirect `2>/tmp/x` preso come path | **falso POSITIVO** (blocca `npm install` + ogni cmd con `2>redirect`) | `npm install axios` → estraeva `['axios']` |
| 2 | `worktree_isolation.py` REDIR | lookbehind `(?<![0-9>&])` troppo largo → `2>file` e `&>file` NON rilevati come write | **falso NEGATIVO** (un write via stderr-redirect nel main sfuggiva) | `foo 2>/tmp/err` → `[]` |
| 3 | `guardrails-static.py` python-c | `os.system|subprocess|exec|eval` matchano dentro STRINGHE/commenti, non solo chiamate | **falso POSITIVO** (blocca `python -c "print('eval')"` + ogni script che NOMINA quelle funzioni — ha bloccato il subagent stesso durante l'audit) | `python3 -c "print('eval')"` → BLOCK |

## I fix (minimi, ~3 righe ciascuno)
- **#1**: scarta `install` se preceduto da package-manager (`npm/pip/brew/...`) + scarta token con `>`/`<` (redirect).
- **#2**: `REDIR_RE` cattura `[0-9]?>` e `&>` (stdout/stderr/combined); `&1`/`&2` filtrati dopo.
- **#3**: il pattern python-c richiede la **chiamata** (`exec(` con parentesi) o `subprocess...shell=True`, non la sola parola.

## Test (cicatrix #3 impone ENTRAMBI)
`test_hooks_overmatch.py` — guiltiness (blocca il vero cattivo) + **innocence** (NON scatta sul caso legittimo limitrofo). 6/6 end-to-end + 6/6 python-c verificati prima del commit.

## NOTA: un 4° falso positivo osservato (non ancora fixato)
Durante questo stesso lavoro, `worktree_isolation.py` ha bloccato un `cd <worktree>\ncat > file` (cd e write su righe separate) calcolando il target nel MAIN invece del worktree — il parser non collega il `cd` multi-riga al comando seguente. Stessa famiglia. Workaround: usare il Write tool (non `cat >` shell). Fix futuro: collegare cd→comando attraverso i newline in `_derive_cwd`.

## Installazione (OPERATOR-RUN — hooks/ blindato dal carve-out by-design)
`bash scripts/harness/install_hooks_overmatch.sh` — copia patcher → applica → ri-testa. Idempotente, backup `.bak-overmatch`.
