# Team Photos — SSOT + refactor (2026-06-15)

## Problema

Le foto del team non hanno una single source of truth: sono hardcoded in 4 liste
frontend + 1 colonna DB, che divergono (membri diversi, ruoli diversi, foto Heru/Zainal
invertite in 2 file, 11 membri su placeholder batik).

## Sorgenti attuali (5)

1. `apps/mouth/src/components/book/book-data.ts` (TEAM_MEMBERS, 18) — team grid /book
2. `apps/mouth/src/app/(blog)/team/page.tsx` — pagina pubblica /team (BUG Heru↔Zainal)
3. `apps/mouth/src/app/v2/company/about/page.tsx` — about (5 membri)
4. `apps/mouth/src/app/v2/_components/SocialProof.tsx` — homepage v2 (BUG Heru↔Zainal)
5. Postgres `team_members.avatar` — servita da routers/team.py, auth.py, portal.py
   - `team-management/page.tsx` TEAM_PHOTOS map (6)

## File fisici

- `apps/mouth/public/static/team/` (principale) — reali + ~13 batik placeholder + 2 file 20MB
- `public/images/team/`, `public/avatars/team/` — legacy

## Design SSOT scelto

**Una sola fonte frontend** = nuovo file `apps/mouth/src/data/team-roster.ts` con
`TEAM_ROSTER: TeamMemberPhoto[]` (key = email-prefix slug, name, role, department, photo).
Le 4 liste frontend importano/derivano da qui invece di hardcodare i path.
Il backend resta autorevole per il CRM/portal via `team_members.avatar`; allineiamo i
valori avatar DB agli stessi path `/static/team/*` (sito e portal coerenti).

## Step

### Fase 0 — grounding residuo (PRIMA di toccare il DB)

- [ ] Leggere `SELECT email,name,role,department,avatar FROM team_members` (MCP postgres
      era giù all'audit — NON modificare la colonna finché non letto il contenuto attuale).

### Fase 1 — asset fisici

- [ ] Inventario foto reali mancanti: Surya, Vino, Damar, Veronika, Angel, Kadek,
      Dewa Ayu, Faisha, Rina, Nina (+ Zainal in book-data). → Antonello fornisce i file.
- [ ] Ricomprimere `adit.png` e `dea.png` (20MB → <500KB) con sharp/squoosh.
- [ ] Depositare le nuove foto in `public/static/team/<slug>.jpg|png`.

### Fase 2 — SSOT frontend

- [ ] Creare `src/data/team-roster.ts` (lista unica, allineata a team_members.json).
- [ ] Refactor book-data.ts / (blog)/team / about / SocialProof per derivare da TEAM_ROSTER.
- [ ] Fixare bug Heru↔Zainal nei 2 file.
- [ ] Test: build mouth (`npm run build`) + render check.

### Fase 3 — CRM/Portal (DB)

- [ ] UPDATE `team_members.avatar` per ogni membro → path `/static/team/<slug>`.
      (backend code-only, NO MCP per la mutation — via migration o script su DB).

### Fase 4 — pulizia legacy

- [ ] Rimuovere `public/images/team/` e `public/avatars/team/` se confermati non usati
      (grep finale prima del rm).

### Fase 5 — chiusura

- [ ] PR su branch worktree, NO auto-merge, screenshot QA /team + /book.

## Note disciplina

- Lavoro nel worktree `.worktrees/mouth-team-photos-ssot`.
- Off-limits non toccati. Email rule N/A. Nessun PII.
- Le foto reali dei membri mancanti le deve fornire Antonello (non le posso generare —
  sono persone reali).
