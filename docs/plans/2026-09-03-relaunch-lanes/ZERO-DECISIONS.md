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

- Item 3 draft (Lane E): **ready — see §Item 3 below.**
- Item 6 ruling sheet (Lane C4): _pending_
- Item 8 one-liners (Lane G, per machine): _pending_

---

## Item 3 — the citation rule, replacement paragraph (drafted by Lane E, 2026-09-03)

**Where it lives.** One paragraph, one file: `apps/backend-rag/backend/prompts/zantara_core.py`,
inside `CITATION_RULES` (the `MANDATORY LAW CITATION` bullet, currently line 314). That constant is
the SSOT for the whole prompt chain — `zantara_core_v4.py:517` and `zantara_core_v5.py:259` both
interpolate it, and `wa_package_builder.py:41-45` imports it directly into the codex-leg persona.
So changing this one bullet changes every prompt version **and** the live WhatsApp path, and no
other file needs to move. Verified 2026-09-03 by grep: `MANDATORY LAW CITATION` appears in
`zantara_core.py` only.

**Why it needs an exit.** The rule says the model **MUST** cite the source law at the end of every
response, and when the KB lacks the article it says to "cite the regulation name only". There is no
licit path to cite _nothing_. A model that is forbidden to stay silent will produce the
nearest-sounding statute. Two measured instances, cycle 359 (WhatsApp thread 30, 2026-09-01):

- Asked _"posso pagare con bonifico?"_ — a question about how a client pays Bali Zero — the bot
  closed with **PP 36/2021**, which is the regulation on **wages**. No statute governs our bank
  details; the rule required one anyway.
- Asked why it would not accept a passport photo in chat, the bot cited **immigration law** as the
  basis. The reason is data protection and our own intake policy; immigration law says nothing
  about the channel a document arrives on.

Neither is a retrieval failure. Both are the rule working exactly as written.

**Proposed replacement** (drop-in for the `MANDATORY LAW CITATION` bullet; the LEGAL/MONEY and CHAT
bullets above it are unchanged):

```
  - **LAW CITATION — required when a law is the basis, forbidden when it is not.**
    Cite a source law at the END of a response ONLY when the answer's substance rests on a
    statute, regulation or official tariff that is present in the KB context you were given.
    Format: "📜 Sumber: [Nama Peraturan], Pasal [X]" or "📜 Source: [Law Name], Article [X]".
    Examples:
    - "📜 Sumber: PP 48/2021 tentang Keimigrasian, Pasal 123"
    - "📜 Sumber: UU PPh No. 36/2008, Pasal 26"
    If the regulation is in the KB but the exact pasal is not, cite the regulation name alone:
    "📜 Sumber: PP 48/2021 tentang Keimigrasian".
    **Cite NOTHING — and add no source line at all — when:**
    (a) the question is operational or commercial rather than legal: our prices, our payment
        methods and bank details, our timelines, which documents WE need from a client, how to
        send them, appointment or office logistics, the status of a file;
    (b) the answer is a courtesy, a greeting, a clarifying question, or a hand-off to a
        colleague;
    (c) the KB context you were given contains no regulation that actually governs the answer.
    In case (c) you may still answer from the context you have — you simply do not attach a
    citation, and you never name a law you were not given.
    **A citation is a claim about the source of the answer. Naming a statute that does not govern
    the question is a fabrication, and it is worse than no citation** — an operational answer with
    no source line is correct and complete.
```

**What changes, in one line:** `MUST cite` becomes `cite when a law is the basis, and never
otherwise`; the "cite the regulation name only" fallback narrows to regulations actually present in
the context; and the three no-citation cases are named so the model has somewhere licit to land.

**Proof, once applied (Lane E runs it, not Zero).** Re-ask the two cycle-359 questions on the real
thread and require: zero `📜` line on the bank-transfer answer and on the passport-photo refusal;
`📜` still present on a substantive immigration or tax answer (the innocence half — the cure must
not turn into a silent removal of citations). Both re-measured on real delivery, in the cycle-360
battery table.
