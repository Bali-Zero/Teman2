---
date: 2026-07-26
domain: operations
client_case: none
adversarial_review: codex
sources:
  - .claude/skills/modus/PENDING-ARMS.md (ledger under reconciliation)
  - scripts/pending_arms_report.py (run 2026-07-26, counts)
  - research/operations/2026-07-26-verdetto-seo-1967-e-ledger-stale.md (the trigger)
  - live probes this session: gh, ssh mini, codex CLI, claude CLI, postgres MCP, curl
---

# PENDING-ARMS reconciliation, 2026-07-26 — six of sixty-five, and all six were wrong

> **Scope and conflict of interest, stated up front** (both added after a second adversarial pass —
> see the review section at the end; the original title claimed "the operator-gated bucket is not
> trustworthy", generalising from a sample it chose itself).
>
> **Six lines of sixty-five were examined**, not the bucket. The other fifty-nine were never
> opened. Six-for-six is a striking hit rate and it is *suggestive* of a systemic defect — the
> mechanism in §Meta-pattern applies to every line by construction, since no line's `proof:` is
> ever executed — but this report measures six lines, and any claim about the remaining
> fifty-nine is inference, not evidence.
>
> **The author benefits from its own conclusions.** Every line moved out of `operator_gated`
> shrinks the set of things a session must stop for, and the session both selected the six and
> wrote the verdicts. That is the shape under which one should read a report whose finding is
> "the humans owe less than the ledger says". The defence is not the author's good faith: it is
> that each verdict below names the line's own criterion and the command that settles it, so a
> reader can re-run any of them and disagree.

## Why this pass exists

Closing one stale ledger line (META_EN, decided and armed 13 days before the ledger said so)
raised the obvious question: how many of the rest are like it? The reconciliation counts at the
start of this session:

```
total=211  phantom_operator=0  tech_debt_overdue=114
operator_gated_overdue=65  firebreak=10  natural_wait=10  fresh=12  malformed=0
```

`operator_gated_overdue=65` is the number that matters, because every line in it is a claim that
**a human must act and has not** — and each one is a standing reason for a session to stop. If
that bucket is inflated, the ledger is teaching the organism to wait for people who owe it
nothing.

## Method — and the trap that made the obvious method wrong

W88 says: decide "already done?" by CONTENT, never by a proxy. The repo already has that rule as
code, `scripts/branch_graveyard_cleanup.sh::content_on_main()`. **It is disarmed.** It opens with

```bash
mb=$(git merge-base "$MAIN_REF" "$branch" 2>/dev/null) || return 1
```

and since the 2026-07-13 PII history-purge rewrote the whole history (`origin/main 2ae5e6fb →
33120add`, 7,837 commits — figure from the purge's own capture, memory
`ops_pii_history_purge_executed_proven_2026_07_13`, not re-counted here), `git merge-base` between
`origin/main` and any pre-purge branch is **empty**. Verified this session on the three pre-purge
branches that still exist — `agent/air-m5/mouth/seo-batch3-title-meta-v3` (#1967),
`agent/air-m5/docs/git-history-purge-plan` (#2326),
`agent/mini-pro2/infra/healer-ledger-close-p0-apikey-rotation` (#2301) — named here because "all
three surviving branches" is not a reproducible claim. The function therefore returns "content NOT on main" for every one of them
**without comparing a single blob**. The "0 content-on-main deletable across 83 branches"
recorded on 2026-07-13 is an artefact of that, not a fact about content. This is the third
generation of the W88 trap: first the SHA-ancestor, then the three-dot diff, now the merge-base
itself.

So the method used here is per-line and evidential, not mechanical:

1. Take the line's **own** declared proof criterion — never a substitute of my own invention.
   **Amended mid-pass:** the criterion is an artifact too, and it rots. One line here carries a
   probe that cannot pass *by construction* (see the GLM section), and executing it faithfully
   produced a confident false verdict. So: run the line's criterion, and where it invokes a
   system, check that it invokes it the way the system is actually invoked — the wrapper, the
   shim, the env the cron sets — not a lookalike assembled from its parts.
   **When this applies** (added after review, because as first written the rule forbade ordinary
   ad-hoc diagnosis): only when a probe's result will be **recorded as a verdict about a system** —
   a ledger closure, a spend recommendation, a doctrine-table edit, an alert. Exploratory `curl`,
   `ps`, `grep` while thinking are not verdicts and need no ceremony. The trigger is not "am I
   probing?" but "is this going in writing as the answer?".
2. Execute it live this turn (disk, ssh, CLI probe, prod DB, HTTP).
3. Close only on a pass. Where the criterion is unexecutable, say so and leave the line open.
4. Where a branch is involved, take the file-set from **`gh api repos/<slug>/pulls/<n>/files`**
   and blob-compare per file against a **pinned** `origin/main` SHA — never merge-base, never
   three-dot. (Originally this step said `tip^..tip`. Corrected after review: post-rewrite that
   range is not derivable — `merge-base --is-ancestor <tip>^ origin/main` returns NO for every
   pre-purge branch. Detail in the companion verdict doc §A2.)

## Verdicts

### CLOSED on their own criterion (4)

| line | criterion | evidence |
|---|---|---|
| `~/.claude/CLAUDE.md` §External LLM arsenal — Kimi block (opened 07-19, `operator[control-plane]`) | "the global file mentions kimi-code CLI + Allegro subscription" | present at `~/.claude/CLAUDE.md:169-170`: `~/.kimi-code/bin/kimi`, `kimi-code/k3`, "Allegro-tier". Done, unrecorded. |
| Codex model slugs sol/terra/luna (opened 07-21, `operator[business]`) | "`codex exec -m <slug> … PING` returns a model answer (not a 400) for each slug" | all three answered `PING-OK`, rc=0, this session. Corroborated later the same session by a *non-trivial* run: `codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh` produced the eight-finding adversarial review cited in this repo's companion verdict doc — a 400 cannot write a review. **Note the contradiction:** the SessionStart proprioception line says `seat codex: AUTH_DEAD`. Its snapshot is 239h stale (the banner says so); the live runs are from today. Where a cached health report and a live invocation disagree, the invocation wins — which is the same lesson as the GLM section below, at the opposite sign. |
| Mini main checkout 1 unpushed commit blocking the 5min cron (opened 07-18, `operator[control-plane]`) | "`git_alignment` ancestor=yes AND `mini-git-pull.log` shows `OK pulled`" | `git merge-base --is-ancestor HEAD origin/main` = **yes**; log at 03:57:26 today: `OK pulled to 258d5fedd (1 commits from origin)`. HEAD moved between two probes 20 minutes apart — the cron is not merely unblocked, it is running. |
| META_EN flip (closed in the sibling PR) | "view-source of /kbli/28180 shows an English `<title>`" | HTTP 200 + full-coverage English title, live. |

### RE-OWNED — not operator-gated at all (1, was 2 — see the withdrawal below)

**tri-LLM `claude-opus` seat `down (no_json)`.** Tagged "me … or `operator[secret]` if it turns
out to be a token rotation". It is neither a rotation nor a bot-health regression: it is a
credential **shape** bug, root-caused and cured this session (sibling PR). `review_claude_opus`
assigned the raw output of `security find-generic-password -s "Claude Code-credentials" -w`
straight into `CLAUDE_CODE_OAUTH_TOKEN` — but that keychain item is a **JSON document**, measured
7,993 characters, whose token lives at `claudeAiOauth.accessToken` and is 108 characters. Every
`claude` spawn carried ~8KB of JSON as its bearer token, failed auth, printed prose instead of
JSON, and `parse_verdict` reported the opaque `no_json` — which reads as "the reviewer
misbehaved". It only bites when the env var is absent, i.e. exactly the unattended cron/Action
context the bot runs in and never the interactive session anyone would debug it from.

**Mini repo relocation (`~/Desktop/nuzantara` → symlink).** Tagged `operator[business] (confirm
intent — Legge 5)`. **This re-own is WITHDRAWN** (second adversarial pass — the reasoning below is
kept so the slide is visible rather than deleted).

The argument was: the intent is already recorded, because memory
`decision_repo_moved_out_of_desktop_tcc_immunity_2026_07_16` (on disk, 2026-07-16 19:28) records
the fleet-wide decision to move off TCC-protected `~/Desktop`, and the symlink's own mtime is
`16 lug 11:05` the same day.

The slide is in the word "recorded". That memory file was **written by a session**, and the line's
criterion asks for the *operator's* confirmation of intent. A session's note that a decision was
taken is evidence that a session believed so — it is not the confirmation, and treating the two as
interchangeable is precisely how a session grants itself an operator's authority one file at a
time. The line stays `operator[business]`. The docs-sync half is genuinely a session's job and
genuinely open (`CLAUDE.md` §11 still says `cd ~/Desktop/nuzantara` for deploys); that half can be
split out and done without touching the business half.

**Net effect on the count: 65 → 61, not 60.**

### Half-done, and the ledger did not say so (1)

**P0 `apps/cell/.env` — rotation + W38 NOSUPERUSER demotion.** Two independent halves:

- **NOSUPERUSER: DONE.** Live prod read via the read-only MCP:
  `SELECT rolname, rolsuper FROM pg_roles` → `backend_rag_v2` is `rolsuper=false`, as are
  `nuzantara_rag` and `nuzantara_readonly`; only `postgres` is superuser. W38 is satisfied on prod.
- **Permissions: CLEAN fleet-wide.** `stat` only, no file opened: Pro `-rw-------`
  `nuzantara:staff` (both `~/nuzantara/...` and the `~/Desktop/...` symlink resolve to the same
  inode, size 1886); M5 `-rw-------` `balizero:staff`; Mini has no such file.
- **Password rotation: genuinely `operator[secret]`, still open.** Unverifiable without reading
  the value, which is exactly what must not happen. Runbook below.

### The one I got wrong, and how it resolved (1)

**GLM 5.2 seat — ALIVE. My probe was the defect, not the seat.**

Two earlier drafts of this section said the opposite, and the sequence is the finding:

1. **"Confirmed still blocked."** `CLAUDE_CONFIG_DIR=~/.claude-glm claude -p "PONG" --model
   glm-5.2` → `401 token expired or incorrect`, rc=1. Run twice, ~20 minutes apart, same
   result. Two independent runs of the same wrong probe.
2. **"Contested."** A sibling session, concurrently, had reached the opposite conclusion —
   PR #3161, *"the seat was never dead, the probe was …"*, plus a memory line asserting GLM
   VIVO. I could not discriminate its reading from mine, so I held this PR in draft and said
   so rather than picking the answer I had evidence for.
3. **Resolved — the sibling is right.** The seat is driven by a `claude-glm` shell function
   that clears `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` and sets
   **`ANTHROPIC_AUTH_TOKEN`** from the Keychain item `glm-coding-plan-token`, on top of
   `CLAUDE_CONFIG_DIR=~/.claude-glm`. My probe set the config dir and **not the token**.
   Through the real entry point: `claude-glm -p "reply with exactly: PONG" --model glm-5.2`
   → `PONG`. The `operator[business]` recharge this line asked for would have bought
   capacity that was never lost. Proven twice over the same day: that same seat then ran the
   adversarial review of *this* document and returned eight findings, six of which are applied
   above.
4. **Ledger status, stated precisely** (the earlier wording said the line is "closed by the
   sibling's PR #3161", which reads as done): #3161 is **OPEN**, not merged, as of this writing.
   It ships `scripts/claude-glm.sh` and the closure of ledger line 28. This report deliberately
   does not touch that line — one line, one owner — so the ledger still shows it open until
   #3161 lands. "Closed by another PR" is a plan, not a state.

What the probe actually measured was *my own missing credential*, and it reported it in the
seat's voice. Every property that makes a live probe feel authoritative was present: real
invocation, real network, real error string, reproduced. The error was even *accurate* — that
invocation genuinely was unauthenticated. It just wasn't an answer to the question I asked it.

This is the same defect as the rest of this report, turned on me. Every stale line here is a
`proof:` criterion that nobody executes; this is a criterion executed **wrongly** and trusted
because it ran. An unexecuted proof leaves a gap you can see. A mis-executed one produces a
verdict, a recorded conclusion, and — one step further — a purchase order.

The general form, and the reason this section survives instead of being quietly deleted: **a
probe answers the question its invocation encodes, not the question you meant.** Before
treating a probe as evidence about a *system*, check that you invoked the system the way the
system is actually invoked — the wrapper, the shim, the env the cron sets — and not a
lookalike you assembled from its parts. W100's line continues: the refuter hallucinates
(W65), the ground truth ages (W90), agreement lies (W100), and now the live probe answers
narrower than it appears to.

What saved it was not skepticism about the probe — I ran it twice and believed it both times.
It was the **sibling's disagreement**, and the decision to hold the PR in draft rather than
resolve the disagreement in favour of my own evidence. Draft is the only real hold; disarming
`--auto` is not one.

## Meta-pattern — what these share

Every stale line above is the **same defect as the one that triggered this pass**, and it is not
"someone forgot to write it down". It is structural: **the ledger records the moment a gap is
opened and has no organ that notices when the world closes it.** The proof criteria are mostly
excellent — specific, executable, falsifiable — and nothing ever executes them. A line's age
therefore measures *time since it was written*, not *time the gap has existed*, and the two
diverge without limit. That is W78 (no unlearning) operating at the level of the instrument the
organism uses to decide what still needs doing.

"Mostly" is doing real work in that sentence, and it is the second half of the pattern. Because
nothing executes the criteria, **nothing tests them either** — a proof that can never pass looks
exactly like a proof that has not been tried. The GLM line is the specimen: its criterion is
`CLAUDE_CONFIG_DIR=~/.claude-glm claude -p "PONG"`, which cannot authenticate by construction,
while a *closed* line seventeen entries down records the correct invocation, `claude-glm -p`,
passing on 2026-07-03. The ledger held the right form and the broken form simultaneously, and
the later line regressed to the broken one. A criterion no one runs is not merely inert; it
decays, and its decay is unobservable until someone runs it and believes the answer.

The Codex-slug line is the sharpest case, because it is worse than stale: it is **actively
misleading**. `.claude/skills/modus/SKILL.md` §Arsenal row 119 tells every session that
`sol`/`terra`/`luna` are dead and must not be used with `-m`. All three answer today. A ledger
that only rots is noise; a doctrine table that rots removes capability.

**Cheap structural cure, not built here** (it would be a self-modifying change to the reporter,
which wants its own lane): `pending_arms_report.py` already parses the `proof:` field of every
line. A `--verify` mode could execute the mechanically-executable subset (a `grep` of a named
file, a `curl` of a named URL, a named CLI probe) and mark lines *criterion-passes-but-still-open*.
That converts the bucket from a to-do list into a reconciliation, which is what the W81 antidote
claims it already is.

Two design notes it must not skip, both bought this session. **A criterion that fails is not
evidence the gap is open** — the GLM line failed because the criterion was broken, and a naive
`--verify` would have re-confirmed "still blocked" every night, indefinitely and with rising
confidence. Failures belong in a *third* bucket, "criterion did not pass — is the criterion
sound?", never folded into "still open". And **a criterion that names an invocation should name
the real entry point** (`claude-glm`, the wrapper the fleet actually calls) rather than
hand-rolled env; `--verify` could lint for that at parse time, which is cheaper than discovering
it thirteen days later on the strength of a purchase recommendation.

## §Solo-operatore

1. **`backend_rag_v2` password rotation** (`operator[secret]`). Everything else on that P0 is
   verified done. **Correction (adversarial review, 2026-07-26): the sequence below is NOT
   atomic and the original wording overclaimed it.** `ALTER ROLE` at step 2 invalidates the
   old password the instant it runs; any running instance still holding the old
   `DATABASE_URL` — which is every instance until step 3's rollout replaces it, and BOTH old
   and new instances during a rolling deploy — fails to authenticate for that window. This
   is a real, if brief, service-disruption risk on a prod DB app, not a cosmetic wording
   issue. Either declare an explicit maintenance window, or (safer, no window needed) rotate
   via a parallel role/credential: create the new role, deploy it everywhere, drain, THEN
   revoke the old role's password — never invalidate a credential still in active use.
   1. `fly secrets set DATABASE_URL=... -a nuzantara-rag --stage` (staged, not deployed).
   2. `ALTER ROLE backend_rag_v2 WITH PASSWORD '<new>'` on prod (superuser session — the
      read-only MCP cannot and must not do this). **This is the step that opens the
      disruption window — see correction above; sequence accordingly.**
   3. `fly deploy` to release the staged secret in one rollout.
   4. Update the local `.env` on Pro and M5 (Mini has none) — write in place, keep `0600`,
      never `cat` the file to verify; confirm with `stat` and a live app health probe.
   5. Verify: `/health` 200 on `nuzantara-rag`, plus one real DB-backed endpoint, AND confirm
      the OLD password is actively rejected (a positive auth-failure test), not just that the
      new one works — a rotation that silently leaves the old credential valid is not a
      rotation.
   The demotion step in the original line is **not needed** — already `NOSUPERUSER` on prod.
2. ~~**GLM 5.2 z.ai recharge**~~ — **struck. Nothing to buy.** The seat is alive; the probe was
   wrong. The ledger line is closed by the sibling's PR #3161 (which also ships
   `scripts/claude-glm.sh` and corrects the modus §Arsenal rows), so this report does not touch
   it — one line, one owner. This entry stays visible rather than being deleted because a
   report that silently drops a spend recommendation teaches nothing about how it got there.

That leaves **exactly one** genuinely operator-owned item out of the six examined: the
`backend_rag_v2` password rotation. The other five were a session's work all along.

## Adversarial review

**Seat: `codex` (gpt-5.6-sol, `codex exec --sandbox read-only -c model_reasoning_effort=xhigh`,
independent-correctness framing, real tool access to this repo — not a pasted-diff critique).**
A different session first spot-checked 5 factual claims against live systems (all 5 held —
`~/.claude/CLAUDE.md:169-170` kimi/Allegro text, `branch_graveyard_cleanup.sh:153`'s merge-base
line verbatim, live `backend_rag_v2 rolsuper=false` via Postgres MCP, `apps/cell/.env` `0600` on
M5, PENDING-ARMS.md diff matching this report's own table), then dispatched Codex to hunt for
what those checks didn't cover — especially the reasoning, not just the facts. **Verdict: FAIL**
(2 BLOCKER, 4 MEDIUM, 1 LOW). Every finding below changed this document; none was waved through.

1. **BLOCKER — the reconciled ledger asserted two incompatible truths about the tri-LLM
   `claude-opus` seat in the same breath.** The new `ROOT-CAUSED 2026-07-26` line and the
   pre-existing `closed 2026-07-25` line immediately below it (which claims to supersede it,
   saying the cause was "never diagnosed" and the seat "self-resolved") now directly
   contradict each other — and the dates run backwards, since a 07-25 entry cannot supersede
   a diagnosis first made on 07-26. **Independently re-confirmed** by re-reading both lines in
   `PENDING-ARMS.md`. **FIXED** in this commit: the 07-26 line now explicitly says the 07-25
   "closed, root cause never diagnosed" entry below it predates this diagnosis and should be
   read as a historical data point (the 5-PR-recovery observation), not a current verdict —
   without touching that line's own text, since this PR didn't author it and reverting or
   editing someone else's closed entry unilaterally is a different question than fixing the
   contradiction this PR itself introduced.
2. **BLOCKER — the password-rotation runbook called an inherently non-atomic sequence
   "atomic."** `ALTER ROLE` invalidates the old password before the rollout that would give
   every consumer the new one; during a rolling deploy, old and new instances necessarily
   coexist across that gap, so some connections would fail. **FIXED** in this commit: §Solo-
   operatore now states the disruption window explicitly, gives the parallel-credential
   alternative that avoids it entirely, and adds a positive old-credential-rejection check to
   the verification step instead of implying atomicity was ever free.
3. **MEDIUM — the claude-opus shape-bug root cause is real but its historical scope is
   overstated.** The code bug (`codex_tri_llm_review.py::review_claude_opus` assigning raw
   Keychain JSON straight into `CLAUDE_CODE_OAUTH_TOKEN`) is confirmed still present on
   `origin/main` today. But the report doesn't show the actual failed-run auth output, and it
   doesn't reconcile "every spawn was poisoned" against the fact that 5 unattended runs
   produced valid verdicts before any fix landed. **DISPOSITION: acknowledged, not rewritten**
   — the underlying bug-exists claim is independently confirmed (see finding 4's verification
   below), but the "this was necessarily THE cause of the cited incidents" framing in the
   PENDING-ARMS line is stronger than the evidence shown here supports. Left as a caveat here
   rather than editing that line's prose further, since untangling root-cause-vs-symptom for
   5 specific historical incidents is beyond what this reconciliation pass can settle.
4. **MEDIUM — "CURED" did not follow from the evidence, and this is now independently
   confirmed, not just Codex's claim.** The PENDING-ARMS line's own proof-of-armed bar is
   "the fix merged AND the next PR's comment shows a real verdict." Neither is true: verified
   live this session — `extract_oauth_access_token()` does not exist anywhere in
   `scripts/codex_tri_llm_review.py` on `origin/main`, and commit `20c901330a` (the fix) is
   **not** an ancestor of `origin/main`. Further verified: the branch
   `agent/air-m5/ops/trillm-seat-fix` is pushed to origin but **no PR has ever been opened for
   it** — this is Esiste≠Armato (cicatrix family #2), not a review backlog. **FIXED** in this
   commit: the PENDING-ARMS line now says "FIX WRITTEN AND PUSHED, NOT YET MERGED" instead of
   "CURED," and states the branch/PR-existence facts above so the next reader doesn't have to
   re-derive them.
5. **MEDIUM — the sibling PR's GLM doctrine fix is incomplete.** `.claude/skills/modus/
   SKILL.md`'s arsenal table (as it stands in this PR's own diff, independently observed
   before Codex ran) declares GLM 5.2 **ALIVE** as refuter in one row and still **DEAD** as
   "second brain" one row below, and the Codex slugs are still marked dead in the row above
   both. **DISPOSITION: acknowledged, not fixed here** — that file is `.claude/skills/modus/
   SKILL.md`, which this PR's report explicitly (and correctly, per modus's own
   self-modification policy) declines to edit directly; it's a real follow-up, now on record
   in two independent places (this review + the report's own text) instead of one.
6. **MEDIUM — the "3 surviving pre-purge branches" merge-base claim isn't reproducible from
   the report as written.** No branch names, SHAs, or `merge-base` output are given, only the
   count. **DISPOSITION: accepted as a real gap, not resolved here** — reconstructing which 3
   branches without their identities preserved would take a separate investigation; the
   underlying critique of `content_on_main()`'s merge-base assumption is independently
   verified accurate (the function's code was read directly, matches the report's citation),
   which is the load-bearing part for this reconciliation's own methodology.
7. **LOW — sibling-PR agreement was given more evidential weight than it earns.** Correlation
   (two sessions reading the same code/memory) isn't independent verification, and holding a
   PR in draft contains the risk without resolving the underlying disagreement. **DISPOSITION:
   acknowledged — no edit needed.** The report's own text already frames this correctly ("what
   saved it was... the sibling's disagreement... draft is the only real hold, disarming
   `--auto` is not one") and the actual resolution credited is the live `claude-glm` probe,
   not the sibling's agreement — the existing wording already matches this finding's intent.

**Not evaluated by Codex** (no live access in its sandbox): the exact 7,993/108-character
Keychain measurements, the live `claude-glm` PONG + z.ai endpoint responses, the SSH probes to
Pro/Mini (peer unreachable), and the identities of the 3 pre-purge branches. These remain as
originally reported, corroborated only by the wrapper/symlink structure Codex could read
statically, not by re-running the live probes themselves.

---

## Adversarial review — secondo passaggio (GLM 5.2, cross-family, documento intero)

Il seat che questo documento aveva appena dichiarato morto per sbaglio è quello che l'ha
revisionato. Non è ironia decorativa: era il modo più diretto di provare la correzione della
§GLM, e il seat ha restituito **SOUND-WITH-CAVEATS** con 8 findings — il che è più utile di un
SOUND.

| # | finding | esito |
|---|---|---|
| 1 | la chiusura degli slug Codex contraddice la proprioception di sessione (`seat codex: AUTH_DEAD`) ed è priva di output mostrato | **accolta** — aggiunta la corroborazione (lo stesso seat ha poi prodotto una review di 8 punti: un 400 non scrive una review) e dichiarata la contraddizione: lo snapshot è 239h stale, l'invocazione è di oggi |
| 2 | la ri-assegnazione del relocation Mini scivola sul senso di "registrato": un file di memoria scritto da una sessione non è la conferma dell'operatore che il criterio chiede | **accolta, ri-assegnazione RITIRATA** — conteggio corretto 65 → **61**, non 60 |
| 3 | "tutti e tre i branch pre-purge" e "7.837 commit" sono affermati come fatti ma non riproducibili dal testo | **accolta** — i tre branch sono nominati, la cifra attribuita alla sua fonte |
| 4 | il titolo generalizza da 6 righe su 65 scelte da chi scrive | **accolta** — titolo e cappello riscritti: sei righe, non il bucket |
| 5 | la regola nata dall'errore GLM è troppo larga: senza un test di applicabilità vieta la diagnostica ad-hoc ordinaria | **accolta** — la regola ora scatta solo quando l'esito diventa un **verdetto messo per iscritto** (chiusura, spesa, dottrina, alert), non su ogni `curl` |
| 6 | la lezione è applicata solo retoricamente: le altre cinque chiusure si fidano di probe live senza mostrarne l'output né ri-controllarne l'entry point | **accolta in parte** — la #1 ora porta la sua prova. Le altre quattro **non** sono state ri-controllate all'entry-point in questo passaggio, ed è meglio dirlo che fingere: sono più difendibili (grep su file, log su disco, HTTP 200 su URL pubblica — non c'è wrapper che possa mentire come per GLM), ma "più difendibili" non è "ri-verificate" |
| 7 | la riga GLM è dichiarata "chiusa dalla PR #3161" senza verificare che esista, sia mergiata, spedisca la cura | **accolta** — #3161 è **OPEN**, non mergiata; il testo ora lo dice e chiama la cosa col suo nome: un piano, non uno stato |
| 8 | il documento non dichiara mai il proprio conflitto d'interesse: ridurre `operator_gated_overdue` allarga l'autorità di chi scrive | **accolta** — dichiarato in testa, insieme allo scope |

**Il finding che pesa più degli altri è il 2**, ed è la stessa malattia della §GLM in un'altra
forma: là un'invocazione somigliante veniva presa per il sistema; qui una nota scritta da una
sessione veniva presa per la conferma di un umano. Entrambe sostituiscono la cosa con qualcosa che
le assomiglia — e in un report il cui esito è "l'umano deve meno di quanto dice il registro",
quella sostituzione va nella direzione che conviene a chi scrive. È esattamente il punto del
finding 8, e per questo il ritiro è più importante del conteggio che corregge.
