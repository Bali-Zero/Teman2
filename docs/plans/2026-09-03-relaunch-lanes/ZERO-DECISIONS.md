# Decisions only Zero can take (Legge 5 / operator) — 2026-09-03

Sessions prepare, measure and draft; none of these nine is theirs to decide. Each item names the
one question, the options with their measured cost, and who executes once ruled.

1. **GARUDA VOA step 5 — how migration 304 gets applied.** (D) a dedicated migration role that
   owns the DDL path, or (E) a fully specified superuser transaction with `SET LOCAL ROLE` and
   runner-compatible tracking. Costs and ownership measured in PR #5573. Option A (temporary
   GRANT to the runtime role) is superseded and unsafe. → Lane A executes.

2. **KBLI — the 61 non-OSS-issued codes.** Relabel now with what the statute implies, or gate on
   the F2 router increment that renders the issuer (Phase 1b)? Spec §9 of
   `docs/specs/2026-09-02-kbli-kg-licensing-class-cure-spec.md`. → Lane D executes.

3. **Bot — the citation rule in `zantara_core.py:314`.** The rule has no licit "cite nothing"
   exit, so operational questions get an invented statute (PP 36/2021 on wages for a bank-transfer
   question). Lane E drafts the replacement paragraph here; the file is off-limits to sessions —
   Zero applies or authorises. → Zero edits, Lane E proves on the real thread.

4. **WR3 — accept or reject clip M05-v11** (`OWNER_VISUAL_REVIEW_REQUIRED`; all machine gates
   pass; 80/100 credits spent; publication stays off). → Lane B lands the branch either way.

5. **E33 — flip `E33_CLAIM_GUARD_ENFORCE` in Fly secrets** once the FR/RU guilt corpus is green
   (Lane B1). It is a production-risk switch, not a code change. → Zero flips, Lane B proves.

6. **Visa Oracle — ratify the gold expectations** (4/20 divergences, ruling sheet prepared by
   Lane C4) and **sign DPIA V2 §8**. Both are enforce-gate preconditions; neither authorises ENFORCE.
   → Lane C records the ratification in the pack.

7. **Secrets (operator[secret]).** Rotate `TELEGRAM_BOT_TOKEN` via BotFather (printed by a probe
   on 2026-09-02); dedupe the doubled `CLAUDE_CODE_OAUTH_TOKEN_3` line in
   `~/.nuzantara-secrets.env` (one `export` line per slot); rotate the burned Supabase Postgres
   password and the Google OAuth triple (ledger 2026-08-21, both still valid). → Zero rotates,
   Lane G re-probes presence-only (`${V:+set}`, never `:-`).

8. **Hooks (operator[control-plane]).** Refresh `host_boundary.py`, `worktree_isolation.py`,
   `model_routing_gate.py` under `~/.claude/hooks/` on all three machines — Lane G prints the exact
   `cp` line and expected sha256 per machine below. → Zero runs the lines.

9. **Interactive model.** Doctrine (2026-07-25, 2026-08-20) puts interactive sessions on Opus 5
   xhigh and keeps Fable 5 manual-only. Keep it, or ratify Fable for a named lane (cost: Team-seat
   weekly inclusion). → README §Session contract follows the ruling.

## Filled in by lanes

- **Item 2 — the two options, priced (Lane D, measured 2026-09-03 on PROD + the canonical).** Nothing
  else in the KBLI lane waits on this: Lot 0 (17 placeholder codes, 9 `KITAS` codes, 1 missing node)
  and Phase 1a's 109 built codes proceed either way. 61 codes, 63 target nodes, both ways.
  - **A — gate on F2 (Lane D recommends).** Client sees no change until F2 ships; then `REGULATED`
    - the statute licence + **the procedure sentence naming the actual issuer** (OJK, the ministry,
      the bupati). Cost: the F2 router increment (3 additive fields on `KBLILicense`, cache `v6`→`v7`,
      2 mouth renderers, 2 test files) + a separate 1-line flip PR after Fly **and** Vercel prove-live
    - 3 cure lots. Risk: delay only — the data is already there, `persyaratan` names the issuing
      body on **61/61** codes.
  - **B — relabel now.** Client sees `REGULATED` + `NIB` / `NIB dan Sertifikat Standar` / `NIB dan
Izin` with no hint that OSS will not issue it. Cost: 3 cure lots, **zero** new router or mouth
    lines. Risk: the client is sent to the wrong door on codes like `85510` (yoga/retreat) and
    `64122` (OJK-licensed) — the licence name is right and the counter is wrong.
  - Measured caveat that binds both: `kewenangan`, the field an `issuer` line would read, holds only
    three generic role labels over these 61 codes (`Menteri/Kepala Badan` 608 rows,
    `Bupati/Walikota` 72, `Gubernur` 16) and names **zero** institutions. `procedure` is the half
    that answers the question; an F2 shipping `issuer` alone would print "issued by Menteri/Kepala
    Badan". Detail: spec §9 of `docs/specs/2026-09-02-kbli-kg-licensing-class-cure-spec.md` (r4).
- Item 3 draft (Lane E): _pending_
- Item 6 ruling sheet (Lane C4): _pending_
- Item 8 one-liners (Lane G, per machine): _pending_
