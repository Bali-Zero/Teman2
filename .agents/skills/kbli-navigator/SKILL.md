---
name: kbli-navigator
description: "KBLI Navigator corner — the live shared context AND the full plan-to-the-end for ALL KBLI corpus/product work (dataset, gold, KG, editorial, kbli pages on balizero.com). Load BEFORE touching any KBLI data or code, or when Zero says /kbli-navigator, 'kbli corpus', 'filiera', 'garuda', or references the July 2026 disease cluster. Holds: the north star (re-validate all 1,559 codes), established truths (verified, with method), LIVE STATE, the GARUDA-FILIERA roadmap (phases 0-3, D0-D6 protocol, batches, seats), artifacts & access, blood-bought operating rules."
---

# /kbli-navigator — KBLI corpus & product corner (project brain)

> Created 2026-07-16 on Zero's order after the July disease cluster; promoted to the standing
> project brain on 2026-07-17 ("crea la skill del contesto così da avere il nostro progetto sempre
> pronto — tutto il contesto e il piano fino alla fine"). This file is the HOT CONTEXT shared by
> every Fable/Claude session and every Codex dispatch working on KBLI. It states the GOAL, what is
> PROVEN, what is IN FLIGHT, the PLAN to the end, and the rules paid for in blood.
> **Update the LIVE STATE section whenever it changes — this corner is only useful if it stays true.**

## 0. The product + the north star

`balizero.com/kbli/<code>` (apps/mouth, 1,559 KBLI-2025 code pages) + the RAG/KG backend answering
KBLI questions on WhatsApp/webchat (`inspect_kbli`/`chat_kbli`/`search_kbli`). Clients make real
licensing/investment decisions on this data — a wrong risk row is client-facing harm (cf. Darinka
KBLI dispute). Honesty beats completeness: a declared gap ("licensing not yet published") is
acceptable; a plausible-but-wrong assertion is not.

**THE NORTH STAR (do not lose it): re-validate the WHOLE navigator — all 1,559 codes — against
government ground truth, code by code.** The 8 collision codes cured so far are the _proven pilot
pattern_, NOT the goal. The goal is a navigator where every rendered risk / licensing / PMA / Bali
fact is either government-sourced (with a citable locator + vintage) or an honest declared gap —
zero silent cross-vintage fill anywhere in the catalog. §5 is the plan that gets us there.

## 0bis. DO NOT REUSE THE WORDING IN `research/content/` — 5 drafts + 2 book chapters are retracted

Seven captures under `research/content/` still argue the **withdrawn** no-Usaha-Besar inference:
`articles/04-consulting-in-bali-the-first-door-to-close.md`, `05-pondok-wisata-vs-villa.md`,
`09-wellness-and-aesthetics-an-open-door.md`, `19-what-changed-from-kbli-2020-to-2025.md`,
`20-the-honest-map-blocked-bali-codes.md`, `book-chapters/ch-the-surf-coliving-55209.md`,
`ch-the-yoga-and-retreat-85510.md`. Their PUBLISHED counterparts were corrected on 2026-08-03
(PR #3579, en/it/id). The drafts are left intact **on purpose** — rewriting a dated capture
falsifies a record — and the warning lives here instead of in a banner inside them, because a
banner drags an untouched `research/**/*.md` into the R1 gate, and the only compliant values
would be a review those bodies never had or an `exempt-` that is false for a file declaring
`client_case:` (superscar #3 / W109: an exemption is an assertion about the document). A future
session reads this corner; it does not browse `research/`.

Also stale in `20-the-honest-map-blocked-bali-codes.md` and its `_INDEX.md` row: the blocked count
is **518 / 33.2%**, not 465 / 29.8%, and `CHIUSO_PMA_NO_BESAR` is **7**, not 20.

## 1. LIVE STATE (last update 2026-09-01 — keep current)

**🟢 2026-09-01 — THE 11 `pma_status` DIVERGENCES ARE 0, AND THE CONSUMER MAP GAINED THE LINE IT
WAS MISSING: AT RUNTIME QDRANT WINS.** The Pro conformance detector (armed 2026-09-01) named 11
`kbli_documents` rows whose `pma_status` disagreed with the VERIFIED canonical. Curing the table
first proved nothing on the channel: `chat_kbli`'s direct lookup reads `kbli_documents.metadata`,
but `_fill_bali_verdicts` (`kbli_notebook_chat.py:211-295`) re-reads the **Qdrant** BPS point for
every result with `bali_blocked is None` and overwrites the whole PMA tuple, and `inspect_kbli`
reads Qdrant first (`kg_nodes` fallback) — so §4 rule 6's four stores have a precedence, and it is
Qdrant → KG → Postgres, not "keep them all in sync" as equals. What shipped: Qdrant PMA layer
synced on the **54 canonical-`located` codes** (`kbli_qdrant_pma_sync.py --layer pma --codes`, 53
written, 54/54 re-verified), inspect cache busted, KG resynced 54/54; `kbli_documents` 5 rows by
full rebuild + 6 hand-written rows by the new **`--pma-only`** mode of `kbli_documents_cure.py`
(PR #5489 — syncs the 7-key PMA tuple via a server-side jsonb merge, judul/content byte-identical
by md5 before/after; 3 Codex adversarial rounds, 116 tests). Detector now: `pma_status disagrees
with VERIFIED canonical: 0`; `licensing presence disagrees: 25` is the next PR. Proven live:
`inspect_kbli 65111` TERBATAS 80% PP 14/2018; `96220` TERBATAS 0% Lampiran II; `chat_kbli` 65201
TERBATAS 80%. **Two things this cure surfaced, both ledgered in PENDING-ARMS (2026-09-01 rows):**
(1) the canonical is `located` on 54 codes only — the other 1,505 answer `NOT_VERIFIED` by design
of the 15/8 fail-closed disclosure (56101 included) while the mouth cites a residual Pasal 3(1)(d)
locator for all 1,559; a whole-catalog sync would relabel ~1,500 answers, so it was NOT run —
Legge 5 decision; (2) `archive_params` snapshots rows through a Python round-trip (inherited debt,
declared by the refuter, did not bite tonight — probed first). Discipline that paid for itself:
cure → cache-bust → probe, never probe first (`inspect_kbli` caches 30 days); `--pma-only` for
hand-written rows, never full `--only` (03110 would have become a 55k-char document).

**🔴 2026-08-20 (later) — P2b BENCHMARK EXECUTED: GATE RED, P2c STAYS CLOSED — two surgical
product defects, ZERO fabrication found.** The seat's usage window reset early (probed
`SEAT-OK`, never assumed); the suspension entry below is CLOSED. Full run: 29 questions × 3 =
87 answers on Pro (`codex-cli 0.148.0`, terra serving, sol judging, 0 transport errors), report
`research/operations/2026-08-20-kbli-navigator-p2b-benchmark.md` (adversarial: Kimi K3 with
data access, 4 findings folded). Floors: (i) zero-fabrication GREEN (deterministic 87 served +
87 raw, judge, hand-check 100% flagged + 20% sample — every flagged claim traced to a real
record field); (iv) gap/probe abstention GREEN 21/21 served; (ii) accuracy RED 4/8; (iii)
wrongful abstention RED 4/8. The two causes, both curable: **(A) the KBLIAnswerGate
over-matches correct answers into refusals** — 3 classes measured (α negated mention of an
absent code, Q05: "68200 non esiste" is unanswerable under `unknownCode`; β exception clause
quoting its own verified cap, Q22 Menhan; γ multi-code clause with one shared verified cap,
Q13 + 4 gap-side kills) — superscar family #3 arriving in the product's own gate; **(B) one
retrieval miss** — "kafe di Ubud" never packages 56303 (judul literally contains "kafe") nor
56101; the brain then honestly abstained on the ONE Bali-trap structured question. Also cured
in-lane, committed to the app repo: codex version-pin bump 0.147.0→0.148.0 (`6904c47` +
fixture `bc7cacb`) after codex auto-updated on Pro (the fail-closed pin refused 87/87 —
by design), and a REAL fd-leak the re-run suites caught (`8b6081c`: runCapture/versionMatches
leaked ~4 fds/call; killByTempDirScan × ~600 processes = measured 2559/2560 fds, blinding
sweep(); green at P2a by process-count threshold, not correctness). Judge-harness lesson
(W100): sol was fed only the expected-codes record slice while the model answered from its
real 5-record package → 22/30 fabrication flags were false; next re-run must feed the judge
the package named in `package_codes`. NEXT (session-owned, blocks P2c): cure A (3 gate rules
with guilt+innocence corpora), cure B (search scoring), cure the judge harness, re-run this
exact corpus (sha `487bc950…`) → only a green re-run deletes OpenClaw (build B).

**🟢 (CLOSED 2026-08-20 by the entry above) 2026-08-20 — P2b BENCHMARK: TOOLING READY + CORPUS FROZEN + OLD BRAIN MEASURED DEAD; THE
RUN ITSELF IS SUSPENDED ON THE SEAT'S USAGE LIMIT (resumes after 2026-08-22 08:30).** Full
runbook + frozen identities: `scripts/kbli_bench/README.md` (this PR). The short of it:
(a) **corpus frozen** — `scripts/kbli_bench/p2b_corpus.json`, sha `487bc9509d01…`, 29 questions
(25 verbatim from the 2026-08-11 WA grounding battery + 1 EN trap variant + 3 out-of-corpus
probes), classification MEASURED against the §3 allowlist on the canonical: 8 structured /
18 known-gap / 3 probes; expected tuples verified on the dataset (51101→49 single-majority,
79122→0 domestic+faith, 25200→49 Menhan, 68200 absent, moratorium rule/date/source). Freeze
finding: `l4_bali.moratorium.virtual_office` ("BANNED as PMA domicile in Bali") EXISTS in the
dataset but the design's allowlist serializes only `moratorium.{rule,effective,source}` — the
fact is not served, so Q15 grades as known-gap; candidate allowlist addition for a later
increment. With n=8 structured, floor (iii) ≤10% wrongful abstention admits ZERO. (b) **the
OLD brain is DEAD, measured twice** — OpenClaw `zantara-kbli` on Mini fails 7/7 models in its
cascade (openai-codex OAuth refresh dead, openrouter/deepseek 401s, even the local-ollama hop
dies on a broken gateway key); verbatim outputs in `scripts/kbli_bench/oldbrain_probes/`;
probe 3 due at resume for the ≥3-probe absence corroboration. The §8 "where reachable" clause
covers this: the ABSOLUTE floors are the gate; new-vs-old will be declared as trivially
satisfied against an unreachable baseline, never sold as a win. Reviving OpenClaw's auth is
`operator[credential]` and nobody's goal — P2c deletes it. (c) **Swift harness built and
independently verified** — app-repo commit `112241c0` (`Tests/benchrunner/main.swift`, 373 l.,
zero `Sources/` changes): `run` mode = production path exactly (package builder cold-chat →
`KBLICodexRunner` with its own pinned argv/model → real `KBLIAnswerGate.check`), serial,
no-retry, errors recorded; `extract` mode grades arbitrary text (the old brain, if ever
revived) with the SAME gate. Conductor re-verified: compile RC=0 on Pro from fresh rsync,
extract guilt+innocence smoke (25200→"100%" rejected `actual:49`; 51101→"49%" accepted), spot
greps for no-retry/pinned-model/real-gate. (d) **scoring tool**
`scripts/kbli_bench/score_p2b.py` — independent deterministic tuple re-check (8/8
guilt+innocence corpus, multi-code+multi-figure clauses rejected as unverifiable mirroring the
Swift gate), sol judge-prompt emitter, floors calculator. (e) **the blocker, measured**: the
ChatGPT Pro seat answers `You've hit your usage limit … try again at Aug 22nd, 2026 8:30 AM`
— both serving (`terra`) and judging (`sol`) ride that seat; paying is barred (standing rule),
substituting a seat would benchmark a different product. Run A→B ordering per §8 unchanged.
PENDING-ARMS row opened.**

**🟢 2026-08-19 — PHASE 2 IS OPEN, AND NOT WITH OPENCLAW: ZERO ORDERED THE CHAT BRAIN ONTO
CHATGPT PRO VIA `codex exec` (the /bot pattern); THE MORNING'S READ-ONLY BKPM AUDIT CLOSED THE
DATASET-STALENESS QUESTION; AND THE DESIGN'S OWN REFUTER FOUND A NEW DATASET SELF-CONTRADICTION
ON THE TRAP CODES.** Zero, verbatim: _«aggiorna il corner e comincia la phase 2 ma non con
openclaw. studia /bot dove abbiamo messo direttamente chatgpt con abbonamento pro»_.

- **Phase 2 route change (supersedes the 2026-08-09 design's brain choice).** The chat brain
  becomes ChatGPT Pro consumed through headless `codex exec` — a Swift `KBLICodexRunner`
  porting the /bot lane's proven `codex_exec_client.py` invariants (stdin-only prompt,
  `--ephemeral --ignore-user-config --ignore-rules`, neutral tempdir cwd, minimal env with
  `/opt/homebrew/bin` in PATH — codex is a Node shebang script, re-measured this session —
  process-GROUP kill, output caps, single-flight, typed auth-death) + a deterministic
  allowlist context package from the bundled dataset (zero LLM planners, measured cap 64KiB,
  worst case 58.4KiB on 61108) + a deterministic post-generation gate (cited codes ⊆ package,
  % figures must match `pma_max_asing`). No broker, no Fly, no server surface. Design doc:
  `research/operations/2026-08-19-kbli-navigator-phase2-codex-chat-design.md` — Codex GPT-5.6
  sol refute-stance, EIGHT live rounds on Pro: BLOCKED(13) → BLOCKED(10) → BLOCKED(7) →
  BLOCKED(5) → FIX-FIRST(5) → FIX-FIRST(3) → FIX-FIRST(2) → **SHIP**; 45 findings folded or
  declared, every measurable claim re-verified on the canonical before folding. SHIP scope is INTERNAL fleet only; BKPM chat is explicitly gated
  (isolation + seat + G-P1 training-toggle — §6 owner bundle, honest-offline default). The
  ~25-question benchmark (78-question team test + cured traps) with ABSOLUTE floors (zero
  fabrications, ≥80% accuracy, ≤10% wrongful abstention, 100% abstention on out-of-corpus
  probes, new ≥ old) is the gate that lets the OpenClaw path be deleted. Seat reality (all
  measured 2026-08-19): Pro logged in; M5 probe-positive (0.147.0 + auth.json 0600); Mini
  AUTH_DEAD/headless; BKPM none.
- **🟢 P2a LANDED the same day — implemented, tested, and INDEPENDENTLY verified.** App-repo
  (M5, no remote) commits `0500fa3..b31840c` (5 atomic): `KBLIContextPackage.swift` (660 l. —
  recursive allowlist with fail-closed schema snapshot over all 1,559 records,
  byte-budgeted question-matched `per_skala`, `pma_conflict` on 50111/50112,
  `bali_moratorium_status` rename, anchors/budgets per design), `KBLIAnswerGate.swift`
  (158 l. — NFKC + code-bound % gate), `KBLICodexRunner.swift` (523 l. — stdin-only,
  ephemeral argv, realPath-bound spawn, pgid kill, intent sidecar + launch sweep,
  single-flight, zero auto-retry), `KBLIBrain` wiring (BKPM = marker-check FIRST,
  fail-closed stub, never OR'd with the seat probe; OpenClaw path behind a build-time
  constant, still compiled). Verification was generator≠grader twice over: the implementer's
  own subagent re-read spec-vs-source (clean), and the conductor re-ran ALL THREE test
  suites from a fresh M5→Pro rsync (`packagetest`/`gatetest`/`codexrunnertest` all green,
  RC=0 — including the real-subprocess pgid+cwd sweep tests) and re-verified both built
  bundles (Mach-O universal, correct `BZVariant`, BKPM `articles/`=0). Three real bugs were
  caught by the tests and fixed (inverse-frequency search scoring; decimal-aware sentence
  splitter in the gate; `realpath` canonicalization for `/var` vs `/private/var` in the
  launch-sweep cwd match). Deferred to P2b, declared not faked: the ~25-question benchmark,
  3 of 4 crash-injection transitions, the real BKPM marker mechanism. **NOT fleet-installed**
  — P2c installs only after the benchmark gate (design §8/§9).
- **🔴 NEW RED ROW — the canonical dataset contradicts itself on the exact cured trap codes.**
  Measured this session on `data/source_documents/KBLI_2025_FINAL_CLEAN.json`: `25200`,
  `51101`, `79122` carry `pma_status=TERBATAS` (caps 49/49/0) while each record's own
  `intel_2026.zantaraOpener` editorial text claims Open — 79122 verbatim: _«Nationally this
  carries PMA status: Open»_. The chat design cures its own exposure by excluding `intel_2026`
  from the package allowlist. **Exposure VERIFIED same day (static trace + live production MCP
  probes): the contradictory text reaches NO client surface** — and not by accident:
  `withNeutralKbliChatOpener` (TS, `kbli-editorial-certification.ts:105-113`) /
  `with_neutral_kbli_chat_opener` (Python, `kbli_editorial_certification.py:235-253`)
  unconditionally overwrite `zantaraOpener` with neutral text at EVERY loader boundary
  (mouth `kbli-data.server.ts:160-165` + `kbli-data.ts:400` — so `page.tsx:1050` only ever
  sees neutral text; `reindex_kbli_2025_final.py` L182; `kg_kbli_resync.py` L148-155);
  `chat_kbli`'s direct-lookup path deliberately never selects the `content` column, and
  `inspect_kbli`'s response schema has no editorial field at all. Live probes on all 3
  codes: correct or no-leak. The mouth gold store's own authored text for 51101/79122 is
  already correct — the "Open" sentence lives ONLY in canonical `intel_2026`. Three
  declared residuals: (1) the live Qdrant collections' provenance is structurally protected
  but not empirically proven (the live probes answered via direct lookup, not semantic
  retrieval); (2) the live `kg_nodes` KG is STALE — `inspect_kbli` returns
  NOT_VERIFIED/declared_gap where the canonical says TERBATAS (protective by accident;
  `kg_kbli_resync.py` exists to fix it — its run is its own lane); (3) the non-production
  sandbox `apps/kbli-navigator` gold store carries an even worse authored text for 79122
  ("Fully open — 100% foreign ownership"), registry-gated to null so never rendered, but
  the text exists on disk. **The DATA defect itself stays open** — the wrong editorial
  sentences in canonical `intel_2026` on those 3 codes still want their own cure lane even
  though nothing serves them. **Second defect, found by the design's round-4
  refuter and censused this session: the STRUCTURED fields contradict each other on exactly 2
  records** — `50111` and `50112` carry `pma_max_asing=49` while their own `pma_kondisi` reads
  _"Hanya PMDN (100% domestik)"_ (class sweep over all 1,559: no other hits). Which field is
  right needs adjudication against the Annex (sea-transport entries) — its own cure lane; the
  Phase-2 chat refuses the ownership axis on those 2 records until then.
- **Cross-lane find handed to /bot (PENDING-ARMS row opened):** the deployed
  `codex_exec_client.py` kills only the direct child (`proc.kill()`, line 553, no process
  group) while the broker spec's §2 promises "kill process group on expiry" — spec-vs-impl
  gap, W81 class.
- **The morning's read-only BKPM audit (Mini) closed the staleness question honestly.** Zip
  `build/KBLI-Navigator-BKPM.zip` on M5 intact (sha256 `c6c62fc8…`, 106MB). The zip's dataset
  is rev `a5721756` (8/8) vs main `3dafab17` (15/8) — but a field-by-field diff on all 1,559
  records restricted to the Swift-DECODED fields (`Models.swift`: pma_status, pma_max_asing,
  pma_cap_verified, per_skala, l4_bali, intel_2026…) found **zero differences → no rebuild
  owed**. #4215 (merged 15/8, "release verified KBLI Navigator") closed the PMA axis — all 3
  axes (licensing, PMA, crosswalk) now 100% honest on the canonical. The 3 hand-off blockers
  are unchanged (chat — this Phase 2's job; adhoc signature; GUI QA). Detector on Pro: still
  disarmed, but `~/scripts/cron-runner.sh` is now byte-identical to the repo (the W107 re-copy
  precondition is met; the arming sequence in the 2026-08-13 entry below still applies).
  INTERNAL app on Mini: CANNOT-VERIFY (TCC headless).

**🟢 2026-08-13 — THE BATCH-A ANCESTRY IS PROVEN LIVE AS A CLASS, THE TRI-STATE IS ON THE CANONICAL, AND
THE GOLD-PAGE GAP FINALLY HAS ITS CAUSE.** Four PRs merged this round: `#4129`, `#4126`, `#4141`
(`1305870b6`) and `#4144` (`baf387b7f1`).

**`#4141` — Batch-A ancestry, proven on 30 pages and not on one.** Canonical now carries
`bps_2020_ancestors` for **221 of 221** Batch-A codes; the honest-gap set is **EMPTY**. Promoted from M5
(the Vercel credential lives only there, reachable at Tailscale `100.110.186.116` — `ssh air` resolves to
a link-local IPv6 and times out) and measured live on `balizero.com` across a 30-code spread: **0 false
denials remaining**. The client-facing falsehood ("No official BPS 2020…" on codes whose crosswalk
exists) is closed for the class, not for a sample. Three foreign-cap divergences that the new ancestry
newly exposed (`51103`, `60103`, `60203`) were adjudicated **`BROADER`** — not patched — because annex
entry 31 restricts _air_ transport and 34/35 restrict the LPS/LPB **institutions**, while these codes are
space transport and on-demand streaming; and their candidate ancestors disagree (`60101`/`60201` carry no
annex row at all), so a mis-assigned ancestor would change the value written. Same PR excluded them from
the slice disclosure (`ADJACENT_NOT_CONTAINED`, now five): that surface renders _"One specific activity
INSIDE this code…"_, which **asserts containment** — true for genuine BROADER codes, false for these, and
it would have told a client that part of on-demand streaming is closed to foreign equity. Lesson worth
keeping: an exclusion is an ASSERTION, and it must be verified on **every** surface the entity reaches,
exactly like a guard.

**`#4144` — the `l4_bali.verdict_state` tri-state applied to the canonical.** Distribution
`blocked 95 / open 3 / unknown 25 / provisional 1436` over 1559 records, 17 legacy `blocked=true`
preserved, all 1559 facts bases re-derived before writing. Additive by contract, and proven by an
**independent read** rather than the compiler's own report: `verdict_state` 0 → 1559 and **0 legacy
`blocked` values changed**. Consumer copies synced + sidecar bumped in the same commit
(`sha256:f74b4577c96f…d12da`). Battery `scripts/kbli_filiera/tests/`: **1294 passed, 0 failed**.

**The consequence nobody had written down, and it will hit the NEXT field too:** adding a field to all
1559 records invalidates every whole-record pin in the hardened cure specs, because
`_hardened_cure_io.classify_plan` pins the hash of the **WHOLE record** at its fully-cured state (its own
docstring says the pin must be recomputed after every cure touching the same record). Class censused
rather than patched where it bit: **17 spec files carry `old_sha256` pins (207 entries), but only 4 target
the canonical (17 entries)** — the ten `prose_*` specs pin FIELD hashes and their refusal is byte-identical
against `origin/main`, i.e. pre-existing. The re-pin is licensed by PROOF, never assumption: stripping the
new field from the live record must reproduce the old pin exactly (**17/17** verified). Without that
check, a re-pin launders someone else's drift — the precise failure the guard exists to catch. Then
`emit_batch_calibration` refused on the membership content-address pin and prescribed its own remedy;
re-emitting was verified mechanical first (same 221 codes, 0 added, 0 removed, per-member fields
byte-identical — only 2 pin lines move).

**`verdict_state` has NO render site yet** — no renderer, no Qdrant, no KG reads it. It is inert by
design, so nothing a client sees changed and no store sync was owed. The day something starts reading it,
that sync becomes its own work.

**🔴 ROOT CAUSE FOUND for the 428 gold pages that never render the BPS transition card.** It is not the
data and not the component. In `apps/mouth/src/app/kbli/[code]/page.tsx` there is a ternary `{gold ? (` at
**line 401** whose else-branch opens at **line 681** (same indent, 10); the
`<KBLITransitionSources transition={kbli.transition} />` call sits at **line 913** — inside the **non-gold**
branch. The component is innocent: it always renders the section, either as "Authoritative BPS crosswalk"
or as "BPS crosswalk gap", which is why gold pages show **no block at all** rather than an empty one.
Measured, not inferred: of a 30-code live sample, the 5 pages missing the card were **5/5 gold** and the
25 showing it **0/25 gold**. Fix = hoist the call out of the ternary — but that is a client-facing render
change on 428 pages and wants its own PR and proof. NOT done.

**The `whatChanged` lying-ancestry lane is MEASURED CLEAN — and its guard is blind on a real template.**
Using the module's own predicate (`plan_text`), canonical: 1559/1559 carry a `whatChanged`, **0 would be
changed**. Gold: 428 entries, **0 changed, 0 contradicted**. But `_whatchanged_basis._NAMED_PREDECESSOR`
only matches `KBLI 2020: NNNNN`, so the **73 records** using `Previous code(s): NNNNN` (21 canonical + 52
gold) are unscanned by construction — checked by hand against `bps_2020_ancestors`: **73/73 supported, 0
contradicted**. They tell the truth today by luck, not by enforcement; a `whatChanged` written tomorrow on
that template with a wrong number would pass green. Under-match, W82 family — ledgered, not cured. The 8
gold entries with no canonical record (`64921 85300 85491 85499 85600 86903 96120 96130`) name no
predecessor at all, and their URLs serve `<title>Page not found | Bali Zero</title>` under HTTP **200**
(the soft-404), so that text reaches no client; re-keying stays `operator[business]`.

**🔴 STILL NOT ARMED: the daily surface-conformance detector on Pro (08:20 WITA).** The CODE is merged
(`#4126`) but the on-host install is not done, and the cause is verified rather than assumed: Pro's main
checkout is **23 commits behind** and does **not contain** `infra/launchagents/wrappers/kbli-surface-conformance-run.sh`
at all, while a LIVE sibling (`claude interactive`, 16h+ elapsed) holds that checkout with 17 staged files.
Arming needs a pull that would race live work, and the two shortcuts are both scars: pointing the
LaunchAgent at a temporary worktree is HOME-fork, writing into the held checkout is sibling-race. Remaining
sequence when the checkout frees: `scripts/pro/pro-git-pull.sh` (never `reset --hard` — W117), **re-copy the
live twin `~/scripts/cron-runner.sh`** (it is a REAL file there, currently identical to the pre-`#4126`
main, so the merge alone leaves it inert — W107), `--lint`, first run with a stub gateway, `install`,
`--kickstart`, `--verify`; the ledger row closes **only after a real 08:20 tick**.

**Traps banked this round, all paid for:** `gh pr view --json isInMergeQueue` is rejected as an unknown
field by this `gh` build — the whole command fails, so never put it in a script; a PR **already queued**
reports `autoMergeRequest: null`, so that field alone never proves "unarmed" (ask `gh pr merge --auto`,
which answers _"already queued to merge"_); Codex's `--sandbox workspace-write` has **no network**, so a
delegated `git push` dies with `RC=128`; the Kimi seat dies around 3 minutes, which killed three dispatches
mid-task — one of them after it had already pushed, opened the PR and armed auto-merge, so **measure the
world, not the seat's transcript**; and the third consumer copy
`apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN.json` is **gitignored by design** (the sync script
calls it a "MARCIA zombie"), so no merge ever reaches it — only `scripts/sync_kbli_dataset.sh`, which
refuses to run from a checkout with `main` checked out. It is stale on Pro right now.

**🟢 2026-08-12 — CONTENT CURE SHIPPED, BKPM ZIP REBUILT: the pre-retraction editorial payload is gone
from every surface.** Lane C absorbed: `KBLI-2025-Content/` articles+chapters refreshed from the
post-retraction canon (app-repo `6616dfd`→`1366376`→`5c55a31`), then a REAL cross-family adversarial
review (Codex gpt-5.6-sol xhigh, refute stance, 10 findings each re-measured on the dataset) fixed the
canon itself — 96220 is TERBATAS 0% (not "National: open"), 55201/55203 sit on the SAME Annex II entry
48 (sub-rows _Pondok Wisata_/_Vila_), honest-map arithmetic corrected (33.2% = almost exactly one in
three; all but FOUR of the 372 nationally open; 1,041 = "not blocked") — applied to monorepo masters
`research/content/` EN+ID + `apps/mouth` 5 slugs × en/it/id (branch
`agent/nuzantara/docs/threshold-book-truth`, commits `32f2cb1f0`+`93056fe95`, R1 armed on all 22
research files) and to the app bundle (`5c55a31`, `bf8b26a`). Book PDFs recomposed from the cured
masters (EN 106pp / ID 116pp, 0 retracted patterns, "as amended by"×5 / "sebagaimana diubah dengan"×6,
visual QA on rendered pages) and installed (`fde504d`); both variants rebuilt on Pro, INTERNAL
reinstalled M5+Pro (bundle-wide parity `21fd5e6a…`, relative paths, quit+relaunch both), **BKPM zip
rebuilt** (`build/KBLI-Navigator-BKPM.zip`, sha `c6c62fc8…`, ~106MB — PDFs inside the zip verified by
hash, 0 articles). The PDF verifier also caught a NEW defect: internal label `BLOCCATO_DIPENDE_SCOPE`
naked in the surf chapter prose + "55101–55106 OPEN" false for 55105 (Hotel Bintang Satu, TERBATAS 0%)
— cured in masters and bundle. Traps for the next lane: mouth translations carry `source_sha256` of the
EN body — hand-patching EN makes them "stale" and `translate_hourly` would RE-TRANSLATE over the
hand-cured it/id (cure: `--stamp-baseline`); Pro's pre-push gate REJECTS a push if you commit on the
branch while a push from it is in flight (fix: re-run the push). Mini: INTERNAL app measured ABSENT
from its Desktop 12/8 ~09:30 (contradicts the 9/8 "all 3 Macs" — possibly lost in the 11/8 wedge or an
iCloud eviction), host unreachable again minutes later — realign when it is back. **Hand-off BKPM is now
gated ONLY by the honest gaps below (chat brain, signature, GUI QA) + Legge 5 — no content blocker.**

**TRACK DESIGN — D1 shipped (5609abb) · D2 shipped (6ce988a) — verdict-on-top supersedes the 2026-06-30 order per Zero 2026-08-11.**

**App macOS — design wave D1→D4d SHIPPED+GATED (2026-08-11)**: palette Proposta · shell nativa (sidebar
source-list, search primo quadrante, tema sistema+override ☀/☾, EN/ID trailing) · a11y (Dynamic Type
~190 call-site, VoiceOver, Increase Contrast) · claim ritrattato no-Usaha-Besar rimosso dal template
Swift (verdictBanner legge la l4.reason curata) · search bilingue (titoli EN matchati) · "Anima
Indonesiana": costellazione Nusantara completa accanto al codice + campo guilloché densità-banconota
(hero/footer/sidebar), empty states decorati, About window cerimoniale — firmata da Zero sui render,
prova post-install a diff zero-pixel. App-repo M5 (no remote) commit `0f40cb9`, bundle M5=Pro identici,
Mini da riallineare quando torna in rete. Metodo consolidato: varianti su render → scelta Zero sui PNG →
ship → diff pixel post-install. Research capture design:
`research/design/2026-08-11-kbli-navigator-indonesian-soul.md` (PR #4053, review avversariale Codex
inclusa). Restano: chicchi padi About (decisione Zero). (Il blocco hand-off BKPM da refresh contenuti è RISOLTO
2026-08-12 — vedi il blocco CONTENT CURE sopra.)

**🟢 2026-08-09 — THE macOS APP IS NOW TWO APPS FROM ONE CODEBASE (Zero's ruling), FLEET-INSTALLED AND
PROVEN — AND THE FLEET GUARD'S REFERENCE WAS THE LIAR (W106b).**

**The ruling (Zero, 2026-08-09):** two apps, one codebase, variant decided at build time
(`build.sh --variant internal|bkpm` → `BZVariant` Info.plist key → `Sources/Variant.swift`, single
runtime source of truth):

- **"KBLI Navigator - INTERNAL.app"** — everything: 20 articles, balizero.com links, chat. Fleet + team
  installer.
- **"KBLI Navigator - BKPM.app"** — book only (2 PDFs + 13 chapters); the 20 articles EXCLUDED from the
  bundle at build time; ZERO balizero.com links (verified 0 hits in Resources); chat KEPT — Zero: "we
  need it perfect at answering KBLI questions". Zip staged at `build/KBLI-Navigator-BKPM.zip`
  (~113MB) — hand-off is Zero's call (Legge 5).

**Shipped and PROVEN, not merely reported.** App repo (real path
`/Users/balizero/Desktop/logo/kbli-navigator-app`, M5, no git remote — local commits are complete
actions): the split (`0e1e723`/`5c10772`/`50e1a8f`/`cb65abe`), an SDK fix (`77b1ddb`), a dataset refresh
from `origin/main` (`a18c148`), and the `check-fleet.sh` W106b fix (`91d91eb`). Real universal builds
(x86_64+arm64) run on Pro — **M5 has no Xcode** (CLT-only; SwiftUI macros can't expand; `build.sh`
exits 3 there) — via a build-farm pattern: rsync repo → `pro:/tmp/kbli-app-build`, build, rsync `build/`
back. SDK scar: a bare `xcrun --show-sdk-path` resolves the CLT SDK on Pro against Xcode's macro
plugin → use `xcrun --sdk macosx`. Second build scar: `rm -rf $BUILD_DIR` used to wipe the OTHER
variant's bundle; now scoped per-app.

Fleet install (all 3 Macs): INTERNAL lives on each Desktop, the old "KBLI Navigator.app" moved to each
machine's Trash (reversible). Install scars: macOS `openrsync` fails on remote paths with SPACES → use
tar-over-ssh; **Mini's `~/Desktop` is iCloud-Drive-synced** — the file provider re-attaches xattrs that
break `codesign` in place → sign in `/tmp`, then `mv` (signature survives). `deploy/check-fleet.sh`
final run: **exit 0, all four surfaces aligned on `a5721756d5b2`** (= `origin/main:data/source_documents/
KBLI_2025_FINAL_CLEAN.json`).

**The W106b twist, worth more than the fix.** Post-install, `check-fleet.sh` cried DRIFT on all 3
machines. Chasing the hashes proved the INVERSE: the installed fleet carried `origin/main`'s CURRENT
dataset; the "canonical" reference was M5's by-design-behind main checkout (235 commits, Aug-4 dataset
`a9a461b41b50`) — and the tool's own printed remedy (rebuild+reinstall from M5) would have REGRESSED
the fleet 4 days. Worse: Phase 1's own `chore(data): refresh dataset from canonical` commit (`c5f277a`)
had already consumed that stale checkout and regressed the app repo's Resources — the fleet was saved
only by the accident that the build ran on Pro, whose checkout was current. Cures: `check-fleet.sh` now
anchors on `git show origin/main:…` after a refs-only fetch (fetch failure → CANNOT-VERIFY exit 3,
never phantom drift; `--local-canonical` escape hatch documented offline-dev-only), and its "unreachable
≠ aligned" note now prints ONLY when ssh actually failed (it used to be a static string on every
mismatch). PR #3907 (MERGED): the fleet-notice pointed at the dead pre-move path
`~/Desktop/kbli-navigator-app` (the repo had moved into `logo/`), so it silently self-skipped on M5.
PR #3909 (armed `--auto`): `sync_kbli_dataset.sh` now REFUSES sync mode from a checkout with branch
`main` checked out (exit 4) — deliberately NOT an origin-anchored read: tracing the callers showed the
script is a PROPAGATOR of freshly-written local canonical edits (cure compilers write then propagate),
so an origin/main read would discard every cure at its own apply step. The implementer refuted the
orchestrator's first design with that evidence and shipped the branch-guard instead, with the
false-positive pinned by a test.

**Honest gaps — the BKPM app is NOT yet a hand-to-BKPM deliverable.**

1. Chat still talks to the OLD brain (OpenClaw `zantara-kbli` on Mini via ssh): fleet-only reachability,
   no retrieval — cold KBLI questions get "I don't have FONTI" refusals. This is Phase 2's job (below).
2. Ad-hoc signature: on a non-fleet Mac, Gatekeeper requires right-click-open; a clean external
   hand-off wants Developer ID + notarization — Zero decision, `operator[business]`, not started.
3. No human has GUI-opened the two new apps yet (bundles proven by content; native GUI QA = 30 seconds
   of Zero's eyes).

**NEXT — Phase 2 "the chat perfect on KBLI" (SUPERSEDED 2026-08-19 on the brain choice — Zero's GO arrived WITH a route change: ChatGPT Pro via `codex exec`, not OpenClaw and not chat_kbli-first; see the 2026-08-19 LIVE STATE entry + the design doc. The benchmark requirement below carries over; the rest of this block is the historical 2026-08-09 design):**
one brain only: a new `KBLIBrainClient` (Swift, URLSession) → prod `chat_kbli` (the cured brain:
canonical + 314 gold + `kbli_documents` + the exact-code retrieval fix), current code-card context
rides with the question; API key read from a LOCAL file, never bundled, chat hides gracefully where the
key is absent (a BKPM Mac); fallback chain HTTP → legacy ssh path → honest offline message; a
**~25-question KBLI benchmark** (from the 78-question team test + cured traps: 51101→49%, 79122→0%,
25200, moratorium, paid-up 2.5 mld, SLHS) run against old and new brain, scored against canonical,
before/after report in-repo. Out of scope: notarization; `kbli_documents` content (that's the
8-phantoms/25-drafts/312-rows ratification packages already on Zero's desk).

**Also open (small, Zero-gated):** Mini Desktop residue `kbli-2025-navigator/` — a Feb-2026 React
prototype (8MB, not a git repo) carrying a cleartext `GEMINI_API_KEY` in `.env.local` (superscar
family #4): trash-or-keep is asked; revoking the key in Google AI Studio is `operator[credential]`, low
urgency. (The June fossil "KBLI Navigator (nativa congelata 28-6).app" was already trashed on Zero's
order.)

**🟢 2026-08-09 — GOLD FULL-POPULATION LIVE: 314 codes (from 3 pilots), G1-G5 all innocent — but only
after G2 caught a real production bug and forced a same-day fix.** The morning attempt (314 = 322 minus
8 phantom codes, see below) applied cleanly but POST-MEASURE found **G2 violated and reproducible**: on
bare-code queries 3 of 10 sampled gold codes (56101/47721/85312) returned the GOLD point at rank1 with
the BPS twin ABSENT from the top-5. Root cause: `_get_kbli_payload_from_qdrant`'s exact-code fast-path
(`kbli_notebook.py`) scrolled Qdrant with `limit:1` and no `order_by` — with two points now sharing one
`kode_kbli`, the winner was a per-code coin-flip on the two points' unrelated deterministic UUIDs
(10/10 correlation confirmed empirically), zero relation to score/doc_type. Same-day rollback per a
pre-declared contract, then the real fix: the filter now POSITIVELY selects `doc_type==kbli_bps` instead
of excluding gold (#3863, deployed v4057, proven live in-container and on the search surface). Re-apply
then measured G1-G5 all clean, G2 15/15 including the 3 ex-violators (#3865). Open, orthogonal:
8 phantom codes in `kbli-gold-content.ts` with no 2025 counterpart (excluded from this apply,
re-keying decision is `operator[business]`), and the `sektor`/`section` payload field remains unreliable
(unscoped, tracked separately).

**🟢 2026-08-08 (late evening) — THE INDEXERS CAN NOW RUN WHERE THEIR CREDENTIALS LIVE, AND THE FIRST
THREE GOLD EDITORIAL POINTS EXIST.** Three PRs, each forced by proving the previous one: #3823
(marker-walk root resolution + the three data files INTO the image — which took two build-context
rounds of its own), #3832 (the gold indexer was BORN broken: a nested `metadata` write against the
flat payload, in the file's birth commit — it had never completed a single run, so `doc_type=kbli_gold`
was 0 points, measured), #3839 (the SAME disease in the stats/sample blocks it had never reached — four
more sites, swept to a true grep-zero). Applied inside Fly: canonical reindex
`--only 64995,64210,49296,46415,46496` (5/5 upserted, collection steady at 1559) and gold
`--only 64995,64210,49296` (the first 3 gold points ever). PROVEN by content, three independent
instruments: the deployed canonical's 64995 carries the honest no-predecessor sentence;
`kbli_qdrant_pma_sync --layer whatchanged` dry-run in-container reports **5/5 "already agrees with
canonical"**; `search_kbli` on an editorial query ("IDXCarbon…") returns the GOLD point FIRST (0.666 vs
0.546 for its BPS twin) with the Quick Answer visible. Characterized, no action needed: on a code
carrying both points the sync tool REFUSES the gold one ("carries no 'whatchanged' block — REFUSING to
rewrite prose we cannot locate") — the refusal semantics were already right.
**Deliberately NOT done: the other 319 gold entries.** Populating the whole class changes retrieval
semantics for every consumer of `kbli_2025_final_hybrid` — that is its own ledgered decision with its
own verification pass, not a night's slip-in.
Lessons paid for (bodies in the PRs): the root `.dockerignore` is a WHITELIST — a new COPY's source
must be re-included or the production image stops building, and the non-required Snyk build gate is
what caught it pre-merge; `source_documents` at repo root is a TRACKED SYMLINK Docker COPY does not
follow — COPY from the real `data/source_documents/` path; a script that exists but never ran can be
broken in TWO phases, and a fix that stops at the first crash site is half a fix (W101 symmetry — the
class census found 4 more sites, and the census probe itself first under-matched on quote style, W107).

**🟢 2026-08-08 — PENDING-ARMS "4 contradicted-predecessor adjudications" (2026-07-25) CLOSED: 2 of 4
CONFIRMED and live on every surface, 2 stay genuinely disputed BY DESIGN. Merged as #3778
(`58a3d01e28`), Vercel promote HTTP 201, proven live by content on `/kbli/49296` (49424) and
`/kbli/64210` (64200).** The 2026-07-25 line asked to
"adjudicate which layer holds the true 2020 origin for each of the 4" (`46415`/`46496`/`49296`/`64210`).
Re-measured against the FULL BPS 2020-to-2025 crosswalk relation file
(`data/kbli-filiera/phase0/bps_crosswalk.json::relation`, all 1,559 codes) instead of canonical's own
`bps_2020_ancestors` field, which PR #3082's populate step only ever wrote for OSS-native codes
(`_l2_status is null`) — `49296` and `64210` have `_l2_status: "no_oss_risk"`, so their corroboration
was invisible to any probe reading only the canonical field.

- **`49296` → CONFIRMED to `49424`.** PP 28/2025 lampiran (100% title match) AND the official BPS
  crosswalk table (Lampiran 10, printed page 386) both name `49424` — two structurally independent
  sources agreeing by membership, same standard as the Lampiran III cross-instrument check
  (2026-08-02, §F2). Canonical + gold `whatChanged` rewritten to a cited confirmed sentence.
- **`64210` → CONFIRMED to `64200`.** Same pattern, BPS Lampiran 10 printed page 398, 95% title
  match. Canonical + gold rewritten.
- **`46415`/`46496` → STAY UNCONFIRMED, correctly.** The two sources genuinely disagree on both
  (e.g. `46415`: pp28/`kbli_2020_source` says `46694`, BPS says `46419`) — picking a winner here is
  the exact disease this lane exists to cure (per the original line's own text). No canonical change.
- **Separate defect found and fixed while investigating `46496`:** gold's `whatChanged` used a
  different sentence template ("Previous code(s): NNNNN") that the original `_NAMED_PREDECESSOR`
  regex (anchored to "KBLI 2020: NNNNN") never scanned — a guard UNDER-match (superscar #3/W82
  family). Gold (which WINS over canonical on the rendered page —
  `kbli-data.server.ts::transformCode`) kept serving a false-confident, uncited predecessor claim
  that canonical had already honestly disclaimed. Realigned gold to canonical's exact honest text.

New compiler `scripts/kbli_filiera/cure_whatchanged_corroborated_predecessor.py` (spec-driven,
facts-basis-guarded — re-derives the corroboration premise from live data before writing, refuses on
drift; 14 tests). Applied to canonical + gold + the 3 synced consumer copies + the
`kbli-dataset-version.json` sidecar sha256.

**KG APPLIED AND PROVEN 2026-08-08, post-merge:** `kg_whatchanged_cure.py` run inside the Fly image
with the spec pinned to the merge SHA (`58a3d01e28`) — dry-run AND apply both reported
`already_cured=2 drift=0`: the two nodes ALREADY carried the cured text (an earlier apply had landed;
both rows hold the `_whatChanged_cure` archive key, which only a real `--apply` writes), so this apply
was an idempotent no-op. Verified by INDEPENDENT read-only SQL on prod, not by the script's report:
`kbli:49296` / `kbli:64210` `properties.whatChanged` equal the spec text verbatim (49424 / page 386,
64200 / page 398). Qdrant `kbli_2025_final` and `kbli_documents` (`chat_kbli`) were checked and do
**NOT** carry this specific false claim for any of the 4 codes — verified via read-only Postgres MCP
query, no action needed there. Also fixed while in the file: the badge visible-caption defect
(`BaliStatusBadge` hover-only `reason` text, invisible on mobile/touch) — client-facing, merged with
#3778, the caption is live.

**🟢 2026-08-06 — THE BOT/MCP HALF IS SHIPPED, SYNCED AND PROVEN LIVE (#3648, `b5dd5f37ca`). Both
web surfaces were already live (#3645/#3646); this closes the third.** Every step measured, none
inferred: deploy `success` → the code proven INSIDE the running container (`grep -c
licensing_disclosure /app/backend/app/routers/kbli_notebook.py` = 2, cache key `kbli_inspect_v3`) →
`kg_kbli_resync.py --apply` → verified by INDEPENDENT SQL on prod rather than by the script's own
report: `properties.pp28_sources` **0 → 1,384** KBLI nodes, **390 inherited**.

Reconciliation that holds, which is what makes it a proof: 1,419 updated + 139 unchanged + 1 missing
(`01122`, declared) = 1,559 canonical codes; and 1,384 = 390 inherited + 994 self-sourced. The 390 was
derived twice by different routes — Python over `KBLI_2025_FINAL_CLEAN.json`, and SQL over `kg_nodes`
— and agreed.

Live payloads, read off prod:

- `inspect_kbli 62110` → `licensing_content_inherited_from` `["62011","62019","62015","62013","62012"]`
  plus the note naming them.
- `56101` (8 licences rendered) and `01111` (6) → **both fields `null`**. Innocence for the RIGHT
  reason: each renders licences, so the silence is the self-sourced verdict, not an empty-list side
  effect.

**Fleet reach measured on the KG after the sync: 390 inherited → 305 get the note, 85 render zero
licences and are correctly silent.** Say 305, never 390 —
[[lesson_a_cures_own_count_is_not_the_count_of_rows_that_gained_the_thing_2026_08_05]].

**THE PROPAGATION FACT THAT MAKES THIS DIFFERENT FROM THE PMA CURE, and the trap it avoids:**
`inspect_kbli` reads `pma_status` from **Qdrant first** and `kg_nodes` only as a fallback — which is
why `kg_kbli_resync.py` was a no-op on that field and the twenty perpres codes needed
`kbli_qdrant_pma_sync.py`. `pp28_sources` is NOT on that path: it is read from `props`, bound from
`SELECT * FROM kg_nodes WHERE entity_id = $1`. **Verified in the router before running the apply**,
because the same-shaped sync had already been a wasted write once on this lane.

**NEVER query `inspect_kbli` between a deploy and its data sync.** The version bump evicts at deploy,
so any call in that window writes a fresh entry WITHOUT the cure and hides it for the 30-day TTL.
This proof was taken with no such call in between.

**What that live call also exposed, and it is the case for #3650 (open):** `62110` VIDEO GAME
DEVELOPMENT is served `Izin Produksi Alat Peralatan Pertahanan dan Keamanan`, `Izin Industri
Pertahanan`, `Sertifikat Persetujuan Kelaikan Fasilitas Produksi Pertahanan`, the placeholder `Izin
Usaha`, and a truncated `NIB dan`. The note now warns the client; #3650 removes the placeholder.
An independent review of #3650 returned DEFECTIVE, and **verifying its objection is what found the
bigger defect**: 0 live permit-typed nodes open with a meN- verb outside the enumerated 23 (its
counterexample was constructed), but **97 nodes on 62 codes carry `kewajiban` as an id token while
`entity_type` files them as permits** — noun-phrase duties (`Laporan Penomoran Telekomunikasi`) that
no verb list can catch. Innocence measured before shipping: 0 of those 97 carry a permit-shaped name.

**🔴🟡 2026-08-05 — WE TELL A VIDEO-GAME STUDIO IT NEEDS THREE DEFENCE-INDUSTRY LICENCES, AND CANONICAL
IS WHERE IT COMES FROM: 62110 INHERITED ITS PP 28 LICENSING FROM FIVE OTHER CODES.** Read this section
to the CORRECTION at its end — the first verdict here (a refusal built on one canonical field) was
wrong within the hour, and the corrected finding is the larger one.

This closes the declared gap left open by #3625 ("the 11,245 node-silent edges are untouched and still
wrong in places") with a NUMBER and a NO, not with a fix.

**The harm, proven on the live endpoint, not inferred.** `inspect_kbli 62110` (VIDEO GAME DEVELOPMENT)
returns six licences whose `requirements` is `[]`, and three of them are defence permits: `Izin Produksi
Alat Peralatan Pertahanan dan Keamanan`, `Sertifikat Persetujuan Kelaikan Fasilitas Produksi Pertahanan`,
`Izin Industri Pertahanan`. A fourth is `Penyelenggara Sistem Elektronik Lingkup Privat`. The
canonical-backed obligations cure could not touch them **by construction**: a target that states no
obligation has nothing to compare against canonical, so it is KEPT.

**Provenance names the mechanism and does not separate right from wrong.** All five non-OSS-tier targets
on 62110 carry one and the same `source_chunk_ids` entry, `2933b2b9-4853-53ad-ab23-e630571011aa`, and
that chunk produced REQUIRES edges for **exactly one** KBLI code — 62110. So the error is one bad
extraction, not a shared over-linked node like the four agricultural ones; there is no "this node is
attached to 888 codes" signal to key on. The chunk text itself is a Qdrant point id and is not
resolvable from Postgres — a pointer, not evidence (W65).

**The population, measured this turn.** REQUIRES edges out of `kbli:%` whose target is a PERMIT type
(`classify_requires_target` → `license`: `perizinan`, `izin_usaha`, `license`, `nib`, `permit_type`,
`penetapan`) **and** states no obligations: **3,222** (code, target) pairs. By entity type —
`izin_usaha` 1,935 rows / 647 codes / 506 distinct targets · `license` 1,167 / 967 / 4 · `nib` 100 ·
`penetapan` 10 · `permit_type` 9 · `perizinan` 2.

**THE TEMPTING PREDICATE, AND WHY IT IS REFUSED** — ⚠️ **read the CORRECTION below before using any
number in this paragraph: it was measured against one canonical field and the missing one changes the
diagnosis.** The obligations cure compares the target's
`kewajiban` against canonical's; the obvious sequel compares the target's NAME against canonical's
`perizinan` for the same code. Measured over all 3,222: **NO_OVERLAP 1,925** (624 codes, 495 names) ·
SUBPHRASE_OF_CANONICAL 634 · EXACT 614 · CANONICAL_SILENT 38 · CODE_ABSENT 9 · CANONICAL_INSIDE_NAME 2.

Read the 1,925 and the cure dies: its biggest members are `Sertifikat Tingkat Komponen Dalam Negeri`
(172 codes), `Surat Persetujuan Penilaian TKDN Penggunaan Mesin Produksi Dalam Negeri` (103), `UMKU`
(83), `Izin Edar Pangan Olahan` (38), the CPPOB and PMR food-safety permits (~90 between them), the
medical-device `Izin Edar` family. **Those are real permits the businesses really need.** Canonical's
`perizinan` states the **OSS main tier only** — `NIB dan Sertifikat Standar` and its siblings — while
the graph's `izin_usaha` targets are overwhelmingly the **UMKU sub-licence layer**. The two vocabularies
describe DIFFERENT LAYERS of licensing, so absence from one is not denial by the other, and a name
comparison reads "contradicted" on the whole second layer.

> **The predicate that worked for obligations does not transfer to names, and the reason is structural,
> not a tuning problem.** Same shape as the 1,341 duplicate `BELONGS_TO` rows: the cure that looks
> obvious would have quietly destroyed data while wearing the shape of a fix.

**🔴 CORRECTED ONE HOUR AFTER MERGING IT — WE DO HOLD THE UMKU LAYER, AND THE DEFENCE PERMITS ARE IN
CANONICAL.** The paragraph above shipped in #3643 saying the UMKU layer was absent from canonical and
that a per-code adjudication would need a source "which we do not hold". **Both halves are false**, and
they were false because the refusal enumerated ONE canonical field. `per_skala_legacy[].pb_umku` is the
UMKU layer: **930 codes, 1,316 entries, 645 distinct values**, and its vocabulary is exactly the one the
refusal called "contradicted" — `Sertifikat Tingkat Komponen Dalam Negeri`, the TKDN machine approval,
`Sertifikat Laik Sehat`, `Pelepasan Varietas Tanaman Perkebunan`.

Re-measured with the reference it should have used from the start (`perizinan` ∪ `pb_umku`, both
`per_skala` and `per_skala_legacy`, bulleted cells split): **EXACT 1,358 · SUBPHRASE 817 ·
CANONICAL_INSIDE_NAME 29 · NO_OVERLAP 971** (497 codes, 328 names) · CANONICAL_SILENT 38 · CODE_ABSENT 9. The graph mirrors canonical far more closely than the first pass could see.

**And that flips the diagnosis of the 62110 case entirely.** Canonical's own record for VIDEO GAME
DEVELOPMENT carries, verbatim in `per_skala_legacy[2].pb_umku`:

> `- Pendaftaran Penyelenggara Sistem Elektronik Lingkup Privat (dalam hal memiliki sistem elektronik
yang dipergunakan) - Izin Penetapan Indust ri Pertahanan - Sertifikat Persetujuan Kelaik an Fasilitas
Produ ksi Pertahanan … - Izin Produksi Alat Peralatan Pertahanan dan Keamanan`

So the KG is **faithfully reproducing canonical**, not inventing. #3625's "CANONICAL IS CLEAN — this is
an EDGE defect" holds for the agricultural OBLIGATIONS and **does not generalise to this class**. (The
mid-word spaces — `Indust ri`, `Kelaik an`, `Produ ksi` — are the PDF text-layer damage this lane has
met before; the text is a bad extraction, not a bad transcription by us.)

**THE MECHANISM IS RECORDED IN THE DATA AND NOTHING SURFACES IT.** `62110.pp28_sources` is
`["62011", "62019", "62015", "62013", "62012"]`: 62110 is a NEW 2025 code with no PP 28/2021 row of its
own, so its licensing was filled from its KBLI-2020 ancestors — computer-programming codes. Measured
across the file: **390 of 1,559 codes carry `pp28_sources` naming ONLY OTHER codes** (plus 88 that mix
own + others, 906 that are self-sourced, 175 empty), and **217 of those 390 inherit a `pb_umku` permit
that belongs to a different code**. The ancestry itself can be wrong — `02101 Pengelolaan Hutan` (forest
management) is sourced from `['63111']` (data processing / hosting).

**This is the north star's own words made measurable**: _"zero silent cross-vintage fill anywhere in the
catalog"_. The fill is not silent in the data — `pp28_sources` is a complete audit trail — it is silent
on the SURFACES. A client reading `/kbli/62110` or asking the bot is told it needs a defence-production
permit, with nothing saying that requirement was inherited from a different code.

**WHAT WOULD ACTUALLY CLOSE IT** (not built): DISCLOSURE, not deletion. A permit whose only support is
an INHERITED `pp28_sources` entry should say so — same family as the `[… cut off in the official
source]` label, and derivable from a field we already carry on every record, with no new government
source needed. Deletion stays refused for the original reason, which survives correction: the layers are
real and most of these permits are real.

**✅ THE WEB HALF IS SHIPPED, DEPLOYED AND PROVEN LIVE (#3645, merge `9a0a8e8adc`).** The disclosure is
split across two surfaces on purpose, because the same fact has opposite correct answers on each:

- **Indexed `<meta>` goes SILENT on the licence type** — a `<title>` has no room for a qualifier.
  `verifiedLicenseType` now also requires `contentInheritedFrom == null`; `verifiedRiskLabel` is
  **untouched**, because the risk tier on these codes IS 2025-native. One flag for both would have
  suppressed a true fact to qualify a different one. `kbliMetaDescription` also had
  `risk && license ? … : null`, which dropped BOTH when only the licence was ungated — it now falls
  back to the risk sentence alone.
- **The page body KEEPS the licence and names the source** (#3646) — a body has room to qualify, so
  going silent there would destroy true information instead of framing it.

**PROVEN by a before/after captured on prod, not by inference.** Before (commit `0f6f3e67f3`) and after
(`9a0a8e8adc`, which is #3645's own merge commit):

| code                 | inherited?                | before                                      | after              |
| -------------------- | ------------------------- | ------------------------------------------- | ------------------ |
| `62110` video games  | **yes**, from 5 codes     | `Medium-Low risk, license: NIB + Sert. St.` | `Medium-Low risk.` |
| `56101` restaurant   | no (own code in the list) | `… license: NIB + Sert. St.`                | **unchanged**      |
| `01111` corn farming | no                        | `… license: NIB + Sert. St.`                | **unchanged**      |

Two innocence controls and one guilt, all three read on the live site. The risk tier survives on
`62110` — that is the asymmetry working.

**The gate binds on 336, not 337.** A raw `_l2_source === "OSS_RBA_resiko_2025"` count gives 337;
`49213` (Angkutan Perkotaan) carries a `per_skala_disputed_pp28_collision` block, so `deriveProvenance`
resolves it to `detached` before it can reach `oss_native`. My own first count said 337 — it measured
the MARKER, the test pins the GATE. Same shape as every other probe lesson in this file.

**🟡 `inspect_kbli` IS THE REMAINING SURFACE, and its blocker is measured rather than guessed.** It
renders the inherited `pb_umku` permits as licences to the bot and the MCP. Two facts bound the fix:
the backend Dockerfile copies `backend` / `scripts` / `training-data` / `*.py` but **not `data/`**, so
the router cannot read canonical from disk; and `kg_nodes` for `kbli:62110` and `kbli:56101` carry
**no `pp28_sources` property at all**. So the path is a sync that writes the field onto the nodes — the
pattern `kg_kbli_resync.py` already uses for `pma_status` — applied from Pro. NOT a second derived copy
inside the backend: that is a HOME-fork by construction (superscar #1) and would drift from canonical
silently.

**Left standing from the refusal, because it is still true**: comparing a licence name against
`perizinan` ALONE reads "contradicted" across the whole UMKU layer, and what remains at NO_OVERLAP after
the union is dominated by **mis-typed nodes rather than wrong permits** — `Izin Usaha` (174 codes), bare
`UMKU` (81), `Badan Hukum` (16), `Perizinan Berusaha` (8), and sentences that are obligations or table
headings carrying `entity_type='izin_usaha'`: `Menjamin mutu yang dihasilkan sesuai standar`, `Layanan
keluhan pelanggan`, `Kewajiban Pelaku Usaha`, `Lokasi industri berada pada Provinsi bersangkutan`. Those
are rendered to clients as licences to obtain. Named here, not cured here.

**THE FIELD TRAP THAT BIT TWICE IN ONE NIGHT — read this before writing any canonical licence probe.**
`per_skala[].perizinan` is populated on **6 of 1,559 codes** (17 of 9,095 scale entries).
`per_skala_legacy[].perizinan` is populated on **1,254**. **299** codes state no licence name anywhere.
`kewajiban` lives on `per_skala`; `perizinan` effectively lives on `per_skala_legacy` — the same split
that made #3639's first description false. A first pass of the measurement above read only `per_skala`
and reported **3,206 of 3,222** edges as CANONICAL_SILENT: a clean, believable "there is nothing here to
cure", manufactured entirely by looking at the wrong field. It was caught only because 3,206/3,222 is
too tidy to be true — the same reflex as the zero in #3642's before-state.

**Smaller, unambiguous, and NOT cured here** (measured, ledgered): `NOT_APPLICABLE_OSS` (50 codes) and
`PENDING_REGULATION` (10) are `licensing_status` ENUM VALUES materialised as `kg_nodes` and
REQUIRES-linked to the codes that carry them. They land in `related_requirements.systems`, so
`inspect_kbli 84111` returns `licensing_status: "NOT_APPLICABLE_OSS"` and, one field below,
`related_requirements: {"systems": ["NOT_APPLICABLE_OSS"]}` — the same fact twice, once as a status and
once as a "related requirement". Noise rather than a false claim, and `related_requirements` has **zero
consumers outside the router** (grepped repo-wide: producer in `kbli_notebook.py`, and this file) — so
it reaches a reader only as a field of the `inspect_kbli` response, never through a rendered web page.
Low harm, hence ledgered rather than shipped. It does not overturn the audit two sections below: that
verdict is that no OBLIGATION TEXT travels through this field and that the classifier's drift is
fail-safe, and both still hold.

**🟢 2026-08-05 — THE OBLIGATIONS BLOCK IS LIVE ON `chat_kbli`, AND THE THREE NUMBERS IT PRODUCED ARE
ALL RIGHT.** `kbli_documents_cure.py --all-machine-template --apply` ran from the deployed image:
**299** rows selected by the recogniser, **170** rewritten, **129** already byte-identical (all with
`per_skala = 0` — an honest no-op, verified per code before the apply), and **87** rows now carry a
`## Kewajiban` block — exactly the subset of the 170 for which canonical states any obligation. Before
this, `count(*) FILTER (WHERE content ILIKE '%## Kewajiban%')` on the live table was **0 of 1,563**.

- **PROVE-LIVE on the whole consumer map, which is one reader.** `grep`ping the repo for
  `kbli_documents` outside tests/scripts returns exactly one file — `kbli_notebook_chat.py`, i.e.
  `chat_kbli` (the `apps/mouth` TS hit is a comment, not a query). Asked about `25200` obligations,
  the bot now answers grouped **by scale**: Mikro/Kecil get the industry-data + safety + MSDS set,
  Menengah adds the disaster-evacuation SOP, Besar adds ISO 9001 — the exact per-scale shape
  `build_kewajiban_section` emits. Positive control with the shared mechanism: all five tokens it
  printed (`ISO 9001`, `SOP evakuasi bencana`, `Lembar Data Keselamatan Bahan`, `Menengah (Seluruh)`,
  `Besar (Seluruh)`) were read back out of the DB row before crediting the channel with reading it.
- **The 1,260 refused rows keep hand-written prose and this is BY DESIGN** — closing them needs prose
  re-authored around the new rows (Legge 5), not a script. The refusal is declared in the apply log.
- **CORRECTION to a note written before this ran:** `96230` was named as the code that would surface
  _"Sertifikat Laik Sehat"_. It did not, and the cure is fine — `96230` is a hand-written editorial
  row (`KBLI 96230: … WHAT IT MEANS:`), refused by the recogniser, never in the 299. A PROVE-LIVE
  exemplar must be picked FROM the apply log, never from memory of "a code that has this fact":
  [[lesson_a_cures_own_count_is_not_the_count_of_rows_that_gained_the_thing_2026_08_05]].

**🟢 2026-08-05 — WE TOLD AN UMRAH TRAVEL AGENCY TO CLEAR PLANTATION LAND, ON A PUBLIC PAGE. CURED,
APPLIED AND PROVEN LIVE.** PR #3625 merged (`4410bd48`); the apply ran from Pro at 16:57 WITA:
**1,711 edge ROWS deleted across 1,707 pairs on 1,029 codes, 0 refusals, RC=0.**
`kbli_notebook.py:466` renders each REQUIRES-edge target's `properties.kewajiban` verbatim as the
code's `requirements`.

- **IT WAS NEVER "FOUR BAD NODES" — that is how it was FOUND.** The deletable set spans **563 distinct
  target nodes**; the four named ones (`0bf540b11cf6`, `55be853cd247`, `c7cd8d6c86e5`, `41a60205c6c0`)
  are **1,116 of 1,707 = 65%**, leaving 591 over 559 other targets. A cure written against the four
  names would have left a third of the lie standing. (An earlier note here said 1,118; measured: 1,116.)
- **THE SECOND CONSUMER, missing from this corner until now — write it down or it gets left out
  again.** `balizero.com/kbli-explorer` calls the same endpoint and prints these lines under the
  heading **"What you need to do:"**, `.slice(0, 3)` — so a client saw exactly the three wrong ones.
  Proven by searching **all 31** chunks the served page references (no sampling): only
  `app/kbli-explorer/page-76f6af2d1b5d8ba9.js` carries both the heading and `kbli-notebook/inspect`,
  and the bundle's host is `https://nuzantara-rag.fly.dev` — the backend the cure landed on. The
  remaining readers (`/kbli/<code>` SEO pages, apps/kbli-navigator, `KBLIEye`) read the static
  canonical JSON, a DIFFERENT store, and were never affected. `chat_kbli` has **zero** occurrences of
  `kewajiban|persyaratan|REQUIRES`.
- **PROVE-LIVE, anonymous, with positive controls sharing the mechanism** (HTTP 200 = what the public
  page gets): on `79122` and `62110`, `pembukaan lahan tanpa bakar` / `good agriculture practices` /
  `Menteri Pertanian` / `"skala"` are all **0**, while `Pembimbing Ibadah` (79122) and `konten SARA`
  (62110) are still **1** — the zeros are real, not an empty response.
- **Population proof, not two exemplars:** the four nodes went from **979 KBLI codes to 9**. Eight of
  the nine are genuinely agricultural (corn, sugarcane, coconut, oil palm, tea, beverage crops,
  rubber, tobacco curing) and SHOULD carry them.
- **The ninth is the whole refusal class, and it is one code.** Both `CANNOT_JUDGE_CANONICAL_SILENT`
  verdicts sit on **`91300`** (cultural-heritage restoration): its canonical row exists with
  `per_skala = 0`, so the predicate cannot prove the agricultural edge wrong and KEEPS it — "absence
  of a statement is not a denial". Visibly wrong to a human, unprovable by the rule: named residue,
  not a miss. Closing it means giving 91300 canonical obligations.
- **DECLARED GAP, measured not assumed:** the **11,245 node-silent** edges are untouched and DO
  contain real errors — `62110` (video games) is still REQUIRES-linked to `Izin Industri Pertahanan`
  and a defence-production permit. Those targets state no obligations, so this predicate is blind to
  them by construction. That is a separate lane, not a follow-up of this one.
- Arithmetic reconciles end to end: 15,030 pairs + 25 duplicate rows = 15,055 rows; −1,711 = **13,344**
  measured after. **1,029 kg_nodes carry `_disputed_requires_obligations`** — one per acted code, so
  nothing was deleted without an archive; per-code transaction, archive and delete land together.
- **The innocence is per code, not per node** — 79122 lost land-clearing and KEPT its pilgrimage
  duties (5 edges remain). `kg_kbli_license_fix.py` cannot do this: its verdict is whole-code.
- A cross-family refuter returned **DEFECTIVE** with four real findings (undecoded HTML entities = a
  latent false-DELETE; a non-list `kewajiban` iterated character by character; "never silent-delete"
  not binding when there is no node to archive on; a tautological wiring pin). All fixed; 34 tests,
  mutation 10/10; scope unchanged at 1,707.
- **Cache:** 7 chunks of ≤150 over all 1,029 codes — **5 entries found, 5 evicted, 0 survived**. The
  `0/150` on chunk 1 is a TRUE zero: the positive control showed the tool still sees
  `kbli_inspect_v2_79122`/`_62110`. The cache is sparse — only inspected codes have entries.
- **GOTCHA paid here:** on Pro the fly credential in `~/.nuzantara-secrets.env` is **unauthorized**
  and `~/.fly/config.yml` is the live one — the **inverse** of the 2026-07-26 W106 reading. Probe by
  doing the work (`machines list`), never `auth whoami`, and never hardcode which side wins.

**🟢 2026-08-05 — TWO MORE DEFECTS ON THE SAME ENDPOINT, BOTH SHIPPED AND PROVEN LIVE.** Reading
`kbli_notebook.py` to cure the edges above surfaced two independent lies in what it returns. Neither
was found by a report: both by asking "what does this field say when the data is EMPTY?".

- **#3634 — `Licenses: None` was an ASSERTION built out of a data gap** (merged `55548f24`,
  PROMOTED, proven in the served chunk). The `kbli-explorer` copy button built
  `licenses.map(l=>l.type).join(", ") || "None"`. Unlike text on a page this line **travels** —
  clients paste it into emails and quotes, where no on-screen caveat follows. Measured: **284 of
  1,559** codes render `licenses: []` and canonical states obligations for **125** of them; sharpest
  is **`07101` iron-sand mining**, which the SAME response flags `REGULATED` / risk `Tinggi` while
  the copied line read `Licenses: None`. Live `licensing_status`: `REGULATED` 1,266 ·
  `PENDING_REGULATION` 217 · `NOT_APPLICABLE_OSS` 75 · null 6 · `NOT_IN_KBLI_2025` 4 — **only
  `NOT_APPLICABLE_OSS` genuinely means no OSS licence is required**, the rest mean we hold no rows.
  Cure is a pure resolver (`apps/mouth/src/lib/kbli-licence-summary.ts`) with guilt+innocence tests,
  so the two labels are one decision instead of a ternary inline in a click handler.
- **#3635 — `related_codes` showed each sibling twice, and the limit paid for it** (merged
  `10060600`, deployed 11:59:58Z, proven live). The KG holds **1,341 duplicated `(source, sector)`
  `BELONGS_TO` rows** — histogram exactly `{2: 1341}`, every duplicated pair twice, never three
  times. `LIMIT 6` ran BEFORE any dedup, so `79122` returned `['79110','79110','79121','79121']`:
  six rows spent on two codes. After the cure (DISTINCT + self-exclusion in SQL, plus
  `related_codes_from_rows` as an independent second line): `79122` → six distinct siblings,
  `56101` → six. **The 1,341 duplicate ROWS are deliberately still there** — `BELONGS_TO` is shared
  with CRM and joined pairwise by `mediated_edges_builder`, so a data-level dedup needs its own
  blast-radius analysis. Curing the READER first was the reversible half.

**MEASURED LIMITS OF THIS ENDPOINT — declared, deliberately NOT "fixed", each with its number.**
Every one of these was a candidate cure that the measurement talked me out of:

- **Why the 11,245 node-silent edges are not curable with data we hold** (the gap the KG block
  above declares): the predicate would need licence TYPES, and canonical names one in **6 of 1,559**
  rows. A full scan of the Qdrant OSS collection — **10,825 of 10,825 points, no sampling** — yields
  **160** (1.5%). **58** codes carry a defence permit; sorting those is per-code legal judgment
  (Legge 5), not a script. So `62110` video games stays REQUIRES-linked to `Izin Industri
Pertahanan` until someone rules on it, and saying so is more honest than a heuristic.
- **222 codes render `sector: "N/A"` and `related_codes: []`** — no `BELONGS_TO` edge at all.
  Canonical can place **42** of them, and **all 42 are multi-sector** — there are exactly 42
  multi-sector codes in the whole corpus, so the KG builder skipped every code it could not assign
  to ONE sector. `"N/A"` asserts nothing false; inventing one sector for a two-sector code would be
  the plausible-but-wrong assertion. **Field-name trap paid here:** asking canonical for `sektor_id`
  / `sektor` gives "5 of 222"; the real key is **`sektors`** (plural, a list) and gives 42.
- **877 `kewajiban` strings end in a bare dangling conjunction** across ~169 codes
  (`"Melaporkan ikan hasil tangkapan dan"`), and `62110` carries a licence literally named
  `"NIB dan"`. Split from the 127 that are legitimate Indonesian list style (`"…; dan"` = item N).
  **NOT trimmed:** dropping `dan` yields a grammatical sentence that **understates a legal duty** —
  the dangling word at least signals incompleteness. The real fix is re-extraction from PP 28/2021.
- **`_resolve_risk_profile` falls back to `licenses[0].risk_level` with no `ORDER BY`** — a latent
  fragility, not a live defect: **218** codes lack a Qdrant risk (159 have no licence edges at all,
  59 have edges that all AGREE, **0 disagree**). Self-audit of the edge cure's blast radius:
  **0 of the 218** were touched.

**Method note that outlived both fixes:** the post-promote PROVE-LIVE for #3634 returned a
believable **zero across all 31 chunks** — the edge was serving cached pre-promote HTML pointing at
the OLD chunk hash. Twenty seconds later the hash had moved and both labels were there. **Compare
the chunk hash before believing a post-deploy zero**, and always run a positive control.

**THE ENDPOINT IS NOW SWEPT FIELD BY FIELD — every one of `KBLIDetail`'s twelve has a number.** Both
cures above were found by asking one question of one field ("what does this say when the data is
EMPTY?"), which is a reason to ask it of ALL of them rather than stop at the two that bit. Enumerated
from the response model, not from a sample of responses — the field you did not enumerate is where
the lie survives.

| field                        | state                                            | number                                                                           |
| ---------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------- |
| `code`/`title`/`description` | identity                                         | —                                                                                |
| `pma_status`                 | cured (perpres caps, earlier lanes)              | 20 patched, 14 deliberately unadjudicated                                        |
| `licensing_status`           | enumerated                                       | REGULATED 1,266 · PENDING 217 · `NOT_APPLICABLE_OSS` 75 · null 6 · not-in-2025 4 |
| `sector`                     | honest gap                                       | 222 `"N/A"`; the 42 placeable are the 42 multi-sector codes                      |
| `risk_profile`               | latent fragility, ledgered                       | 218 without Qdrant risk; **0** with disagreeing licences                         |
| `licenses`                   | **cured** #3625 (obligations) + #3634 (gap≠None) | 1,707 pairs detached · 284 empty lists relabelled                                |
| `related_requirements`       | **audited — no obligation text leaks**           | see below; one noise finding added 2026-08-05 (status enums in `systems`)        |
| `related_codes`              | **cured** #3635                                  | 1,341 duplicate rows collapsed at the reader                                     |
| `expert_legal`               | universally absent                               | **0 of 1,568** kbli nodes carry it — always `null`, asserts nothing              |

**`related_requirements` got the closest look and came back clean, which is worth recording as
loudly as a defect** — it renders the SAME REQUIRES edges the cure above deleted from, so it was the
obvious place for the lie to have a second door. It does not: it renders target NAMES only, never
their `kewajiban`, so no obligation text travels through it. And `kbli_requires_kind.py` carries the
W106 signature in its own docstring — _"this classification was derived from a census, and a census
is a snapshot"_ — with nothing re-measuring it, so it was re-measured here:

- **35 distinct target entity types reach that list today; the classifier knows 30.** The census HAS
  drifted — 6 types have appeared since: `fasilitas`, `pekerja`, `kbli`, `entity`, `parameter`,
  `jabatan`, totalling **16 edge rows** over 8 target names.
- **The fail-safe direction held, and that is the finding.** All 8 are things a business _is_ or
  _has_ — a port facility, ship crew (`Awak Kapal`), a Regent's office (`Bupati/Walikota`), an R&D
  activity, a consumer-complaint service, `UMKM`. **Not one is a permit that got demoted to
  `other`**, which is the only drift that would cost a client something (a licence they are never
  shown). A missing badge on 16 edges is the acceptable failure the module designed for.
- Mapped-but-unused: `pasal` has a bucket and **0** live rows. Harmless; noted so a future reader
  does not read its absence as a bug.

**🟢 2026-08-05 — "MELAPORKAN IKAN HASIL TANGKAPAN DAN". THE SENTENCE STOPS THERE, AND EVERY SURFACE
PRINTED IT LIKE A COMPLETE INSTRUCTION.** #3637 merged (`a532487e`), deployed and PROVEN LIVE.
1,714 legal duties end mid-sentence; one is literally `". Produk yang"`.

- **This entry exists because a note in this corner was WRONG, and it is the most reusable thing
  here.** The earlier note said _"877 obligations end mid-sentence — deliberately NOT fixed, because
  trimming understates a legal duty."_ The reasoning is right and still stands, but it only rules out
  **trimming**. It said nothing about the client, who was reading a cut-off duty as a complete one.
  **A ruling about one remedy is not a ruling about the defect.** Same shape as `Licenses: None`: a
  gap rendered as an assertion. The cure LABELS and never alters — `describeObligation` returns the
  source text byte-identical, and a mutant that trims is killed by test.
- **And the count was wrong because it looked at ONE FIELD:** `kewajiban` **1,241** over 229 codes
  **plus `persyaratan` 473** over 92 = **1,714**, not 877. On the graph the endpoint reads: **234**
  rows over 104 codes, 39 distinct strings, the widest sitting on **35** codes.
- **FOUR render sites.** Beyond the two obvious ones, BOTH halves of `LicensingSection.tsx` (the
  static `/kbli/<code>` pages), which carry the larger population. **Naming trap, the third of the
  night** (after `sektors` and `kode_kbli_2025`): the ENDPOINT's `requirements` is fed from
  `kewajiban`, the STATIC page's `requirements` is `persyaratan`. Same word, different fields.
- **The word list is DATA-DERIVED.** A first draft guarded eight further prepositions; measured
  against both stores each matched **zero**. Kept: `dan`/`atau`/`yang`/`di`, word-boundary anchored —
  a substring match would falsely flag **17 complete duties**, sharpest being the Hajj obligations
  ending **"ke Arab Saudi"** on `79122`. That is now an innocence test.
- **THE LANE IS BOUNDED, and the boundary is the useful part.** Asking the same question of every
  other text field, both stores: `judul` **0** · `uraian` **0** · `pma_nota`/`pma_kondisi` **0** ·
  kg_nodes titles+descriptions **0**. **The truncation lives entirely in the PP 28/2021 + OSS
  extraction and never in the BPS classification data** — that is where a re-extraction must aim, and
  why the visible page headings were never wrong.
- **PROVE-LIVE, and the correspondence is exact — label count == truncated count on every page:**
  `62110` renders `Menjamin konten … konten SARA dan [… cut off in the official source]`, **1 label
  for 1 truncated duty**; `01111` 7 duties/0 truncated/**0** labels; `18113` 4/0/**0**; `79122` with
  "Arab Saudi" ×23 → **0**. That last one is the proof that matters.
- **BOTH PROVE-LIVE mistakes were mine, and both are exemplar-selection:** the first exemplar came
  from CANONICAL, but `03120`'s page has **zero** obligations (detached-licensing code) — that zero
  read like "the cure failed". The second ignored **which tier the page opens by default**
  (`licensing[0]`): on `01111` the truncated string exists but sits in a tier that is not rendered.
  **Pick the exemplar from what the PAGE SERVES, and from the branch that actually renders.**
- **Follow-on — licence NAMES. ⚠️ THE PARAGRAPH THAT STOOD HERE WAS WRONG, and correcting it is
  worth more than the fix.** It said #3639 cured `"NIB dan"` on "21 codes, Google structured data and
  the page title" by making `resolveLicenseType` treat an unusable name as absent. **#3639 is inert.**
  `resolveLicenseType` is fed from `per_skala[].perizinan`, where `"NIB dan"` appears on **zero**
  codes; the 21 canonical occurrences live under **`per_skala_legacy[].perizinan`**, written for audit
  by `build_kbli_l2_oss_risk.py` and read by nothing that renders. #3639 was dequeued mid-flight, its
  description corrected to say it is defence-in-depth, and merged on those honest terms.
  - **The live before-state had already said so and was nearly read backwards.** `62110`, `47301`,
    `96100`, `15112` served `"NIB dan"` **zero** times and the derived `NIB + …` 18/14/1/14 times.
    That zero meant "you are measuring the wrong path", not "already fine". **A zero in a
    before-state is a claim about your probe as much as about the world.**
  - **The live path is the ENDPOINT** (#3642): `kbli_notebook.py` sets `licenses[].type` straight
    from the KG node name, so it reaches the explorer's licence cards AND the clipboard line that
    travels into client emails. Measured on prod: `"NIB dan"` on **10** codes
    (`03110 15112 15113 20293 25119 25933 28171 61901 62110 62191`) and
    `"Sertifikasi Cara Budi Daya Ternak Yang"` on **2** (`01445 01469`).
  - **`62110` is the anchor case — it carries guilt AND innocence in ONE response:** a licence typed
    `"NIB dan"` (scale Besar) alongside two typed `"NIB dan Sertifikat Standar"`, which contain `dan`
    but end on `Standar` and must be copied verbatim. Verify there, not on a page.
  - Labelled, never trimmed and never replaced: trimming to `"NIB"` states a weaker licence than the
    law requires, replacing it invents the ending, dropping it hides a licence the business needs.
  - **✅ MERGED, DEPLOYED AND PROVEN LIVE 2026-08-05.** #3642 merged as `0f6f3e67f3`; the frontend
    does not go live unattended (it lands `STAGED`), so `scripts/vercel_prod_deploy.py` built it and,
    after eight probes still showed the old build at terminal READY, promoted it — HTTP 201, and
    `balizero.com/api/health` now reports `commit: 0f6f3e67f3…`, **which is #3642's own merge commit**.
    Proof of BEHAVIOUR, not just of shipping: the `kbli-licence-summary.ts` read out of that exact
    deployed commit, run against the exact `licenses[].type` list `inspect_kbli 62110` returned in
    the same turn, produces
    `… NIB dan Sertifikat Standar, NIB dan Sertifikat Standar, NIB dan […cut off in the official source]`
    — the label **once**, on the truncated name, with both complete `NIB dan Sertifikat Standar`
    entries and `Izin Usaha` left bare. The served explorer chunk carries the shared module (note
    present, `Confirm the full wording at oss.go.id` present, negative control 0).

**🔴 SETTLED — DO NOT DEDUP `kg_edges`, AND DO NOT ADD THE UNIQUE CONSTRAINT.** #3635 left the 1,341
duplicated `BELONGS_TO` rows in place and ledgered a blast-radius analysis. It has been done, and
BOTH halves of the stated reason were wrong:

- **Wrong table.** `mediated_edges_builder` / `evidence_dossier` / `admin_crm_kg` all operate on
  **`crm_kg_edges`**; only `kbli_notebook.py` and `kbli_documents_phantom_cure.py` touch `kg_edges`
  with `BELONGS_TO`. The shared relationship-type NAME is not a shared table.
- **And the rows are not redundant.** Whole table: 2,118 duplicated triples / 2,161 excess rows over
  16 relationship types, of which only **423** are byte-identical. The KBLI slice: **all 1,341**
  differ in **BOTH** `source_chunk_ids` and `confidence`; **zero** byte-identical. They are two
  independent EXTRACTIONS of one fact, each recording which passage asserted it and how confidently.
  **Deleting either destroys provenance.**
- `crm_kg_edges` HAS `UNIQUE (source, target, relationship_type)` (migration 167) and `kg_edges` does
  not. That looks like the asymmetry-between-twins defect and is **not**: multi-evidence rows are this
  table's design, and the writers' `ON CONFLICT (relationship_id)` is consistent with it.
- **The reader-side dedup (#3635) is the correct and complete cure** — collapse at render, keep every
  evidence row. Right answer, better reason. Method note worth keeping: the root-cause hunt stopped
  at "here is the missing guard" and would have shipped the wrong fix; the next question —
  _"and is the thing that guard would prevent actually wrong?"_ — reversed the conclusion.

**🟢 2026-08-05 — THE `whatChanged` LANE: FOUR STORES, AND THE CURE ITSELF LEFT A CONTRADICTION IN
THREE OF THEM.** #3610 cured 13 codes still telling clients _"Direct 1:1 match from KBLI 2020 — code
and scope unchanged"_ on records whose own crosswalk denies it. Promoting it (prod was serving a
build **two commits behind** — nothing on this project goes live unattended) proved all 13 live:
`lie=0 cure=2` on each, innocence held on `01111/01112/01113`, whose records agree they are
continuous.

**What the promotion exposed is the lesson worth keeping.** The removal pattern knew two phrasings of
the claim; **"No structural changes" is a third** and was in neither, so on `47401` and `63900` the
cure deleted the sentences it recognised and published the honest replacement **next to a sentence
denying it** — live on the website and in the KG. And the first draft of the fix repeated the disease
a generation lower: written from those two, it missed `96210` (_"Hair salons have been consistently
classified across both KBLI versions"_), found only by pulling the KG's own vintage of all sixteen
cured texts.

Two halves, and only one changes what a client reads: **widening the removal pattern alone would have
cured nothing** — re-derived on the shipped catalogue, **zero** records are still convicted, so a
record whose convicting wording was already taken is refused by `drop_false_continuity`. The repair
pass (`residual_continuity_claim`, #3619) decides **without reading a record**: an already-retracted
text that still asserts continuity is an internal contradiction. What makes a measured-only pattern
safe is the organ beside it — pass D's replacement ends at `(GARUDA-FILIERA).`, so a cured text that
does not end there goes **red** instead of reaching a client, and the organ **refuses** rather than
cures.

**The KG cure is applied and verified by an independent path** (read-only Postgres, not the writer):
13 cured / 13 archived / 0 drift, and the corpus-wide count of nodes asserting continuity fell
725 → 713, exactly −13 minus the two that still carried residue. Innocence: the 6 records whose
crosswalk agrees (`47112 47242 47751 47761 47774 47782`) are untouched — `47242` is word-for-word the
shape of `47401`'s pre-cure text with the opposite truth.

**Still open in this lane:** the 4 unadjudicated layer disagreements (`91212 91222 91424 91425`, BPS
vs `pp28_sources`) — the replacement sentence deliberately asserts only the NEGATIVE for that reason;
and `reindex_kbli_2025_final.py::build_embedding_text` still bakes the old Bali framing into the
vectors (embedding model FROZEN → payload-only merge is the precedented fix).

**🟢 2026-08-03 (night) — THE CHAT CHANNEL NOW CARRIES THE BALI VERDICT, AND THE STORE ALWAYS KNEW.**
Production was asked whether a PT PMA can open a massage parlour (86995) in Bali and answered _"Yes,
you absolutely can!"_ with capital figures and next steps. The live Qdrant point for 86995 carried
`bali_blocked: true` at that moment. **Not a data gap — a disconnected pipe, one field wide**:
`KBLISearchResult` had nowhere to put the verdict, so nothing read it into the LLM context. It was
never about one code: **518** activities carry a Bali block the channel could not state.

- **Cured at the CHOKE POINT, not at the constructors** (#3557). Seven call sites build a
  `KBLISearchResult` and only two see a Qdrant payload; the other five read Postgres/the KG, which
  hold no Bali layer (measured: 0 rows of 1,563). Curing the two in view would not have cut the risk,
  only moved which question gets the wrong answer (W107). The backfill sits in the one function every
  answer passes through, and a test asserts that placement rather than trusting it.
- **Absence is SILENCE, never "open."** A missing verdict produces no sentence at all. Reading absence
  as permission is the exact inference this lane spent the week withdrawing from 32 codes.
- The 12h explanation cache prefix moved with the change (`v27`→`v28`) — without it, answers generated
  blind would have kept serving for half a day after the deploy.

**🟢 QDRANT BALI LAYER SYNCED — 39/39, applied and read back.** `kbli_qdrant_pma_sync.py` is now
one tool for both layers (#3555), and the separate `patch_qdrant_bali_l4.py` is DELETED: it keyed off
a field name canonical does not use (`l4_bali.verdict`), defaulted the miss to `"OPEN"`, and would
have published `OK_or_HIGHER_RISK` + "not blocked by moratorium" onto **118 currently-blocked codes**
— on the store `inspect_kbli` reads FIRST. Two tools that must agree about one fact are now one
(W105). Population derived from the canonical diff, not listed by hand: `--layer bali --codes <39>`,
dry-run → apply → **re-read: 39/39 already agreed**, then `kbli_inspect_cache_bust` (2 of 39 had an
entry; both evicted — one of them was the code this session had queried before the cure).

**🔴 THE SEVENTH SURFACE: the macOS app's EDITORIAL OVERLAY — three files nothing in this repo had
ever seen.** `check-fleet.sh` compared exactly ONE file (the machine dataset), found all four copies
aligned, and printed _"fleet aligned with canonical"_ over three laptops whose PROSE was materially
wrong. **The guard covered the file that cannot lie in prose and missed the three that do.** Measured
whole-document against canonical: 9 of 322 entries state an ownership figure canonical contradicts,
6 carry the withdrawn UMKM inference. Cured 8 (#3562) — per code, because the template written first
was wrong in BOTH directions: it would have inverted 55203 Vila's TRUE closure (the Perpres annex
really does allocate _Vila_ to Koperasi/UMKM) and dropped the Bali moratorium block from four others.
**55202 (youth hostel) was found only because the cure REFUSED** — the first audit read only the
paragraph naming PMA, and 55202 carries the sentence elsewhere: one miss in a family of six, inside
the probe written to find them. 79122 said Umrah travel is "fully open, 100%" (annex: 0%); 86101
handed the reader a 12–24 month roadmap to foreign-own a GOVERNMENT hospital.
**NOT reconciled, on purpose (7):** 64992/65121/66191/66301 are OJK sectoral caps canonical does not
model, 85102 encodes a Yayasan/SPK constraint, 73100 rests on a grep of a text-layer-dead PDF, 47221's
canonical cap is literally `special`. Canonical is the doubtful side in each — aligning prose to it
would manufacture agreement, not truth.

**🟡 CORRECTION TO THIS FILE'S OWN LEDGER — the 80-code channel cure names the WRONG blocker.** It
says the apply is parked because it "needs a write DSN" and "on M5 the fly credentials are dead."
Measured tonight: `flyctl auth whoami` → rc=0, `zero@balizero.com`; the deployed image holds the
write DSN and `kbli_documents_cure.py`. The real obstacle is different and does not move: the SAFE
selector `--all-licensing-absent` needs the repo layout (`scripts/kbli_filiera/`) that the image does
not ship, and it **cannot be substituted by `--only`** — the content-preservation gate runs _only_
under the state-selector (deliberately, since `--only` serves the quarantine population where the
stored text is fabricated by definition). So `--only` on this population would destroy the 25
hand-written rows the reviewed design exists to protect. Detector re-run tonight: `licensing_divergent`
is **25**, i.e. exactly the previously-REFUSED set — the 55 rebuildable are already written.
Unblocking wants the writer to accept a report produced by the predicate's sole owner, not a second
copy of the predicate.

**🔴 2026-08-03 — THE 39 "CLOSED TO PT PMA" BADGES ARE MOSTLY WRONG, AND THE REAL OBSTACLE IN BALI IS
NOT THE PERPRES AT ALL.** Two research files shipped, both graded by Codex on fresh context (the seat
is named in each frontmatter; the R1 gate rejects an unnamed one, correctly — an earlier draft said
"cross-family refute pass" when the refute lanes were Claude agents, i.e. the SAME family, W100).

- `research/compliance/2026-08-03-kbli-39-closure-verdicts.md` — primary sources. Of the 39 codes
  rendering `CHIUSO_PMA_NO_BESAR`: **7 genuinely reserved** (55201 homestay · 55203 villa · 79903 tour
  guide · 95291 tailoring · 96100 laundry · 96210 barber · 96220 salon), **2 partial** (55209 only the
  _Guest House_ slice, 43110 only _simple/intermediate technology_ demolition — Perpres 10/2021
  **Pasal 5(5)** scopes a Lampiran II reservation to the wording in the Bidang Usaha column),
  **11 carry a non-ownership requirement a PT PMA can satisfy**, **19 carry nothing located**.
- **ROOT CAUSE, one inference used as primary ground:** _"no Usaha Besar scale row → reserved for UMKM
  → closed to PMA"_. **Permeninves/BKPM 5/2025 Pasal 26(1) inverts it** — Usaha Besar is a CONSEQUENCE
  of PMA status, not a gate a licensing table can withhold. That inference is what produced all 39.
- `research/compliance/2026-08-03-kbli-39-market-sources.md` — secondary sources, 9 lanes. Graded
  DEFECTIVE by Codex; four claims withdrawn or narrowed IN PLACE. **The withdrawn one matters: the
  "IDR 10bn leaves nothing in between" argument is dead** — `modal usaha` and `nilai investasi` are
  different legal quantities and no cited provision makes them one. Do not reuse it.

**🔴 THE GOVERNOR'S LETTER, READ AT SOURCE (2026-08-03) — the market quotes its background section.**
`B.27.000/642/PM/DPMPTSP`, 28 Jan 2026, Koster → Menteri Investasi/BKPM. The scan (agency-hosted,
`flado.id`) has a **zero-character text layer**; it was rendered at 200 dpi and read from the images.

- **`Lampiran: -` — NO ANNEX.** Neither the "nine codes" nor the "eighteen" was ever attached.
- **The operative request is BY RISK TIER, verbatim:** close on OSS _"1. PMA … dengan Tingkat Risiko
  **Rendah dan Menengah Rendah** yang berada di Provinsi Bali; dan 2. PMA yang berlokasi usaha di
  **virtual office**"_. Two categories, no code list.
- The nine KBLI everyone publishes as "the blocked list" sit at background point 2 under _"sebagian
  besar **mengajukan** dengan KBLI"_ — the codes PMAs most often APPLY FOR, cited as evidence of the
  problem. Illustration, not scope.
- Purpose (point 3, verbatim): the scheme is _"digunakan sebagai sarana memperoleh **izin tinggal**
  bagi WNA … tanpa adanya kegiatan berusaha yang nyata"_. Immigration is on the 10-name copy list.
- **The instrument nobody has cited:** it follows a **Nota Kesepakatan BKPM RI ↔ Bali**,
  `KS.01.00/2.S/A.1/2026` + `B.36.100.3.7/2767/KS/B.PEMKESRA`, _tentang Pengendalian Pelaksanaan
  Penanaman Modal di Provinsi Bali_. **NEXT DOCUMENT TO OBTAIN** — not held, not in the literature.
- **Measured on canonical: 22 of the 39 carry only `Rendah`/`Menengah Rendah`** — exactly the tiers
  named. The other 17 hold no licensing rows at all, so they cannot be classified (same missing
  `per_skala` population the channel cure works through).
- **Limits, stated:** it is a REQUEST; no implementing instrument located. The scan is internally
  consistent but not authenticated by an official publisher.

**🟢 STILL IN FORCE — verified this session by direct fetch of peraturan.bpk.go.id (HTTP 200), not by
report.** `Details/161806` Perpres **10/2021 → Status `Berlaku`**, `Diubah dengan` Perpres 49/2021;
`Details/168534` Perpres **49/2021 → Status `Berlaku`**. Neither is revoked. What died is the
LANGUAGE: the annexes still name KBLI-2020 codes and no investment instrument has ever been re-issued
in KBLI-2025 numbering, so every 2025-numbered verdict runs through the BPS conversion table — a
statistical artefact with **no legal force**. Say that out loud in any client-facing claim.

**🟢 APPLIED 2026-08-03 — THE 39 ARE RE-DECIDED IN CANONICAL.** Zero's order: _"tu qua fai la
sessione e porti /kbli-navigator … pronto per BKPM senza aspettare operatori"_. New sanctioned
compiler `scripts/kbli_filiera/cure_l4bali_perpres_adjudication.py` + the adjudication as DATA at
`data/kbli-filiera/kbli39-perpres-adjudication.json`. Ownership comes from the Perpres annexes, the
Bali position from the risk tier — the two questions answered by the two things that answer them.

`CHIUSO_PMA_NO_BESAR` **39 → 7** (the genuinely allocated; only the `reason` changed, from the OSS
inference to the annex row) · `BLOCCATO_DIPENDE_SCOPE` **+2** (43110, 55209 — Pasal 5(5)) ·
`CHIUSO_MORATORIA_BALI` **35 → 48** (still red, TRUE reason) · `NON_CLASSIFICABILE` **8 → 25**
(no licensing rows held; we say so).

National `pma_*` fields untouched — fingerprint asserted before/after, a change ABORTS. Corpus 13
tests, mutation-verified 5/5 including the dangerous direction (opening a moratorium-blocked code).

**Propagated:** `scripts/sync_kbli_dataset.sh` → apps/mouth/data, apps/backend-rag/backend/data,
apps/kbli-navigator/data (+ the gitignored backend runtime copy); `kbli-dataset-version.json` bumped
to `sha256:0bd006544c6f…` / 2026-08-03. `apps/kbli-navigator` resolves canonical directly — no copy.

**STILL OPEN, named by the sync script's own notice — do not call this done:**

- **Qdrant payload** — `inspect_kbli` reads `pma_status` from Qdrant FIRST; `l4_bali` rides the same
  payload. Tool: `apps/backend-rag/scripts/patch_qdrant_bali_l4.py` (payload merge, NEVER a re-index
  — the embedding model is FROZEN).
- **The native macOS app fleet** (M5/Pro/Mini + team zip) — outside the repo, `check-fleet.sh` is the
  only thing that speaks for it.
- **`chat_kbli`** still answers on `kbli_documents.content`, which does not carry `l4_bali`; whether
  the channel should now brake on the 7 is a separate cure.
- **The 17 `NON_CLASSIFICABILE`** need licensing rows before they can say anything about Bali. Same
  population as the channel-cure gap.

**🟢 TOOLING (2026-08-03).** #3548 the channel cure was dead at import in the deployed image (a
module-level `parents[4]`), taking `--only` with it — merged, live. #3550 `--only` bypasses the
content-preservation gate silently; now REPORTED — merged. #3551 (open) `perpres_umkm_reservation_relation.py`
filed **30 live pages as "archaeology"**: the `retired-2020-code` bucket tested whether the same NUMBER
survives the vintage change, so every RENUMBERED code landed in the one bucket declared
not-client-facing — 30 of 30 had a live heir, reaching 66 pages, 63 of them `TERBUKA/100%`. This is
why 7 of the 9 real reservations had to be re-derived by hand. **Identity wins where it exists; the
crosswalk resolves only what identity cannot** — the first fix let the crosswalk win unconditionally
and a spurious edge (`14111 Industri Pakaian Jadi → 17091 Industri Kertas Tisu`) demoted 34 rows into
a bucket nothing evaluates. Still a REPORTER, exit 0 (Legge 5).

---

**🟡 F1 — THE CHANNEL CURE NOW SELECTS BY STATE, AND REFUSES 25 OF 80 ON PURPOSE (2026-08-02, code
shipped; the DB apply is a separate step and is NOT claimed here).**

The detector's own numbers, re-measured this session rather than read off this file: **3**
`pma_status` divergences (`02101`, `03110`, `03120` — all `canonical=TERBUKA table=TERBATAS`, i.e.
the channel is MORE restrictive than canonical, the safe direction) and **80** codes where canonical
holds verified OSS-2025 licensing rows and `kbli_documents` serves **none** (687 rows). The three
sea-cabotage codes this section used to list among the divergences (`50122/50123/50126`) are
**already cured** — `TERBATAS`, `updated_at 2026-08-01` — so the "8 divergences" above describes a
pre-cure world; only these 3 remain, and 2 of them (`02101`, `03120`) carry
`pma_cap_verified: false` on canonical itself, so syncing them would claim a truth fix nobody has.

**What changed: the SELECTOR, not the renderer.** Every cure to date ran `--only <hand-written
list>` — 140 rows total, so **1,423 of the table's 1,563 rows had never been touched by any cure**.
`kbli_documents_cure.py --all-licensing-absent` now asks `kbli_surface_conformance.py --json` for
STATE and consumes its verdict instead of re-deriving the predicate, so the two tools cannot
disagree about the same fact (W105). Exit 4 (CANNOT-VERIFY) is a REFUSAL, not an empty finding —
that report carries zero divergences, byte-identical to a healthy fleet (W84). One direction only:
the mirror case belongs to `--all-quarantined`, and curing it here would rewrite a live row-set into
a gap statement.

**A CROSS-FAMILY REVIEW RETURNED "DEFECTIVE" ON THE FIRST DESIGN, AND TWO OF ITS FOUR POINTS CHANGED
THE CODE.** (Codex GPT-5.6, instructed to refute; generator≠grader.)

- The first draft found editorial prose by searching for the headings `WHAT IT MEANS` / `BALI
CONTEXT` — a guard judging FORM, so prose under any other heading would have been classified
  disposable and **destroyed** (superscar #3). Replaced by POSITIVE, whole-document recognition of
  the 2026-02-18 machine seed: a row earns a rebuild only if its heading names this code AND every
  `##` section belongs to that seed's three. Measured: all 50 machine-shaped rows carry exactly
  `Informasi Umum` / `Deskripsi Kegiatan Usaha` / `Investasi Asing (PMA)` and nothing else, so a
  hand-added section refuses the row. Head-only matching would have passed a row with material
  appended below — pinned by a test.
- **The uncomfortable call, taken in the direction the review argued.** 5 rows (`74191 85610 86910
86995 96220`) say _"Since there's no PP28 data yet, licensing is currently minimal — get your NIB
  early"_ on codes where canonical now holds government rows. A government-contradicted filing
  instruction harms a client more than losing market copy, so those 5 are **rebuilt** even though
  they are hand-written, and what is lost is stated: `86995`'s disambiguation from `86991` (medical
  massage) and `96230` (spa) now lives only in `kbli_documents_archive`. Ledgered as an editorial
  debt, not glossed.
- Net: **80 selected → 55 rebuildable (50 machine-seed + 5 contradicted-claim), 25 REFUSED and
  named.** The 25 keep hand-written prose AND keep serving `Perizinan: N/A` on WhatsApp/webchat —
  refusal is the right default but is NOT a resolution, and closing them needs prose re-authored
  around the new rows (Legge 5).
- Two review points did NOT change the code and are recorded as measured limits: the archive is
  ONE-SHOT per code (`ON CONFLICT DO NOTHING`), so a SECOND cure of the same row preserves nothing —
  measured **0 of the 80** are already archived, so it does not bite this run and will bite the
  editorial pass; and the literal-phrase probe that found the 5 is not a general judgment about
  prose contradicting data.

**NOT CLAIMED: nothing has been written to the database.** The apply needs a write DSN; the local
Keychain holds `nuzantara-postgres-readonly` only, and on M5 the fly credentials are dead — so the
apply runs from Pro, and until it does, the channel still serves `Perizinan: N/A` on all 80.

**🟢 2026-08-02 — THE PERPRES CAP IS LIVE ON THE CHANNELS. Twenty codes cured, and the cure had to be
chased through four stores before a client could see it.** #3515 (canonical) → #3517 (Qdrant sync
tool) → #3518 (LLM corpus). What a client is told now, measured on prod rather than inferred:

- `chat_kbli` on `51101`: _"no, you cannot own 100% … limited to a maximum of 49% … the Indonesian
  partner must retain a single majority."_ Before: 100% open.
- `inspect_kbli 51101`: `pma_status` **TERBATAS**. Before: TERBUKA.
- Innocence held on both surfaces: `10761` still reads TERBUKA/100%, correctly — the annex restricts
  only _coffee processing that holds a geographical indication_, a narrower **bidang usaha** than the
  2025 code. That is why 12 BROADER + 2 RENAMED codes were REFUSED rather than patched.

**THE LESSON WORTH KEEPING: `inspect_kbli` reads `pma_status` from QDRANT FIRST, and the kg_nodes
property only as a fallback.** So `kg_kbli_resync.py` — which exists _because_ that endpoint once
served a stale status — is a no-op on that field while Qdrant carries a value. Measured: after the KG
resync, `kg_nodes` said TERBATAS on all twenty and the endpoint still answered TERBUKA. The
propagation order that actually reaches a client:

1. `kbli_documents_cure.py --only <codes> --apply` — feeds `chat_kbli` verbatim. **The cap lands in
   `content`, not in `metadata`**; the metadata cap key stays absent by design.
2. `kg_kbli_resync.py --apply` — syncs `pma_status` only; the cap field is on **0** kg_nodes rows.
3. `kbli_qdrant_pma_sync.py --collection kbli_2025_final_hybrid --codes <…> --apply` — **the decisive
   one**, new in #3517. Payload-only merge, never a re-index (the embedding model is FROZEN).
4. `kbli_inspect_cache_bust.py --only <codes> --apply` — up to a 30-day TTL; a cured store is
   invisible until evicted. Any diagnostic call made BEFORE the cure writes a stale entry: 1 of the 20
   needed eviction, and it was the one this session had queried.

**PROBE TRAPS PAID FOR HERE** — each returned a clean, believable zero or a plausible wrong answer:

- `kbli_2025_final` **is not a collection**. It resolves to `kbli_2025_final_hybrid`;
  `kbli_2025_final_oss` (10,825 points) answers to none of the code keys. A filter on a non-existent
  collection returns zero points for EVERY code, including ones you know exist. Run a code you know
  exists as a positive control before believing any zero — the same rule vindicated the cache-bust
  step, where `0/20` was true and `56101` proved the tool could still see one.
- `kg_nodes.name` is the ENGLISH TITLE; the code lives in the `kode` property.
- On a static file, a cache-busting query does NOT bust the Vercel edge cache, and neither does a
  client no-cache header. **Compare the `etag` against an md5 you computed yourself.**

**🟢 CLOSED — the frontend half is now SERVED, and the cause is no longer a family of suspects.**
Zero ran the interactive `vercel login`; the session did the rest. **That login was called "the one
`operator[gui]` step" and it is NOT one — corrected the same day by the next promote.** The credential
`expiresAt` is measured in HOURS: the one minted that morning expired at 09:18:57Z mid-session, and
`403 {"invalidToken": true}` is therefore the ORDINARY state of a healthy machine, not evidence that no
credential exists. `auth.json` carries a `refreshToken`; `vercel whoami` redeems it in ~1s and the
session promoted `223a8471` with the result (HTTP 201) with no human involved. **Do not re-open a
"waiting for Zero to log in" lane on a 403** — run the refresh first; the login is the entrance only
when the refresh fails. Armed in code so this cannot be re-derived by hand:
`vercel_prod_deploy.py::_token()` now performs the refresh instead of instructing a human to.
The newest `production`/`READY` deployment already carried the cure and the custom domains were
still serving the previous build — `POST /v10/projects/<id>/promote/<dpl>` → HTTP 201 published it.
**Cause established, and by a control that could have refuted it — not by elimination.** Reading
the promoted deployment back gives `readySubstate: PROMOTED`, but that is the state AFTER the
promote and proves nothing on its own. The evidence is the SIBLINGS: two other Git-created
`production`/`READY` deployments from the same day — `9fcdc00a0` (PR #3515, mouth-touching, 21:24)
and `9a6a30a38` (PR #3513, a docs PR, 17:52) — are **still `STAGED` right now**, hours later, having
never been promoted by anything. The mouth-touching one is what makes this the test; the docs one
shows the staging is not content-dependent.
Git-integration production builds on this project land staged and stay staged. So the cause is the
staging mechanism already ledgered on 2026-07-30, NOT a stale alias and NOT the edge cache; had
those two read `PROMOTED`, this paragraph would be wrong. **This also refutes a note written here
on 2026-07-30** claiming a merge goes live on its own and the lag is CDN/deployment-creation rather
than promotion: `9fcdc00a0` has been READY and unserved for ~14h. Nothing publishes unattended.

PROVEN LIVE on `balizero.com/llms-kbli.txt`, by etag against an md5 computed here (a cache-busting
query and a client no-cache header both fail to reach origin on a static asset): `aa793fa029bd…`
= the post-regeneration file, `age: 0`, and rows publishing a TERTUTUP code as `100%` foreign-open
**61 → 0**. Read as content rather than as one number: `11010` TERTUTUP now `0%` (was `100%`),
`47221` prints `special` instead of an invented percentage, 64 rows at `0%`, and the 217 codes with
no risk classification say `Not classified` where they used to assert `LOW`. 1,570 lines — the file
is whole, not truncated into agreement.

**Declared gap, measured not assumed:** prod serves `1050e5c99` while `origin/main` is `ddd86a1ef`.
`git diff --name-only 1050e5c99 origin/main -- apps/mouth/` is **empty** — the two commits in
between are the backend sync tool and this corner, so the served frontend and the tip are identical
where it renders. The recurrence question (nothing promotes unattended) is NOT re-opened here: it
already has its own ledger line from 2026-07-30, and a second one would be a twin.

**🟢 THE SIXTH SURFACE: the macOS app on M5/Pro/Mini — cured 2026-08-02, and it was missing from
this corner entirely, which is why it kept being left out of the consumer map.** Write it down here
or the next session will call five surfaces "all of them" too. `~/Desktop/kbli-navigator-app` builds
`KBLI Navigator.app`, installed on the Desktop of all three machines plus a zip handed to the team —
a consumer copy OUTSIDE the repo, so `check-kbli-dataset-sync` can never reach it. It was carrying
`27a18d4821dc` against canonical `54a89c221135`: **20 codes divergent, all 20 promising MORE foreign
ownership than the truth** (`25200` arms and `30400` military vehicles at 100% vs 49%, `51101`/`51102`
airlines likewise, `79122` Umrah/Hajj at 100% vs 0). Exactly what PR #3515 said it had cured — the web
had, the desktop had not — and not dormant: the M5 app had been opened 48 times, last on 2026-07-29.
Cured by running tooling that already existed and had never been run (`deploy/install-3mac.sh`, then
`make-team-installer.sh`); proven per machine by CONTENT, with `10761` as an unmoved control, and a
full re-diff of 1,559 codes giving 0 divergent. `check-fleet.sh` now exits 0 with all four surfaces on
`54a89c221135` = the `datasetSha256` in `apps/mouth/data/kbli-dataset-version.json`.

**The lesson worth more than the fix:** `sync_kbli_dataset.sh` had a notice for exactly this, and it
compared only the app repo's `Resources/` — which `build.sh` refreshes from canonical on every build.
So between a build and a deploy it printed _"already matches canonical"_ over three stale laptops. A
guard that can print the good news over a bad world is worse than no guard. Now in
`scripts/lib/kbli_fleet_notice.sh`, judging BOTH files, with guilt+innocence tests a workflow actually
names. Deliberately NOT made to exit non-zero — the `kbli_filiera` cure compilers call the sync script
unconditionally under errexit, so that would abort a DATA cure to deliver a DEPLOY reminder; the ledger
line that proposed it was refuted by reading the callers.

**Still open on this surface (ledgered, not lost):** the app repo has **no git remote** — a HOME-fork
by construction; `check-fleet.sh` is correct and **nothing executes it**; and on Mini a file provider
re-stamps `com.apple.FinderInfo` within ~20s so an ad-hoc signature there cannot stay valid (NOT called
breakage — `spctl` rejects all three machines equally, which is what ad-hoc signing means).

**🟡 STILL OPEN — 12 BROADER codes deliberately unadjudicated.** Their 2025 code is wider than the
_bidang usaha_ the instrument restricts, so a cap remains a per-code decision, not a deduction;
`--strict` on `perpres_foreign_cap_relation.py` stays disarmed until they are ruled on (arming a gate
on a live backlog is its own defect). **RESOLVED 2026-08-12:** the 2 RENAMED codes `21021`/`21022`
are now `TERBATAS`, 0% foreign ownership, on Perpres 49/2021 Annex III entries #5/#6 respectively.
Evidence/implementation pointer: `scripts/kbli_filiera/apply_perpres_foreign_caps.py:93-121`.

**🟡 `operator[business]` — whether any client already advised on one of these codes should be
reached back to.** Not a technical question, and not a session's to answer.

**🔴🔴 2026-08-01 (F2, evening) — WE TELL CLIENTS THEY CAN WHOLLY OWN AN INDONESIAN ARMS FACTORY, A
SCHEDULED AIRLINE AND AN UMRAH TRAVEL AGENCY. THE OPERATIVE PERPRES CAPS ALL THREE.** Proven on the live
site, not inferred — `/kbli/25200` (Industri Senjata dan Amunisi), `/kbli/79122` (Biro Perjalanan Ibadah
Umrah dan Haji Khusus), `/kbli/51101` (Angkutan Udara Niaga Berjadwal) each render **"100% Open"** with
**zero** occurrences of "49%". The law: 49% for the first and third (defence needs the Minister's
approval to exceed it; air additionally requires the national owner to keep single majority), **0%** for
umrah travel. Found by opening the Perpres lampiran that had been in the vault since 2026-07-19 and that
nobody had read.

**Three independent things had to be true for this to survive, and each is its own lesson:**

1. **The instrument everyone cites is the wrong one.** Perpres 49/2021 arts. 3/4/5 read
   `Lampiran I diubah` · `Lampiran II diubah` · `Lampiran III diubah` — all three annexes of 10/2021 were
   REPLACED. Canonical's locator for `47221` still says "Perpres 10/2021 Lampiran III … entry #44"; the
   operative Lampiran III has **37** entries and does not contain 47221 at all (49/2021 moved it into the
   body, art. 3a, as _persyaratan lainnya_ — a different legal category from a percentage cap). Follow
   that locator today and it leads nowhere.
2. **The vaulted 10/2021 lampiran are text-layer-dead** — 0 real words and 0 five-digit sequences extract
   from all three. So `grep <code>` there returns 0 for EVERY code, always. At least two canonical
   verdicts rest on exactly such a negative: `02102` ("code absent from all 3 lampiran (grep 0) →
   open-default") and `73100` ("ZERO 73xxx codes anywhere → neighbor-% contamination"). Not proven wrong
   — **proven unverifiable with what we hold**, which is not the same thing and must not be written up as
   if it were.
3. **The operative annex's own text layer corrupts the two columns that matter** (`26513`→"265L3",
   `49%`→"497o", `100%`→"lOOo/o"). A parse of it read 40 code tokens for a 41-pair table and could not
   read a single percentage. The four pages were rendered at 200dpi and transcribed **from the images**;
   the image is the authority, the text layer is the suspect.

**The measured join (F2 step 3, through the BPS crosswalk — never bare digits): agree 6 · DISAGREE 35 ·
ambiguous-by-law 2 · no 2025 heir 1.** A first reading of the titles puts ~20 of the 35 in "activity
identity is plain" (`Industri Senjata dan Amunisi`, `Aktivitas Kurir`, `Pelayaran Rakyat`, 11
ferry/river-lake codes, couriers, military vehicles) and ~15 in "the 2025 code is BROADER than the
restricted activity" — `10761` is _Pengolahan Kopi_ while the law restricts only coffee **with a
geographical indication**; `26513` is _Alat Ukur dan Alat Uji Elektronik_ while the law restricts
**defence radar**. That second bucket is the D0–D6 population §5.3 said would be produced rather than
promised; it now has a number.

**THE STRUCTURAL FINDING, bigger than the 35: the cap attaches to the (bidang usaha, KBLI) PAIR, never
to the code.** Entry 7 caps `30111` at 49% as a warship yard; entry 8 caps **the same code** at 0% as a
builder of pinisi, cadik and traditional wooden vessels — and the body says so explicitly (**Pasal 6 ayat (3)** for
Lampiran III; the twin for Lampiran II is Pasal 5 ayat (5)): where one KBLI covers more than one bidang
usaha, the requirement applies only to the bidang usaha named in that column. (Corrected 2026-08-06 at the
source — this said `art. 3(3)`, which does not exist; Pasal 3 has two ayat.) Our single `pma_max_asing` integer cannot express that, nor a phase-dependent cap (`58130`: 0%
at establishment, 49% via the capital market for expansion; broadcasting 20% likewise), nor a
conditional one. **Any future cure that picks one number for such a code is asserting something the
instrument does not say** — those codes are reported `ambiguous` and are not auto-patchable by
construction (pinned by a parametrised test: even when the catalogue happens to match one of the two
lawful values, the verdict stays ambiguous).

Shipped: `scripts/kbli_filiera/perpres_foreign_cap_relation.py` + `data/kbli-filiera/perpres-foreign-caps.json`
(41 pairs, per-entry locator, vintage 2021-05-25) + 16 guilt/innocence/transcription-pin tests,
mutation-verified. **A REPORTER, not a gate**: `--strict` exists and is deliberately NOT armed — arming
it on a 35-item backlog would turn every unrelated PR red (W95). Flipping it is the closing act of the
cure lane. Still in force check done before using any of this as a yardstick: no presidential regulation
has replaced 10/2021+49/2021 as of 2026.

**CURE APPLIED to canonical the same day — 20 patched, 14 deliberately not.** `DISAGREE 35 → 14`
(`agree 6 → 27`; the arithmetic works out to 21 rows because `51101` is reached from two ancestors).
Patched: the arms/military family (`25200`, `30400`), both commercial air-transport codes, all 11
ferry / river-lake / pelayaran-rakyat codes, couriers (`53200`), wooden building materials (`16221`) and
umrah travel (`79122`). Each carries `pma_official_basis` = the annex entry, `pma_cap_verified: true`
and a `pma_kondisi` naming the actual condition (single majority · Defence Minister approval · domestic
capital only) — the conditions the old single-integer model silently dropped.
**0% foreign becomes `TERBATAS`, never `TERTUTUP`**: "Modal dalam negeri 100%" closes the activity to
FOREIGN capital, not to everyone, and `TERTUTUP` here holds narcotics and alcohol. The precedent is
`47111` (TERBATAS / 0 / "UMKM only"). Filing an umrah agency with narcotics would have been a different
false statement, arrived at by tidiness.
**Not patched, with the reason written per code in `ADJUDICATION`:** 12 where the 2025 code is BROADER
than the restricted activity (`10761` is all coffee processing, the annex restricts only coffee with a
geographical indication; `26513` is electronic measuring instruments, the annex restricts defence radar;
`30301`-`30303` are civil aircraft, the annex restricts military) and 2 where the rename looks right but
is unproven (`21021`/`21022`: "Obat Bahan Alam" is plausibly today's name for "obat tradisional" — that
equivalence wants a BPOM instrument, not an inference). **The list of what we refused to touch is as
much the deliverable as the patch.**
A formatting trap worth remembering: the canonical file is 540,083 lines at `indent=2`, and the first
writer draft used `indent=1` — a 20-record change would have arrived as an unreviewable whole-file diff.
Matching the file's own serialisation keeps it at **126 added / 66 removed**, and a test now pins it
(a run with nothing to patch must leave the bytes identical).

**Corollary that corrects this morning's scoreboard: the PMA axis is not merely "1% located" — where we
now HAVE the source, the catalogue contradicts it.** And `classify_pma` over-counts: several of the 13
`located` records carry a documented ABSENCE ("code absent from all 3 lampiran → open-default"), which is
not a locator. It measures the field's shape, not the entity — the family-#3 disease, in the instrument
built to measure the disease.

**🟢 2026-08-01 (later same day) — THE THREE SEA-CABOTAGE LIES ARE GONE FROM THE CHANNEL: 5 OF THE 8
`pma_status` DIVERGENCES CURED IN PROD AND PROVEN LIVE. The other 3 were held back, and WHY is the more
useful half of this entry.** `chat_kbli` for `50122` now answers _"you cannot own 100% … **TERBATAS** …
cap **49%** … joint venture ≥51%"_ where it used to answer open; `50123`/`50126` likewise, plus
`02102`/`73100` which failed restrictively. Applied inside the Fly machine
(`python backend/scripts/kbli_documents_cure.py --only 02102,50122,50123,50126,73100 --apply`) and
re-read through the READ-ONLY role, never the applier's own report — `kbli_documents_archive` holds the
pre-cure rows byte-exact, so the before/after is evidence rather than memory. Licensing rows on those 5
went 1 → 4-12 each. Three traps paid for here, all cheap to avoid next time:

- **`PYTHONPATH=.` KILLS the prod container** (it REPLACES site-packages, it does not extend them) — the
  first run died on `ModuleNotFoundError: asyncpg`. This script imports nothing from `backend.*`; run it
  with a bare `cd /app && python backend/scripts/…`.
- **The canonical dataset is NOT in the image** (`/app/source_documents` does not exist — L2.11b), so the
  cure fetches `--dataset` over HTTP. `RAW_BASE` names `Balizero1987/Teman2` while this repo is known as
  `Bali-Zero/Teman2`: identity was established by downloading it and matching sha256 against
  `origin/main`'s blob, never by trusting the name.
- **The script's own docstring claimed a safety gate that does not exist** — it said an `--only` code
  without a `per_skala_disputed_*` marker "is skipped with a logged reason". `main()` never checks the
  marker; it gates `--all-quarantined` only. None of these 8 codes carries the marker, so the documented
  behaviour would have skipped every one of them. Corrected in the file, with the REAL guarantee stated
  in its place (the cure is a pure function of the canonical record, so verify the record with
  `_coverage_basis.classify_licensing/classify_pma` — all 5 cured codes are `sourced_oss_2025` +
  `located`).

**THE THREE HELD BACK — each is a different lesson, none is "not done yet".** `02101`/`03120`: canonical
says `TERBUKA` but carries `pma_cap_verified: false` and no `pma_official_basis`, so curing would push an
UNSOURCED "100% open" onto a second surface (`03120` = freshwater capture fisheries). The table's current
`TERBATAS` is equally unsourced but errs conservatively — holding adds no new claim. Their cure is
L2.11c (make the SITE honest), already Zero-gated, not this tool. `03110`: the cure is correct but
computes **48,008 chars** of `content` against a table whose live max is **25,483** (p99 13,272, median
2,458) — and `chat_kbli` injects `content` VERBATIM with no truncation. A 69-row licensing table wants a
channel-appropriate rendering before it enters an LLM context. **Size is a scope dimension on this store
and on no other.** Cache needed no eviction and this was checked, not assumed: `@cached` keys on the
hashed args including `parent_docs`, so a changed row misses by construction.

**Also found live, NOT cured:** every `chat_kbli` answer is stamped `sources: [{"title": "PP 28/2025"}]`,
including this one, whose decisive fact (the 49% cap) comes from **Perpres 10/2021 Lampiran III**. A real
regulation attached to the wrong claim — same family as L2.11d. Ledgered.

**🟢 2026-08-01 — THE PROGRAMME NOW HAS A SCOREBOARD, AND IT SAYS THE AXIS WE WERE WORKING ON IS DONE
WHILE THE ONE NOBODY TOUCHED IS AT 1%.** Run
`python3 scripts/kbli_filiera/kbli_coverage_scoreboard.py` before trusting any number below it.
Measured today: **licensing 1,559/1,559 honest** (1,337 OSS-2025-sourced · 217 declared gaps · 5
PP28-located) · **crosswalk 1,338/1,559** (mechanical ancestry with a locator, 0 adjudicated — honest
because the page claims provenance only) · **PMA 15/1,559 = 1.0%** (13 records name a per-code basis;
**1,544 assert a foreign-ownership verdict with nothing on the record saying where it came from**).
The plan that follows from this is §5, REWRITTEN today on Zero's mandate — it retires the A/B/C/D
sweep framing. **The "99 no-scope codes still to adjudicate" carried by this section are DECLARED
GAPS, not lies in production**; they are product improvement, and F4's refresh loop closes them free.

**🔴 CORRECTION TO L2.11e BELOW — the 17 divergences it reports were ALREADY CURED when it was
written.** Re-measured on prod this turn through the read-only role: all 17 read `TERTUTUP` with the
canonical Title Case titles restored, and their `updated_at` is **2026-07-26T23:32Z** — i.e. the
re-seed landed BEFORE the census that entry dates 2026-07-27. Nothing was lost; the ledger simply
recorded a superseded state as current. Left in place below because its ANALYSIS (the divergence
tracks rows that were never re-seeded, and the `--only` path needed no code change) is correct and is
exactly what the two findings below confirm.

**🔴 THE REAL POPULATION: 1,423 of `kbli_documents`' 1,563 rows (91%) have NEVER been touched by any
cure.** Every cure to date ran `--only <named list>`, 140 rows in total. Measured two ways that agree
exactly: `updated_at < 2026-07-01` = 1,423, and `judul = upper(judul)` (the original 2026-02-18
UPPERCASE seed) = 1,423. Two findings fall out of it, both found by the new state-based detector
(`scripts/kbli_filiera/kbli_surface_conformance.py`) on its first run, neither previously in this
corner:

- **8 live `pma_status` divergences** against canonical, in the store `chat_kbli` injects verbatim into
  the LLM context. Three are PERMISSIVE: **`50122`/`50123`/`50126`** (sea cabotage) read `TERBUKA` in
  the table while canonical carries an **adjudicated 49% cap** quoting Perpres 10/2021 Lampiran III —
  and their siblings `50111`/`50121` read `TERBATAS`, so the answer a client gets depends on the last
  digit. The other five (`02101`, `02102`, `03110`, `03120`, `73100`) fail restrictively. **Six of the
  eight sync to an adjudicated basis; two (`02101`, `03120`) sync only to canonical's own value, which
  itself carries `pma_cap_verified: false`** — a cure must not claim a truth fix on those two.
- **80 codes where the channel serves NO licensing while canonical holds verified rows** — **687 rows**,
  all from the trusted OSS-2025-native core, including `82400` (MICE organisers), `55400`, `56400`, the
  `65xxx` insurance family and much of `85xxx` education. Verified not to be probe poverty: the
  `content` column itself reads `Perizinan: N/A`. Honest-degrading, not a lie — but the WhatsApp/webchat
  channel is materially poorer than the website on exactly the codes where our data is best.

**Shipped with this entry (F0 + F1-detect of §5):** `kbli_coverage_scoreboard.py` + `_coverage_basis.py`

- ratchet baseline `data/kbli-filiera/coverage-baseline.json`, armed in
  `kbli-filiera-vault-compilers.yml` with the canonical dataset in its `paths:` trigger (a data-plane
  commit that strips provenance cannot dodge the gate); and `kbli_surface_conformance.py`, read-only,
  selecting on STATE rather than on a list of codes. 46 new guilt+innocence tests; the ratchet is
  mutation-verified against the real 1,559-record dataset. **NOT yet armed on a schedule** — the
  conformance detector needs DB access so it cannot live in CI; today it is a manual run, and that is a
  ledger line, not a claim.

**🟢 L2.13 — A CAPITAL THRESHOLD IS NOT A PERMIT: `inspect_kbli` CALLED 35 ENTITY TYPES
"LICENSES" (#3323, SHIPPED + PROVEN-LIVE 2026-07-27, squash `ff2371156a`).**
The KG route that answers WhatsApp/webchat walked **every** outgoing `REQUIRES` edge from a
KBLI node and appended the target's **name** to `licenses[]`, with no notion of what the target
was. Measured on prod: **35 distinct target entity types** reach that list, and **8,026 of
15,055 edges are not permits**. On `56101` (restaurant — among the highest-traffic questions
this product receives) a client was shown **23 "licences"**, 8 of them false: seven renderings
of the same two _capital thresholds_ (`10 Billion IDR`, `2.5 Billion IDR`, `Rp 2.5 miliar`,
`IDR 10 billion`, `IDR 10 miliar`, `Rp10.000.000.000,00`, `Modal Disetor`) plus `PT PMA`, the
company form. Presenting a capital threshold as a permit to obtain is exactly the
plausible-but-wrong assertion this navigator exists to eliminate.

Cure: `backend/services/kbli_requires_kind.py` classifies by **entity type**, never by
substring in the name — the names are precisely where the noise lives (`"NIB dan Izin (…)"`
vs `"Biaya izin …"`, both containing "izin"). Two rules: **nothing is dropped** (non-permits
move to the additive `related_requirements` field —
costs/durations/obligations/regulations/documents/entity_forms/immigration/systems/other;
deleting 7,369 `dokumen` edges would have been a second defect wearing the shape of a fix), and
**an unknown type is never promoted** (falls to `other` — the failure mode is a missing badge,
never an invented licence). 24 tests pin guilt AND innocence.

**PROVEN-LIVE on `56101` after the Fly deploy + cache eviction**, with conservation checked
rather than assumed: `licenses[]` **23 → 9**, and the 23 originals all reappear — 9 licences

- 7 `costs` + 5 `documents` + 1 `entity_forms` + 1 `immigration` = 23. The four
  `NIB dan Sertifikat Standar` rows are NOT deduplicated: they are per-scale
  (Mikro / Kecil-Menengah-Besar / Menengah / Mikro-Kecil), legitimately distinct.

**CACHE STEP — do not skip it, and do not sweep it.** `inspect_kbli` caches the assembled
`KBLIDetail` under `kbli_inspect_v2_{code}` with a TTL of up to **30 days**, so a deploy alone
changes nothing on the consuming surface. Every previous cure knew which N codes it touched;
this one changed the response shape for _every_ code with non-permit edges, which is exactly
the case `kbli_inspect_cache_bust.py` refuses to serve (`--only` mandatory, no sweep — by
design). Resolution: **enumerate and measure instead of sweeping** — dry-run all 1,559 codes in
7 chunks (`fly ssh -C` cannot carry a 9,353-char argument), which found **74 codes with a live
entry** (checksum 250×6 + 59 = 1,559), then `--apply` to exactly those 74 → **74/74 evicted, 0
survived**. Declaring `N of M` is the point; a silent sweep reads as "covered everything".
Two traps paid for in this run: `ssh` inside a `while read` loop **eats the loop's stdin**, so
only the first chunk ran and the total would have read "3 of 1,559" as if complete (use
`ssh -n`); and any diagnostic call made BEFORE the deploy writes a 30-day entry holding the
defective payload — `56101` became one of the 74 that way.

**STILL OPEN, and not to be mistaken for cured:** the same answer carries obligations about
_"cara budi daya tanaman pangan yang baik"_ with reporting to the **Minister of Agriculture**,
on a restaurant. That is not a mistyped edge — it lives inside the `kewajiban` property of a
**legitimate** `perizinan` node ("NIB dan Sertifikat Standar", Menengah), which the classifier
correctly keeps. Contamination _inside_ a permit node: different axis, open defect.

**🔴 L2.12 — THE GITHUB `deployments` API MEASURES VERCEL'S _REPORTING_, NOT ITS _DEPLOYING_
— AND THE FRONTEND PIPELINE IS IN FACT DEAD (corrected 2026-07-27, second pass).**
Never conclude "the frontend is / is not live" from `gh api .../deployments`. **That part
stands.** But the reassuring half of this entry — _"nothing is blocked and no operator action
is required"_ — was **WRONG**, and is corrected below. The original retraction is kept because
the probe that produced it is the one every session reaches for first.

Measured: the newest **Production** deployment record is still `13265a2406` at
**2026-07-26T19:57:32Z**, and no record has been created since. Yet the cured string
`13 May 2026 moratorium` — introduced by `45444d21e9` (**23:05:17Z**, the L2.10 block-cause
cure) and `07ab9d6d37` (**23:44:13Z**, #3275) — **is served by prod**, on a freshly rendered
page. So Vercel deployed at least twice after the last record. ~~What broke is the
Vercel↔GitHub reporting integration, not the pipeline; nothing is blocked and no operator
action is required for the product.~~ **← this conclusion was wrong.** Deploys had still
been happening at that hour, but for a reason that guaranteed they would stop: they were
being created **by hand**, by a sibling lane. Nothing automatic was left.

**What is actually true (measured 2026-07-27 10:15-10:40Z).** The **Vercel GitHub App is no
longer installed on the repo** — `GET /v9/projects/mouth` returns **`"link": null`** — so a
push to `main` creates no build at all. Consequence, measured rather than inferred:
`balizero.com/api/health` reported commit `76615aa741` (**05:19Z**) while `origin/main` was
**19 commits ahead**, **5 of them under `apps/mouth/`** — not only #3317 but **#3320**, which
aligns every E33G duration and income claim with the visa rulepack. Since balizero.com and
every subdomain share the single Vercel project `mouth`, the whole public surface was stale.

**The probe that settles it** — three properties, all required:

1. an **origin-computed** route, forced with `?cb=<epoch>` until the headers read
   `x-vercel-cache: MISS` + `age: 0`. A `HIT` says nothing about the running build;
2. a value the fix changes **arithmetically**, not a prose string: `/api/kbli/gold/01122` →
   `pma.maxForeign`, **0** pre-fix (`raw.pma_max_asing || 0`) vs **100** post-fix
   (`resolvePmaCap`, TERBUKA with no cap on the record);
3. **the confound closed first**: `0` would ALSO be the correct post-fix output if the dataset
   carried `pma_max_asing: 0`. Verified across the last 6 dataset revisions — `01122` has
   never had that key (the only one of 1,559 lacking it; the 62 records at `0` are TERTUTUP).
   Only then is `0` diagnostic.

**The valve, and who turns it.** Until the App is reinstalled, frontend deploys are manual —
`POST /v13/deployments` with `gitSource` **then** `POST /v10/projects/<id>/promote/<dpl>`. The
promote is **not optional**: an API-created deployment reports `target: production` and `READY`
while the custom domains still serve the previous build. **The session runs this**, not the
codeowner (SHIP-LIFECYCLE). Executed 2026-07-27: deployment from `d848de6ac5` → READY in 7 min
→ promote HTTP 201 → prove-live `maxForeign` 0→100, `undefined% Open` gone from `/kbli/01122`,
and TERTUTUP codes (`47222`, `11010`) still reading `0` as the innocence control.
GOTCHA: on M5 **both** fly credentials are dead and the `fly`/`flyctl` names are shell
functions with a dead cwd — probe with `scripts/lib/fly_credential.sh`, and run Fly commands
from Pro. Vercel's own token is at
`~/Library/Application Support/com.vercel.cli/auth.json` on macOS, **not** `~/.vercel/`.

**`operator[gui]` — the only irreducible step:** install/authorise the Vercel GitHub App on
`github.com/apps/vercel` → Configure → grant repo access. GitHub does not expose App
installation to a PAT. Tracked in `.claude/skills/modus/PENDING-ARMS.md` (opened 2026-07-27).

**The organism was not silent — it was misrouted.** `Frontend Live Sentinel` (PR #3291)
detected this behaviourally, printed a diagnosis naming the exact valve above, and delivered a
Telegram alert (`Telegram alert delivered`, 08:50:27Z) — **six times** today. It is armed and
correct. But its only recipient is Zero's Telegram, i.e. precisely the party who by contract
does not deploy. An alarm delivered only to the one party barred from acting is delivered to
nobody. When arming an alarm, the question is not "does it fire?" but **"does it reach someone
who can and must act?"**.

**Two traps that made the wrong reading feel solid — both cost-free to avoid:**

1. **`date + age` is not "now".** On HTTP response headers `date` **is** the moment of the
   response; `age` is how long the cached copy has been held. Summing them moves your own
   probe forward in time — here by ~1.5 h, which turned "I sampled 37 min after the merge and
   got a cached pre-merge copy" (normal propagation) into "the render post-dates the merge and
   is still stale" (a stall that never existed).
2. **Two corroborations that sample the same instant are one corroboration.** "API frozen" and
   "page stale" agreed only because both were read off the same wrong moment — they could not
   have contradicted each other. Before trusting agreement, ask whether the second check could
   have failed for a _different_ reason than the first.

**The probe that actually settles it:** `curl` the page and grep for a string your own commit
introduced (`git log -S "<string>" origin/main` gives you the commit and its merge time). Prod
against prod — the same rule already paid for on the Fly side.

**L2.11 — THE PMA CAP WAS A BINARY DERIVED FROM A TERNARY, ON BOTH PLANES (2026-07-27).**
`pma_status` has three values and the code treated it as two, so the foreign-ownership figure
was invented rather than read — even though the dataset already carries the adjudicated one
(`pma_max_asing` + `pma_official_basis` citing the Perpres 10/2021 lampiran + `pma_cap_verified`).

- **Backend** (`services/kbli_eye.py`): `max_foreign_ownership = 100 if TERBUKA else 0` served
  a figure the dataset contradicts on **9 of the 10 TERBATAS codes**, 8 of them in the direction
  that DENIES a lawful stake (the seven sea-cabotage codes `50111/50112/50113/50121/50122/50123/50126`
  allow **49%**; `79110` allows **100%**; `47221` is a non-percentage "special" regime). The
  decision matrix shared the defect: `not TERBUKA -> REJECTED` refused an activity where a PMA
  may lawfully hold 49%. Now keyed on the CAP: 0% stays REJECTED (62 codes), limited-but-open
  becomes WARNING/`PERPRES_10_2021_FOREIGN_CAP`. Exactly **9 codes leave** the REJECTED bucket,
  none enters. `is_umkm_reserved` was `not is_open_pma` — "reserved for micro/small enterprise"
  asserted on all 71 non-TERBUKA codes while the data names it on **2** (`47111`, `47222`, both
  via the lampiran's `DIALOKASIKAN` column); it is now tri-state, `None` = undetermined.
  Note `Kemitraan dengan UMKM/Koperasi` is a PARTNERSHIP duty, **not** a reservation — a bare
  substring match on "UMKM" over-matches it (family #3).
- **Frontend**: the cap was read in two places with different defaults —
  `kbli-data.server.ts` used `raw.pma_max_asing || 0` (the 1,559 static pages + gold API +
  sitemap) while `kbli-data.ts` used it bare (index, sectors, OG). On `01122` (the single
  record with no cap field, TERBUKA) the coercion rendered **"0% Open"**. One resolver now:
  `apps/mouth/src/lib/kbli-pma-cap.ts`, pinned by an INTERACTION test (neither layer may
  re-derive it), with the same narrow status fallback the backend uses.
- **The service had ZERO direct tests** (only downstream mocks) — that is why both survived.
  20 added: guilt on every wrong verdict, innocence on every verdict that must not move, and
  population pins over all 1,559 codes.

**🔴 L2.11b — `KBLIEye` IS DEAD IN PRODUCTION, AND WAS DYING MUTE (`operator[business]` to revive).**
Proven live on `nuzantara-rag` (machine `1781e5eda03438`): `/app/source_documents` **does not
exist** and `python -m backend.services.kbli_eye` returns `{"state": "ERROR", "reason_code":
"DATABASE_NOT_LOADED"}`. The KBLI dataset never enters the image — the Dockerfile's final stage
copies `backend`/`scripts`/`training-data`/`*.py`, never `data/` (repo-root `source_documents`
is a symlink into `data/`, which is not in the build context). So **both** consuming endpoints —
`POST /api/dashboard/map/analyze-investment` and `POST /api/prime/v2/analyze` (called by
`apps/mouth` via `/api/property/analyze`) — have been degrading their whole KBLI block to
`state: "ERROR"` for an unknown period, and `_load_database()` announced it with a **bare
`return`**. The refusal is now logged (family #2: a silent failure is not a failure seen).
**Deliberately NOT revived here** — shipping the 35.3 MB dataset would resurrect a SECOND source
of truth that contradicts the cured one: this service carries its own hardcoded Bali rules
(9 gov-letter codes + 4 moratorium codes) against the navigator's 518-code overlay. The real
choice is (a) ship the dataset and align its Bali rules to the overlay, (b) re-point it at the
Postgres `kbli_documents` store that already exists in prod, or (c) retire it with its two
endpoints. **Nothing renders its payload today** — censused: no frontend reads
`max_foreign_ownership` or `kbli.state`; `DealFlowWizard` renders only `analysis.kbli?.code`,
which survives the ERROR shape via the caller's fallback. So this is latent, not visible harm.

**🟡 L2.11c — THE "UNVERIFIED CAP" QUALIFIER CANNOT RENDER ON ANY OF THE 1,559 PAGES — AWAITS ZERO.**
`page.tsx` has an honest branch — `≈N% (unverified)` — nested inside `status === "restricted"`,
so it needs a TERBATAS code with `capVerified === false`. All **10** TERBATAS codes carry
`pma_cap_verified: True`; the only **2** records with an explicit `False` (`02101`, `03120`) are
TERBUKA and render `"100% Open"`. Net: the qualifier renders on **0 of 1,559 pages** — a
fallback that never fires, which is this project's own signature for "nobody looked at the data".
Meanwhile `pma_cap_verified` is **ABSENT on 1,543 records** and the readers default
`raw.pma_cap_verified !== false` → treated as verified. Note precisely what this does and does
not mean **at the render level**: for `open` codes the page never prints the word "verified" (it
prints `"N% Open"`), so the claim is not "1,543 pages assert a verified cap" — it is that the
catalogue has **no way to say "we have not verified this"**, on a layer the corner itself flags
as vintage-2020 and per-code-unadjudicated (FATAL-2). Making the qualifier reachable = re-labelling
1,543 client-facing pages, which is the FATAL-2 re-label already reserved to Zero (Legge 5).
**Options, none taken:** (a) flip the default so absent = not verified and let the qualifier
speak on 1,543 pages; (b) keep the default and add a distinct third state ("source: blanket
Perpres attribution") so "adjudicated" and "assumed" stop looking identical; (c) leave as-is and
adjudicate the 1,543 first, per-code, so the qualifier becomes true rather than loud.

**🔴 L2.11d — THE CHANNELS ANSWERED E-COMMERCE WITH A RETIRED 2020 CODE (2026-07-27, cured).**
`kbli_notebook_chat.KNOWN_KBLI_CODES` is a hand-written dict consulted when a code misses BOTH
PostgreSQL and Qdrant, and it is also injected by an activity-keyword map — so whatever it says
lands directly in the LLM context answering on WhatsApp and web chat. **Proven live on prod before
the fix**, `chat_kbli("I want to open an online shop in Bali as a foreigner…")` returned
**`KBLI 47911`** with `sources: [{"title": "PP 28/2025"}]` and `pma_status: TERBATAS`.

`47911` is a KBLI **2020** code, retired in 2025 and **absent from the catalogue** (re-verified).
Being absent, it misses both stores _by construction_ — which made this dict its ONLY possible
answer, with no retrieval able to correct it. Same structural blind spot as the phantom-code class
(every cure tool keys off "a canonical record exists"), on a **fifth** surface the phantom census
never covered: a hardcoded dict inside a router. It invented a restriction out of nothing AND
fabricated provenance — a 2025 regulation cited for a code that 2025 deleted.

Cure: repointed to **`47901`** (Platform Digital Intermediasi Perdagangan Eceran, TERBUKA — the
successor citing 47911 in its `pp28_sources`), with the description carrying the **fork** rather
than a replacement certainty: 47901 is the marketplace OPERATOR; a business selling its own goods
online takes the PRODUCT-CATEGORY code and that category's restrictions (`47221` TERBATAS,
`47222` TERTUTUP, most others TERBUKA — all re-verified against canonical). Also `56290`:
hardcoded TERBATAS, catalogue says TERBUKA. The map's own comment asserted the inverse of the
truth — _"prevents wrong codes (e.g. 47901 for online retail instead of 47911)"_ — and that belief
is what put a dead code on the channel. **Structural guard added**
(`test_kbli_hardcoded_fallback_matches_catalogue.py`): any entry naming a code the catalogue lacks,
any PMA status the catalogue contradicts, or any keyword row aiming at an unknown code now fails
CI. Verified to bite — replayed against the old values it flags both.

**🔴 L2.11e — `kbli_documents` CALLS 17 CLOSED CODES OPEN, AND IT IS THE STORE FEEDING THE
CHANNELS.** Censused read-only across the three stores carrying a PMA verdict:

| store                                | TERBUKA | TERTUTUP | TERBATAS | "Verify at OSS" |
| ------------------------------------ | ------- | -------- | -------- | --------------- |
| canonical dataset (1,559)            | 1,488   | **61**   | 10       | —               |
| `kg_nodes` (1,558 carry a PMA layer) | 1,484   | **61**   | 9        | 4               |
| `kbli_documents` (1,563)             | 1,502   | **44**   | 13       | 4               |

_(`kg_nodes` holds **13,491** rows with `entity_type='kbli'` — the known dedup disease; exactly
1,558 of them carry a `pma_status`. Cite that number, not "1,558 nodes".)_

**Canonical and the KG agree on all 61 — verified by MEMBERSHIP, not by count**: the two 61-code
sets are identical, `A − B` and `B − A` both empty. Two same-size sets are not the same set, and
this is the fact the whole "direction is decidable" argument rests on, so it is proven, not
counted. **`kbli_documents` disagrees on 17** — and it is the store
`chat_kbli` injects verbatim into the LLM context. Not an editorial fork: two independent sources
concur and the odd one out is the client-facing one. The 17: `47222` (store says TERBATAS) plus 16
reading TERBUKA — `59111`, `59121`, `85101`, `85201`, `85311`, `85315`, `85550`, `85560`, `86101`,
`86104`, `87201`, `87301`, `91111`, `91121`, `91211`, `91221`. **All 16 are government activities
by canonical title (16/16 carry `Pemerintah`)**: government hospitals and clinics, state
kindergartens, primary and secondary schools, job-training centres, libraries, archives, museums
and heritage sites — presented as 100% open to foreign ownership. Direction is unambiguous, so the
fix is a data-plane sync of `kbli_documents` from canonical, **not** a Legge-5 judgment. Supersedes
the narrower "4 codes claiming openness while `pma_status=TERTUTUP` — AWAITS ZERO": the population
is **17** and the direction is decidable.

**The divergence is not random — it tracks rows that were never re-seeded, and that names the
cure.** Of those same 61 canonical-TERTUTUP codes, **6** are stored in Title Case with the full
canonical title (`01287`, `59131`, `60311`, `85321`, `85401`, `85403`) — re-seeded rows — and
**every one of them carries the correct TERTUTUP**. The other 55 are the original UPPERCASE seed,
and **all 17 divergences live there**, zero in the re-seeded set. So a re-seed from canonical is
already demonstrated to fix both fields, on 6 rows, in production. Corroborating the same story:
**20 of the 61** store titles are strict truncations of the canonical title (word-boundary cut
around ~55 chars), and on 5 of the 16 government codes the cut lands exactly past the word
`Pemerintah` — e.g. `59111` "…DAN PROGRAM TELEVISI **OLEH**", `91221` "…MONUMEN YANG **DIKELOLA**".
The truncation removes the one word that identifies the activity as governmental, so even the title
in the client-facing store has stopped saying what the record means. _(Scope declared, not implied:
truncation was measured exactly on these 61; the rate across all 1,563 rows is UNMEASURED — the
length histogram peaks at 47-52 chars with a max of 104, so a fixed character cap is ruled out.)_

**The cure needs NO code change, and the near-miss is worth recording.** The obvious read is that
`kbli_documents_cure.py` cannot reach these 17 because they lack the `per_skala_disputed_*` marker
— which would call for widening the tool, i.e. a fifth parallel cure path. **That read is wrong**,
measured by running the tool's own decision function against the REAL production rows: the marker
gates only the **`--all-quarantined` sweep selector** (119 codes, none of the 17 among them). The
`--only` path has no such gate — `plan_cure` requires only that the code exist in canonical AND in
the table, and `build_cured_metadata` writes canonical `pma_status` wholesale. Probed on the live
metadata of `86101` and `47222`: cured `pma_status` → `TERTUTUP`, metadata differs → `update_row`
True. **A skip is not an eligibility gate until you have read which selector produced it.**

Exact delta the re-seed would write, measured across all 17 (read-only role, 2026-07-27):

- **17** `pma_status` corrections (16 `TERBUKA` → `TERTUTUP`, `47222` `TERBATAS` → `TERTUTUP`).
- **17** titles rewritten to the canonical Title Case, **5** of which are currently truncated past
  the very word that identifies them as governmental (`59111`, `59121`, `87201`, `87301`, `91221`).
- **12** already-detached rows get `licensing_status` `N/A` → `PENDING_REGULATION` (class-parity
  with the KG cure's marker) — they do NOT lose licensing, they already have none.
- **5** rows (`47222`, `59111`, `59121`, `86101`, `86104`) hold a **one-element** `per_skala` where
  canonical carries 4/4/4/3/4 — the re-seed EXPANDS them; the seed had kept a single scale row.

The **global detached invariant still holds** — re-verified this turn, **0 of the 217** canonical
`per_skala == []` codes serve licensing in `kbli_documents` — so this lot does not re-open the
4th-surface class closed on 2026-07-24; it is a distinct field (`pma_status`) on rows that were
never re-seeded.

**Coverage gap found in the same census (separate, honest-degrading):** 5 canonical codes have no
PMA layer in the KG at all — `01122`, `47721`, `56101` (restaurant in a fixed building), `70201`
(tourism management consulting), `79110` (travel agency). High-traffic Bali activities. The channel
degrades correctly for them (`pma_status` defaults to `"Verify at OSS"`, an honest gap, never a
guess), so this is missing coverage rather than a lie — but a client asking about a restaurant or a
travel agency currently gets no PMA verdict from the KG.

**L2.10 — THE BLOCK-CAUSE WAS A CONSTANT ON SIX RENDER SITES (2026-07-27; four cured by
#3262, the last two by #3275 — the "FOUR" this section first claimed was itself the defect,
see the METHOD NOTE).** Every Bali-blocked page names WHY it is blocked.
The dataset carries **six** distinct blocking statuses (372 `BLOCCATO_CLASSE_RISCHIO` · 68
`TERTUTUP` · 39 `CHIUSO_PMA_NO_BESAR` · 35 `CHIUSO_MORATORIA_BALI` · 2
`CHIUSO_REGOLATORE_SETTORIALE` · 1 `CHIUSO_BALI` · 1 `CHIUSO_BALI_PROPOSTO`), and **not one
render site read the status.** Cured by one total function, `apps/mouth/src/lib/kbli-bali-block.ts`:

| Site                                                                | What it asserted for EVERY blocked code                        | Wrong on                                                                                                                                                                                                                   |
| ------------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `page.tsx` PMA verdict banner (above the fold, 456 pages)           | "reserved for MSMEs"                                           | **417**                                                                                                                                                                                                                    |
| `LicensingSection` national-vs-Bali frame (gold layout)             | "under the 13 May 2026 moratorium"                             | **72** (58 of them next to a spliced reason ending `→ not blocked by moratorium` — the cause and its denial in one sentence)                                                                                               |
| `rewritePmaLineForBali()`                                           | "(reserved UMKM / moratorium)" — two causes at once            | now **cause-free**: it never receives the status, so it asserts nothing                                                                                                                                                    |
| `page.tsx` assistant opening line                                   | "(reserved UMKM / 2026 moratorium)"                            | seeds the CHAT context → a wrong cause here becomes a wrong cause in the answer                                                                                                                                            |
| `kbli-faq.ts` — visible FAQ **and `FAQPage` JSON-LD** (455 answers) | "(reserved for UMKM / 2026 moratorium)"                        | **416** — and this is the copy that LEAVES the site, ingested by search engines. It also spliced `l4_bali.reason` with no `shouldShowReason` gate, so `69104` served Italian into the structured data                      |
| `KBLIProvenancePanel` "Sources & Verification" row                  | `moratorium.rule` as the SOURCE + "derived from the risk tier" | **111** — and `moratorium.rule` is **one identical string on all 1,559 records**, so it can never explain a per-code verdict. Verified on prod: `/kbli/38122` (sector regulator) and `/kbli/11010` (ownership restriction) |

Also cured: Italian reaching client pages (`69104` served _"Notaio/PPAT è ufficio personale e
statale … PMA impossibile"_; marker list **validated against all 518 blocked reasons**, flags
exactly 2 — the first draft included `solo` and would have eaten `86201`/`86202`'s English
"cannot open a **solo** practice"); a proposed closure stated as in force (`79110`, travel
agency); and **8** zero-row pages that walk a client through a licensing route the same page
declares to have "No verified basis" (`72101`, `75001`, `75002`, `75009`, `86109`, `86202`,
`86203`, `91222`).

> **METHOD NOTE, worth more than the fix.** Sites 1, 3 and 4 were found only because the
> PROVE-LIVE probe was run **before** the merge and its CONTROL came back silent: `01192`
> (`BLOCCATO_CLASSE_RISCHIO`) rendered no licensing frame at all — because it has no gold entry
> and takes a different layout. Chasing the control's silence, not the fix's success, exposed
> 417 pages. A control that cannot see what it certifies is worth nothing; **an empty probe
> accuses the selector.** (The probe itself lied twice first: a literal anchor that could never
> match because tag-stripping turns `Bali</strong>,` into `Bali ,`.)
>
> **SECOND METHOD NOTE — the count above was WRONG when first written, and how it was wrong is
> the reusable part.** This section originally said FOUR sites. There were six. Sites 5 and 6
> were found hours later, while chasing an unrelated residual, because the sweep had enumerated
> by **grepping the wording of the site already known** — which finds surfaces that phrase the
> defect the same way and is structurally blind to one that phrases it differently. The
> enumeration was over a FORM, not over the ENTITY "asserts why Bali blocks this code".
> Re-running it by entity (every consumer of `baliL4`/`l4_bali` that emits prose) found both and
> also CLEARED the rest — `KBLIStructuredData` and the OG-image chip are cause-free, verified
> not assumed. Two corollaries paid for in this lot: (a) a surface that **documents itself as
> mirroring another** (`kbli-faq.ts`'s header says its facts come "from … the PMA verdict
> banner") is a site that a cure to that other one BREAKS — curing one put two copies of the
> same claim in contradiction on one page; (b) a field cited as a per-code basis must be checked
> for **distinct-value count** — one value on every record is a layer annotation, never
> evidence, and the give-away is a fallback branch that can never fire.
>
> **A SEVENTH copy exists and is DORMANT** — `apps/kbli-navigator/app/kbli/[code]/page.tsx`
> carries the same sentence verbatim. Deliberately not cured, verified three ways:
> `/kbli-navigator/*` **308**s to `/kbli/*`, its own alias `kbli-navigator-rebuild.vercel.app`
> **404**s, and no workflow deploys it. Declared rather than silently skipped — if it is ever
> revived it starts out wrong.

**RESIDUALS — recorded, NOT built (per Zero 2026-07-25: findings + options into the corner, no
blocking question):**

- **4 codes claim openness while `pma_status=TERTUTUP`** — `59111`, `59121`, `86101`, `91221`.
  Needs per-code adjudication; for the two film codes the vintage-2020 `pma_status` may itself
  be the wrong side of the contradiction. **AWAITS ZERO** (Legge 5 — it is a verdict change).
- **Italian still in the DATA** (`l4_bali.reason` for `69104`, `79110`). Suppression now covers
  all three render sites that splice the reason (licensing frame, banner, and — as of #3275 —
  the FAQ and its JSON-LD), so no client sees it, but the field is still wrong at the source: a
  data-plane repair for a `scripts/kbli_filiera/` compiler, not a frontend one. Note the shape:
  the FAQ had to be found and fixed SEPARATELY even though the gate (`shouldShowReason`) already
  existed — a guard is only applied where someone applied it.
- **`49213`'s canonical prose declares a gap that was resolved 2026-07-18**, and canonical is
  what feeds WhatsApp/RAG, where **no frame exists**. The frontend cure does not reach that
  surface (consumer-map rule).
- **`apps/mouth` is not on the pre-push allowlist** (`scripts/prepush_classify.py`, 9 entries,
  zero mention of `apps/mouth`), so every frontend PR runs the full ~40-min backend suite and,
  under fleet contention, gets SIGTERM'd mid-push. Innocence already measured: no backend test
  reads a frontend file. Guard change → auto-merge OFF. No lane owns it.

**L2 EDITORIAL-HONESTY SWEEP — 2026-07-26. The claims were cured by W1; this lane cures the
LANGUAGE the claims are written in.** Four lots, all driven by `scripts/kbli_filiera/` compilers
with spec-authored exact rules — never a hand-edit, never a regex invented at the keyboard.

- **L2.1** false renumbering / contradicted predecessors / mid-word truncation — PR #3179 MERGED,
  KG arm APPLIED and re-verified through the read-only role (not the applier's own report).
- **L2.2** the licensing disclosure, 152 codes — PR #3181 MERGED, **PROVEN-LIVE**: `/kbli/72201`
  and `/kbli/79909` served 0 occurrences of "Risk tier under review" at the pre-merge baseline and
  serve it after the rebuild.
- **L2.3** `whatChanged` spoke Italian and leaked internal enum tokens — PR #3196 MERGED
  (`9583709d9f`), 576 records (465 canonical + 111 gold), 20 rules, 0 enum tokens on either
  surface. One residue was DECLARED not hidden: `/kbli/46442` still carried hand-written Italian
  editorial prose. **That declaration was two-thirds wrong and L2.6 closed it** — the residue was
  never 1 record (it was 9), and "a template map cannot translate it without inventing it" was a
  false dichotomy: free prose is translatable by literal rule + an independent grader, which is
  exactly what L2.6 did.
- **L2.4** the same leak OUTSIDE `whatChanged` — **38 (record,field) pairs / 40 occurrences** across
  `whatYouNeed` (30), `baliContext` (6), `zantaraOpener` (2), both surfaces. 14 new rules.
- **L2.5** `mapping_note` / `aggregation_note` — PR #3201. `whatChanged` **embeds `mapping_note`
  verbatim**, so L2.3 cured the composed copy and left the SOURCE Italian: ~157 pages rendered an
  English `whatChanged` block and an Italian crosswalk row about the same fact. 88 records served a
  raw Python list literal (`Cleaned: removed invalid ['01272']`) — visible AND in the **FAQPage
  JSON-LD Google indexes**. 443 rewrites, **zero new rules**: every one was already matched by a
  rule written for `whatChanged`; the work was structural (those fields hang off the RECORD, while
  `cure_dataset` iterates the `intel_2026` container).
- **L2.6** the last Italian in `whatChanged` — **9 canonical + 1 gold**, free prose no template could
  reach, 6 of them visible in a `<p>` on prod. Same four `invariato` records were also **cut
  mid-word** in storage. 15 new rules. After L2.6, `whatChanged` is the ONLY field that ever carried
  client-facing Italian and it now carries none.

**L2.6's three findings, none of which are about Italian:**

- **A probe whose vocabulary is smaller than the defect reports a WRONG bound, not a loose one.** The
  compiler printed `residue: 2`; an independent lexical scan of the same field found **9**. Its
  11-token list simply did not contain the words the defect used, and `residue: 2` read as _almost
  done_ for three lots. A bound is only conservative if its vocabulary is at least as large as the
  thing it bounds.
- **The fix for an under-match ships an over-match unless you look for the twin in the same edit.**
  These markers match as SUBSTRINGS and the English word _hereditary_ contains **eredita** — the
  obvious token would have made the probe fire on ordinary English. Anchored to `eredita parte`,
  pinned by an innocence test. (Same shape as W94/W105: the cure re-catching the disease it cures.)
- **Decide per RENDER SITE, and say which of the two you fixed.** 3 of the 9 sit behind a gold record
  that masks `intel_2026` → cured at rest and for the non-page consumers, NOT visibly. 3 others
  (10433/60103/60203) quote the old Italian value inside an English correction notice — that is
  evidence of a correction, pinned as untouched. Same field, same scan, three different verdicts.

**Open (filed, not fixed):** `46411` now reads _"Renumbered/adjusted from KBLI 2020. 46411 is
unchanged."_ — the lead (derived from `status_mapping`) contradicts the tail. Content defect, needs a
crosswalk adjudication, deliberately not resolved under a translation PR.

**Four findings from L2.4 that generalise past KBLI — this is the part worth re-reading:**

1. **The two surfaces do not share a field distribution.** The first census measured CANONICAL and
   extrapolated to gold; gold leaks in `zantaraOpener`, canonical never does. Caught only because a
   prod baseline curl showed `BPS_ONLY` on `/kbli/72201`, a code absent from the population list.
   Gold MASKS `intel_2026` on the page (`goldEntry ? {…} : {…}` is a mask, not a merge), so a
   gold-only leak is a RENDERED leak. Measure each surface; never extrapolate.
2. **The residue probe was blind twice, in two different ways, and both were self-inflicted.**
   First it stripped quoted spans with `'[^']*'` — which in English prose is not a quote stripper
   but a PROSE stripper, because `'` is the possessive apostrophe: in `82400.baliContext` the one in
   _"Bali's"_ paired with one 468 chars later and swallowed a real leak, reporting CLEAN. Then, once
   bounded, it still exempted _immediately_-quoted tokens as "citations" — but the single such token
   in the whole corpus was scare-quotes around an identifier in client prose, not evidence. **How
   both surfaced: the rules fired more often than the probe had found targets. A firing with no
   matching finding means the FINDER is blind, not the rule greedy.** Chase that gap; never
   reconcile it by assumption.
3. **Shape is not entity — third instance in this lane.** The probe defined an internal symbol as
   `SCREAMING_SNAKE`, and the catalogue's most common one, **`OK_or_HIGHER_RISK`**, has a lower-case
   `or`. Three client-facing prose leaks (84111/84144/84146) hid behind that assumption. The probe
   now recognises symbols by NAME, mirroring `apps/mouth/src/lib/kbli-status-labels.ts`, with the
   shape kept as a fail-closed catch-all — and a test parses that TS file so the two cannot drift.
4. **A guard whose GUILT depends on production still being broken deletes itself the day you fix
   production.** `kbli-internal-leak.test.ts` proved the render-layer cure worked by asserting the
   raw gold file still leaked. L2.4 fixed the data; the guard went red without any regression. Guilt
   moved to a fixture; the live file now carries the stronger claim (clean at rest AND after
   render). The new `zantaraOpener` test made the identical mistake twenty lines below the comment
   warning against it — recorded because that is how easy it is.

Also: the naive `FIELD` → `FIELDS` widening was **rejected on measurement**. Over all 7,641
(record,field) pairs of the new fields the rules fire 10 times while `cure_text`'s trailing
whitespace-collapse mutates **184** records with no leak at all — markdown indentation in
`whatYouNeed` is structure. Normalisation is now per-field and a record is written back only when a
rule fired; both pinned by tests that go red under mutation.

**Still open (ledger, not lost):** `kbli_documents` — the 4th surface — never received the L2.2
disclosure: 152 disclosed / 119 marked / **98 curable**, 54 structurally outside the tool's scope.
BLOCKED because no machine in the fleet currently holds a Fly credential that can see
`nuzantara-rag` (M5 none · Pro's token scoped to `nuzantara-postgres` · Mini, the only good one, is
down and unreachable from both). Also open: Qdrant `whatChanged` re-index needs `--only` on
`index_kbli_gold_content.py`.

**Method note:** a curl PROVE-LIVE on `/kbli/<code>` proves the DATA, not the RENDER —
`LicensingSection.tsx:16` loads `react-markdown` with `ssr: false`, so the server HTML carries raw
markdown and `**bold**` in a curl is expected, not a leak. A visual check needs a browser.

---

**RENDER-TRUTH PASS — 2026-07-25. Two defects found by PROBING THE LIVE PRODUCT, both invisible to
every existing gate, both measured on the real data before a line was written.**

**(a) The catalogue spoke pipeline at its clients.** `intel_2026.editorial` was authored by an LLM
NARRATING THE JSON RECORD, so internal symbols reached readers verbatim: **`Bali status:
OK_or_HIGHER_RISK` on 908 "By the numbers" cells across 1,141 codes (73% of the catalogue)**, +725
occurrences inside editorial prose, +8 in `l4_bali.reason`, +**113 of the 428 GOLD codes**. Cured at
RENDER (`apps/mouth/src/lib/kbli-status-labels.ts`) by resolving each symbol to the label
`BaliStatusBadge`/`TransitionBadge` already used — the labels existed, they were simply unreachable
from the editorial renderer. **Presentation only: symbol and label denote the same verdict, no fact
moved.** Deliberate non-targets, both test-pinned: **TERBUKA/TERTUTUP/TERBATAS stay Indonesian**
(terms of art the product teaches), and **`_data_note` stays verbatim** (there a symbol is a CITATION
of the record used as divergence evidence — rewriting evidence corrupts the audit trail).
Coverage is a **deny list** (walk everything, skip only `_l3_regen` + `coverImage`), so a field added
tomorrow is covered by default. Gate `kbli-internal-leak.test.ts` measures BOTH data files and also
**ratchets a SEPARATE debt it cannot fix: 392 codes narrate raw field names** ("l4_bali_blocked is
false", `pma_max_asing`) — that class needs an editorial rewrite (W5), and the ratchet only falls.

> Cross-family gate (Kimi K3, generator≠grader) returned **2 real BLOCKERs**, both re-measured on disk
> before acting: the gold layout renders `gold.*` DIRECTLY from `getGoldContent()`, bypassing the
> loader cure entirely; and the first gate was blind to that very file. Cured at the `getGoldContent`
> choke point (covers the page + `/api/kbli/gold/[code]` at once).

**(b) 95 codes CERTIFIED a Bali verdict derived from a basis the same record calls unverifiable.**
`l4_bali.confidence` MEDIUM/HIGH + `needs_review:false` while `per_skala == []` — **24 of them
`blocked: true` at HIGH confidence**, i.e. the page tells a client "a PT PMA cannot register this in
Bali", stated as settled, on a detached risk tier. Cured with the ALREADY-SANCTIONED wave-1 treatment
(`cure_l4bali_disclosure.py`: confidence→LOW, needs_review→true, reason disclosure-wrapped with the
original preserved verbatim; **`status` and `blocked` are NEVER touched** — flipping either is a
re-derivation that needs the true tier, F15). Spec `cure_specs/l4bali_gap_disclosure_2026_07_25.json`
(95 codes), emitter `emit_l4bali_gap_disclosure_spec.py`, structural predicates shared with the writer
in `_l4bali_basis.py`. Applied + content-verified on **all FIVE dataset copies** (canonical, mouth,
kbli-navigator, and the two gitignored backend-rag copies the sync script also writes); catalogue-wide
disclosed count 57 → **152**.

> **The cross-family gate (Kimi K3, generator≠grader) earned its keep — 4 of its 5 findings were real,
> each re-verified on disk before acting (W65), and one was refuted with evidence:**
>
> 1. **A THIRD shape of dead basis, invisible to the wave-2 selector — found, cured.** `per_skala == []`
>    is itself a PROXY for "the basis is gone", and PR #2921's `partial_detach` primitive breaks it:
>    rows survive while the tier the verdict cites does not. **`93114`** read `APERTO_BALI_RISCHIO_ALTO`,
>    `blocked:false`, **HIGH confidence**, reason _"the Besar scale is 'Tinggi'"_ — with NO Besar row
>    left in the record (the tier lives in the disowned block). It failed in the PERMISSIVE direction:
>    the page told a client the code IS registrable by a PT PMA. Cured via a new `detached_tier` basis
>    that re-derives the status from the surviving rows with the SAME function that wrote it
>    (`resolve_kbli_l4_needs_review.besar_risk`) and fires only on a mismatch. Catalogue-wide census of
>    the class: 3 partial detaches (`49213`, `93114`, `93191`), exactly 1 inconsistent.
> 2. **A client-facing sentence asserted an HTTP status we never observed — rewritten.** The first
>    `no_oss_scope` suffix said _"(the scope endpoint returns 404)"_. `_l2_status = no_oss_risk` is
>    written by `build_kbli_l2_oss_risk.py:163` for a MISSING dump line, ANY non-200, **or**
>    `success:false` — asserting `404` inside the sentence whose whole job is honesty is the disease
>    itself (F12). Now: _"could not be retrieved from the OSS API when this dataset was built"_.
>    **CORROBORATION RE-SOURCED 2026-08-02 — the citation used here was not evidence.** This line used
>    to cite `KBLI_2025_OSS_GROUND_TRUTH.json` `_meta` (`ruang_lingkup_no_scope: 221`,
>    **`ruang_lingkup_errors: 0`**). That counter cannot corroborate anything: the per-record schema of
>    that file has **11 keys and not one of them is an HTTP status**, and `_rl_status` has a vocabulary
>    of exactly **two** values (`ok` 1338 / `no_scope` 221) — there is no slot in which an error could
>    have been recorded, so "0 errors" is unfalsifiable by construction. Worse, the code that wrote
>    those labels **does not exist in this repo** (`_rl_status` and `ruang_lingkup_errors` appear only
>    in the data file and in this corner), and the raw dump its consumer reads is
>    `RAW = Path("/tmp/oss_risk_raw.jsonl")` — **gone**. A frozen measurement whose producer nobody can
>    re-run (#9/W106) cited as proof of what a government API said.
>
>    **The real evidence is the vault, and it is stronger than what this line claimed.**
>    `scripts/kbli_filiera/vault_fetch_oss.py` records status per probe (its docstring states the
>    contract: _"a 404 on ruang-lingkup … is a LEGIT no-scope signal … NEVER as an empty file
>    pretending to be data"_). `~/nuzantara-vault/oss/absences.jsonl` holds **663 ruang_lingkup
>    absences = 221 distinct codes × exactly 3 attempts each, every one HTTP 404**. And the two
>    instruments agree **by MEMBERSHIP, not by count** — the old file's 221 `no_scope` set and the
>    vault's 221 404 set are identical, `A−B` and `B−A` both empty (two same-size sets are not the same
>    set; this is the fact the whole "the emptiness is observed" argument rests on, so it is proven).
>    Independent schema, independent run, independent date.
>
>    **What that does and does not license.** It licenses saying the emptiness is OBSERVED at OSS
>    rather than caused by us. It does **not** license the client-facing sentence naming a legal
>    consequence: a 404 is SILENCE, not a statement that the activity cannot be licensed at Besar.
>    And by this repo's own D0 discipline (≥3 attempts over ≥**72h**,
>    `research/operations/2026-07-16-kbli-filiera-methodology.md`) the corroboration is **partial**:
>    the three probes span `2026-07-16T16:52Z → 2026-07-17T15:48Z` ≈ **23 hours**, which rules out a
>    transient blip, not a multi-day publishing outage. Declared, not rounded up.
>
> 3. **Wave 1's disclosure sentence narrated two JSON keys at clients — migrated catalogue-wide.** It
>    read _"detached to `per_skala_disputed_pp28_collision` (see `_data_note`)"_, and `kbli-faq.ts:42`
>    splices that verbatim into a published FAQ answer. Fixing only the new codes would have shipped a
>    half-fixed class + two dialects, so `--reword-legacy` migrated **all 57 wave-1 records** too.
>    Now **0 of 1,559 verdict sentences name a pipeline field**, pinned by a test that measures the
>    live catalogue. The key is not lost — it stays on the record, in `_data_note`, and in the spec.
> 4. **Editorial residue is now declared instead of silent.** `_meta.editorial_residue` records that
>    **95 of 95** cured codes still carry `intel_2026` prose stating a risk tier as FACT ("as a
>    medium-high/high-risk activity"), so on those pages the article body and the badge now disagree.
>    The cure deliberately does not touch editorial prose; wave 1 flagged this class and wave 2 had
>    dropped the practice.
> 5. **REFUTED with evidence — `93111`/`93112`/`93119`/`93191`.** The gate called these false negatives
>    (they carry `_l2_status: no_oss_risk` AND a surviving row). They are NOT: each has
>    `pp28_sources` populated (a declared PP28 locator) and their stored verdict still follows from the
>    row they keep — and all four were adjudicated by the signed Batch-A Lot-8/9 gates. Their real
>    exposure is the PP28 **vintage-2020** axis (FATAL-2), already tracked catalogue-wide — not this
>    wave. Recorded here so the next session does not re-derive it.

> **META-PATTERN — THE SELECTOR IS THE DISEASE (THIRD sighting in one session; this is now a rule).**
> Wave 1 cured 57 of these and left 94 not because it failed, but because **it selected on a MARKER
> (`per_skala_disputed_*` present) instead of on the STATE (the layer this verdict derives from is a
> declared gap)** — so 54 codes detached without ever receiving a marker were not skipped, not
> reported, simply **unreachable by the tool**. This is the exact shape already recorded in this
> corner for the PHANTOM CODES ("every cure tool keys off _a canonical record exists_ → a code living
> only downstream is unreachable by all of them"). **RULE: every cure tool must state whether its
> scope is 'records carrying marker X' or 'records in state Y', and prefer the STATE.** A marker is
> an artefact of which lot happened to touch a code; the state is the defect.
> **And the wave-2 selector fell into it too, one level down** (found by the adversarial gate, not by
> us): `per_skala == []` is ITSELF a marker standing in for the state "this verdict's basis is gone".
> A partial detach leaves rows behind, so the marker reads INTACT while the cited tier is gone — 93114.
> The cure for a proxy is to ask the question the proxy was standing in for: **re-derive the verdict
> from what the record holds NOW, with the same function that wrote it, and compare.** That is
> `_l4bali_basis.status_matches_surviving_rows`, and it is deliberately restricted to the three
> statuses whose derivation is TOTAL in `besar_risk` — the other three come from a different pass
> (lowest tier across all scales), so re-deriving them here would manufacture false mismatches.
> Undecidable is recorded as undecidable, never as clean.
> The wave-2 selector is structural — `l4_bali.status` enum identity + a dead-basis shape + a
> corroborating signal — and **fails loud on an unclassified status** rather than guessing (an
> unclassified enum cannot be known to derive from the detached layer). It deliberately EXCLUDES
> TERTUTUP/TERBATAS/CHIUSO_REGOLATORE_SETTORIALE: those derive from `pma_status` or a sector
> regulator, bases that are intact, so disclosing a derivation defect there would itself be false.
> (Corrective note for anyone reading an earlier draft: a first prose-based count said "134 codes /
> 64 blocked". That over-counted by matching risk words in the reason of PMA-derived verdicts. The
> structural number is **95 / 24** — 40 disputed-key + 54 no-OSS-scope + 1 partial-detach. The spec
> file IS the census; a number that lives only in prose rots, so a test now pins it to the artefact.)

**⚠️ AWAITS ZERO (Legge 5) — three linked editorial calls, investigation CLOSED, no cure past the gate:**

1. **17 codes attribute to OSS an observation OSS never served, client-facing, at `blocked: true`.**
   Their reason reads _"OSS has no Usaha Besar scale row → a PT PMA is barred"_ — and **7 of the 17 go
   further and enumerate _"(only Mikro/Kecil/Menengah)"_**. But all 17 (verified on canonical, this is
   the whole `CHIUSO_PMA_NO_BESAR` slice of the wave: `47771 52211 70100 91424 93115 93121 93122 93123
93125 93126 93128 93129 93192 93194 93195 93197 93199`) carry `_l2_status: no_oss_risk` — OSS
   returned **no scope at all** — plus a disputed key: their ONLY scale rows ever lived in the
   **disowned PP28 vintage-2020 block**. Two different sentences are in play and they do not fail the
   same way: _"OSS has no Besar row"_ is trivially TRUE when OSS serves nothing (though the reader
   hears "OSS says UMKM-only", which is not what a 404 says), while the enumeration _"only
   Mikro/Kecil/Menengah"_ is **unsupportable** — it is a positive claim about rows OSS never served,
   read off the repudiated block. The wave-2 cure DISCLOSES all 17 (confidence LOW + needs_review) but
   does **not** rewrite the sentence: correcting a client-facing claim is editorial.
   **Decision needed: rewrite (and to what — "OSS serves no scope for this code" vs the current
   UMKM-reserved framing), or leave it disclosed as-is?**
2. **May a verdict stand at all once its basis is disowned?** 24 codes now read "blocked, low
   confidence, needs review". The conservative posture (F15) says keep the block; the honesty
   contract says we are asserting a commercially decisive NO on data we do not trust. **And it cuts
   both ways**: `93114` asserts the OPPOSITE — `blocked:false`, _"Registrable by a PT PMA in Bali"_ —
   on a tier equally disowned. A client acting on a wrong NO loses an option; a client acting on a
   wrong YES spends money on a company that cannot be licensed.
   **Options: (i) keep the verdict + disclosed [current, shipped]; (ii) flip to NON_CLASSIFICABILE
   like the 8 pilot codes; (iii) keep it but suppress the verdict from the hero badge.**
3. **RECORDED, not a pending decision — a prior signed classification was falsified by the data.**
   The wave-1 test listed `47771`, `52211`, `70100` under CLEAN_CODES ("clean structural", asserted
   byte-unchanged) on the belief that their verdict rests on a structural OSS observation independent
   of the risk tier. The evidence in (1) refutes that belief. They were RECLASSIFIED in this ship —
   moved out of CLEAN_CODES into `WAVE2_RECLASSIFIED_FROM_CLEAN` with a new test that pins both the
   reclassification AND its evidence (`_l2_status == no_oss_risk`, `per_skala == []`, disputed key
   present, disclosure marker present, `status`/`blocked` unchanged, original reason preserved). Noted
   here because a signed classification being overturned by later evidence is exactly the thing that
   must never happen silently — it belongs in the corner even though nothing awaits a ruling.

**L2.1 — `whatChanged` PROVENANCE PASS: CURED on both in-repo surfaces (PR #TBD, 2026-07-25).
The field had THREE live vintages, not one.**

Censused on every surface that serves it, `intel_2026.whatChanged` carried three defects:

|                              | canonical | gold | KG (`kg_nodes.properties`) | `kbli_documents`          | Qdrant                   |
| ---------------------------- | --------: | ---: | -------------------------: | ------------------------- | ------------------------ |
| A false renumbering claim    |         4 |    1 |                          4 | —                         | inside the embedded text |
| B mid-word truncation @216   |        13 |    2 |                         13 | —                         | inside the embedded text |
| C contradicted predecessor   |         4 |    1 |                          4 | —                         | inside the embedded text |
| population holding the field |     1,559 |  428 |                      1,554 | **0 — verified negative** | 428 `doc_type=kbli_gold` |

**`apps/mouth/data/kbli-gold-all.json` WINS over canonical on the rendered page.**
`kbli-data.server.ts::transformCode` takes `whatChanged` (and `whatItMeans`/`whatYouNeed`/
`zantaraOpener`/`youllAlsoNeed`; `baliContext` only if the code is NOT blocked or the gold text does
not read as a foreign-ownership go-ahead) from gold whenever an entry exists, and
`app/kbli/[code]/page.tsx:428` renders `gold.whatChanged` directly. **Curing canonical alone changes
nothing a client sees for those 428 codes** — and a canonical-only immune organ proves nothing.
Standing rule for every future editorial cure: say which of the two files you wrote, and put the
organ on the surface that WINS. The canonical was in the data-plane registry and gold was not — the
guarded file was the one that loses; `kbli-gold-all.json` is now registered too.

- **C is the shape that inverts a client's decision.** `46415`/`46496` said _"→ KBLI 2025: 46415
  (confermato). Verifica e aggiornamento NIB"_ — _your code carried over unchanged_ — while
  `status_mapping` is `CODICE_RINUMERATO` and the layers record a DIFFERENT 2020 origin.
  `49296`/`64210` named `49299`/`64190` while the layers hold `49424`/`64200`.
  **Cured by DELETION, never by correction:** on 46415 the layers disagree with each other
  (pp28/`kbli_2020_source` = 46694, BPS = 46419), so substituting "the right number" would be us
  picking a winner and publishing it as fact. The replacement names every code our layers DO hold
  and declares the mapping unconfirmed. **Which layer is true is an open source adjudication** for
  46415 / 46496 / 49296 / 64210 (PENDING-ARMS).
- **B cannot restore what was lost.** 13 texts were cut mid-word at exactly 216 chars; the trim drops
  the fragment only. `46411` and `46631` are left with almost nothing (46631 = its opening sentence
  alone) — named on every run rather than discovered on the page; restoring prose is editorial.
- **8 gold codes have no canonical record** (`64921`, `85300`, `85491`, `85499`, `85600`, `86903`,
  `96120`, `96130`). Inert — `generateStaticParams` iterates canonical and `dynamicParams = false` —
  but this is the phantom class on a 5th store, so it is pinned by a test.
- **One decision function** (`scripts/kbli_filiera/_whatchanged_basis.py::plan_text`) serves all three
  surfaces; gold carries no crosswalk fields, so gold is judged by the CANONICAL record. The KG
  applier (`backend/scripts/kg_whatchanged_cure.py`) holds NO logic — it consumes a compiler-emitted
  spec whose entries pin `md5` of the text the decision was made against, and refuses to write on
  drift.
- **Innocence measured on real data:** of the 45 KG nodes opening with the template sentence, **28
  are deliberately untouched and every one really does record a predecessor — 0 misses.**

**NEXT AFTER THIS — L2.2, `whatYouNeed` on gapped codes. RE-MEASURED STRUCTURALLY 2026-07-26 —
the "~41 from prose" figure is RETIRED, and the finding it was hiding is bigger than the number.**

Re-run with `_l4bali_basis.gap_basis()` as the selector (structural, as this section previously
demanded) instead of prose matching:

|                                             |                                                                                                                                                                                                         |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| gapped population                           | **218** — not 217. `disputed_key` 116 + `no_oss_scope` 101 + `detached_tier` 1. The 218th is the partial-detach case, which still has surviving rows and so is invisible to a `per_skala == []` filter. |
| carrying `_data_note` (cured)               | **117**                                                                                                                                                                                                 |
| cured set vs `disputed_key`+`detached_tier` | **SET-IDENTICAL**                                                                                                                                                                                       |
| `no_oss_scope` codes ever cured             | **0**                                                                                                                                                                                                   |

**That is the finding.** The `whatYouNeed` cure's scope was the disputed-key class; the **101
`no_oss_scope` codes were never in it at all** — not partially cured, never selected. Of those 101:
**43 name a risk tier with no gap language**, 44 are clean descriptive prose, 14 already disclose.

The old "~41" was numerically close to 43 by coincidence, off the wrong population, and its
approximate-ness masked a scope hole rather than a counting error.

**The worst shape, verified in full on `79909`:** the record carries `_l2_status: no_oss_risk`,
`_l2_source: null`, `per_skala: []`, `kategori_risiko: null` — OSS returned **no risk scope at
all** — while the client-facing text says _"its **OSS risk class** at the large-enterprise (Besar)
scale **is** medium-high or high"_ and concludes _"A PT PMA can pursue this code in Bali, subject to
the standard licensing for its risk class."_ It attributes to OSS a classification OSS never
returned, then builds a go-ahead on it. Same family as L1.2.

The 43: `65123 72201 72202 79909 84113 84122 84130 84144 84146 85103 85104 85204 85314 85317 85318
85581 85582 85583 85584 85586 85587 85589 87101 87102 87202 87302 87991 87992 87993 88101 88902
88903 88904 88905 91421 91423 94110 94121 94122 94910 94990 97000 98100`.

**META-PATTERN, third sighting — the selector is the disease.** Every cure in this programme has so
far selected on a MARKER or a PROXY of the state rather than on the STATE: wave 1 on
`per_skala_disputed_*`, wave 2 on `per_skala == []` (defeated by a PARTIAL detach), and this one on
the disputed-key class (blind to `no_oss_scope`). Each time the population the tool could _see_ was
a strict subset of the population that was _sick_. The cure is to re-derive the state with the same
function that wrote it — which is exactly what `gap_basis()` is for, and what L2.1's
`_whatchanged_basis.plan_text` does for its own three passes.

**Cure shape is NOT mechanical — and "surgical clause removal" is RULED OUT, measured, not
assumed.** Unlike L2.1 pass A these are not a template sentence, and a compiler must not author
replacement prose (the constraint that left `46411`/`46631` thin). The obvious fallback — delete the
tier-asserting clause and append a recorded gap sentence — was tested against the 43 and does not
survive: **40 of 43 are WELDED**, i.e. the tier claim shares its sentence with a fact the reader
still needs (PMA openness, moratorium status, `TERTUTUP`/`TERBUKA`). The 3 the check called
"separable" are welded too on reading — the predicate just missed them. Structure: 32 records carry
1 tier-sentence of 2, 9 carry 1 of 3, 2 are a single sentence. Deleting the clause mangles the
paragraph; deleting the sentence removes facts the page is right to state. Example (`79909`):

> _"Nationally this activity is open to foreign ownership, and in Bali it is NOT blocked by the
> 13 May 2026 moratorium — **its OSS risk class at the large-enterprise (Besar) scale is medium-high
> or high**, which the moratorium leaves open."_

**So L2.2 is an EDITORIAL lane, not a compiler lane** — same bucket as the 95 tier-asserting texts
and the 392 field-name narrations already in PENDING-ARMS, generator≠grader mandatory.

**PROVENANCE VERIFIED — and it hands L2.2 a fully structural selector.** The hypothesis was "the
tier is an orphan of the detach". Measured against `l4_bali`, the truth is sharper:

| `l4_bali.status`    | n   | confidence / needs_review | `still_certifies()` |
| ------------------- | --- | ------------------------- | ------------------- |
| `OK_or_HIGHER_RISK` | 38  | `LOW` / `true`            | **False**           |
| `TERTUTUP`          | 5   | `HIGH` / `false`          | True                |

For **38 of 43 the L1.2 cure ALREADY RAN**: the structured verdict is disclosed, its `reason`
literally begins `[derivation under review]`, and the record no longer certifies it. **It is the
`whatYouNeed` prose that still narrates that same verdict as settled fact.** So this is not an
orphaned derivation — it is **the cure landing on the field but not on the prose that narrates the
field**, the same shape as "the rendered surface is not the guarded surface".

That gives L2.2 the structural predicate it was missing, with no prose matching anywhere in the
selection: **`gap_basis(record) is not None` AND `still_certifies(record["l4_bali"]) is False` AND
the prose asserts the verdict** — and only that last conjunct needs text, exactly as L2.1's pass A
uses its template only to LOCATE the sentence, never to decide membership.

It also splits the population honestly: the **5 `TERTUTUP`** records still certify (`HIGH`/`false`)
and are a different subcase — nationally closed, so the Bali tier is moot rather than unsupported.
Do not sweep them in with the 38.

Residual editorial need is now much smaller than a rewrite: since `l4_bali.reason` already carries
the agreed hedge, the prose cure may be an **appended recorded sentence** (the move passes A and C
already make in L2.1) rather than authored replacement prose — which is what "welded" ruled out.
Still generator≠grader, and still not started here.

**GROUND CLOSED 2026-07-26 — and it supersedes the 43/38/5 numbers directly above.** Those were a
slice, measured through an ad-hoc selector. The repo already owns this lane, and reading it changes
the answer. `python3 scripts/kbli_filiera/emit_l4bali_gap_disclosure_spec.py --census` today reports
**`IN SCOPE 0` / `already_disclosed 151`**: the FIELD layer is finished catalogue-wide, and that
emitter's own docstring already draws the boundary — _"this spec does NOT touch editorial prose — it
only discloses l4_bali"_ — with a `_meta.editorial_residue` counter for exactly this gap. **L2.2 is
that tool's declared follow-up, not a new discovery. Build on it, not beside it.**

| the population that matters                                | n       |                                                           |
| ---------------------------------------------------------- | ------- | --------------------------------------------------------- |
| records whose `l4_bali.reason` carries `DISCLOSURE_PREFIX` | **152** | `disputed_key` 97 · `no_oss_scope` 54 · `detached_tier` 1 |

by `l4_bali.status`: `OK_or_HIGHER_RISK` 90 · `CHIUSO_MORATORIA_BALI` 33 · `CHIUSO_PMA_NO_BESAR` 17 ·
`APERTO_BALI_RISCHIO_ALTO` 11 · `TERTUTUP` 1. (PENDING-ARMS' "95 of 95" is stale too — the wave grew.)

**And the third conjunct above — "the prose asserts the verdict" — has to go.** No matcher can carry
it. The emitter's own `_TIER_CLAIM_RE`, run over every `intel_2026` field, flags **152 of 152** — a
discriminator firing on 100% of its population discriminates nothing, and its author knew, commenting
it _"Bookkeeping only … NEVER used for selection"_. A strict hand-built matcher over `whatYouNeed`
flags **19** and demonstrably misses real assertions (`"Bali classifies it as medium-high risk"`,
`"has a medium-high risk classification"`, `"falls under higher-risk scrutiny"`), while
over-matching the L1.2 cure text, which itself contains the words "risk tier". Stripping
disclosure-bearing sentences first does not separate them either. **19 ≤ truth ≤ 152, and no pattern
closes the gap — so stop trying to select the asserting subset.**

**Design consequence:** append to **all 152, unconditionally**, exactly as the field layer was cured,
idempotent via a marker the cure writes itself (nothing on a record says "prose already disclosed" —
`_l3_regen` records how prose was generated, `_data_note` is data-layer). The asymmetry decides it:
appending a true sentence to a page that never asserted the tier is harmless; missing one that did is
the client-facing defect. Host = a **new sibling compiler** under `scripts/kbli_filiera/`, NOT
`cure_l4_editorial.py`, whose contract is spec-authored exact-substring replacement over 8 codes and
which promises it "NEVER invents a value" — 152 authored old/new pairs is precisely the LLM
re-authoring this lane rules out.

**SUPERSEDED CENSUS (kept for the correction it records):**

- **4 codes assert a KBLI-2020 renumbering with NO recorded predecessor anywhere.** `64995`, `85691`,
  `85692`, `90113` — `status_mapping: BPS_ONLY`, `pp28_sources: []`, `kbli_2020_source: null` **and
  `bps_2020_ancestors: null`** — yet their `whatChanged` opens with _"Renumbered/adjusted from KBLI
  2020."_. `64995` contradicts itself inside the same paragraph: _"Renumbered/adjusted from KBLI 2020. Codice completamente nuovo in KBLI 2025"_. FACTUAL defect (a provenance claim nothing in the
  record supports), curable by a `scripts/kbli_filiera/` compiler — and the honest replacement is
  _"no KBLI-2020 predecessor is recorded for this code"_, **never** _"new in 2025"_: absence of a
  crosswalk row is not evidence the activity did not exist (that inference is how this class of
  defect is born).
  > **Correction, and why it matters:** an earlier pass in this same session listed **8** codes here.
  > Re-measured on the live canonical after Batch-B's `bps_2020_ancestors` populate landed
  > (2026-07-24, #3082), **4 of those 8 now DO carry a BPS ancestor with a lampiran locator** —
  > `65121→65121`, `85571→78421`, `85693→74321`, `85694→74322` — so their claim is plausibly TRUE
  > (85571's own text already said "Migrated from KBLI 78421"). Their residual issue is a lesser one:
  > `adjudication_status: mechanical-only` / `inheritance_verdict: not-adjudicated`, i.e. the prose
  > states as settled what the record marks as un-adjudicated. A census taken before a sibling lane
  > lands is stale by the time you cure it — re-measure at cure time, never cite the old number.
- **215 `whatChanged` texts mix Italian into client-facing English** (not "10" — that earlier figure
  was a sample read as a population, W97). Two shapes: an English sentence with `"PP28 usa
c[odice]…"` appended, and fully-Italian ones like `"KBLI 2020→2025 mapping: codice rinumerato."`.
  This is editorial, not factual, and belongs to the same editorial-rewrite lane as the 95 tier-
  asserting texts + the 392 field-name narrations (all three tracked in modus PENDING-ARMS).

**W2 / BATCH-B IS UNDERWAY (the "W2 NO-GO" line further down is STALE — Zero gave GO and it has shipped
in mechanical, additive increments).** Chain so far, all merged + proven:

- **Phase-0 gate — SHIPPED (PR #3080, PASS).** BPS 2020↔2025 crosswalk parser + acceptance gate; relation
  digest `ca9e7ffc`, P=R=1.0 on 211 edges; Kimi red-team → 4 fixes. (item-10 Tier-4 AQL default **0.010%
  still awaits Zero's Legge-5 ruling** — the one true open Zero-gate on the mechanical pipeline.)
- **Step 2 — populate SHIPPED (PR #3082, squash `e9f71479`).** Additive canonical field
  `bps_2020_ancestors` written **mechanical-only** onto the **1,338 OSS-native** codes (`_l2_status is
null`); Batch-A's 221 untouched. `inheritance_verdict` always `not-adjudicated` — mechanical presence
  NEVER implies regime transfer. Gate-content-bound (recompute `_relation_digest`), additive-proven 2 ways.
- **Step 4 — SURFACE SHIPPED + PROVEN-LIVE (PR #3095, squash `bc52c788`, 2026-07-25, apps/mouth only).**
  New labeled **"BPS crosswalk"** element on `/kbli/<code>` rendering the field — the FIRST runtime reader
  (was dormant). **Zero chose "additive: new BPS element (safe)"** over re-pointing the legacy `previousCodes`
  (a data-audit proved re-point unsafe). Diff **153 insertions / 0 deletions** → legacy "Previous codes"
  BYTE-UNTOUCHED, zero regression. Honest framing verbatim on prod: _"provenance only, not a licensing
  claim: the regulatory regime of these predecessor codes has not been adjudicated as transferring."_
  **Cross-family gate (generator≠grader; Kimi K3 — Codex 401-dead) CAUGHT A BLOCKER**: the first draft
  LINKED each ancestor to `/kbli/<c>`, but ancestors are KBLI-**2020** vintage while `/kbli/<c>` is a **2025**
  page — verified on real data, **317** ancestor codes coincide with an UNRELATED 2025 code (wrong-vintage
  link = client harm; `KBLI2020:X ≠ KBLI2025:X`). Fix: **ancestors render as PLAIN TEXT, never linked.**
  Proven live on the collision case `01138` (ancestor `01283` = `<span>` plain text, **0** `<a href=.../kbli/01283>`
  on the page). Detail: memory `ops_kbli_batch_b_step4_shipped_2026_07_25`. GOTCHA: `/kbli` pages are
  **SSG+ISR** — `?cb=` does NOT force a fresh render, so a stale edge-cache can serve an old prerender for
  minutes (seen on `01111`); not a gate (twin `01118` renders its self-code fine).

**⚠️ OPEN FINDING surfaced by step 4 — AWAITS ZERO'S EDITORIAL RULING (Legge 5).** Step 4 made VISIBLE that
the two predecessor sources disagree. Grounded on the canonical data (1,338 Batch-B): **703 identical
(pp28 == BPS)**, **635 divergent** (328 where the OFFICIAL BPS knows ancestors the legacy pp28 drops · 69
where pp28 has extra · 238 mixed), and **560 codes render BOTH elements with DIFFERENT 2020 codes side by
side on prod right now** (e.g. `01138`: legacy "Previous codes" = `01122` vs BPS = `01283`; `01309`: `02119`
vs `01302`, disjoint). They are two DIFFERENT sources: **BPS crosswalk = the official government conversion
table** ("which 2020 code does this 2025 code descend from"); **pp28 = a PP28-risk regulatory citation**, not
a real crosswalk. So the element did not create a bug — it EXPOSED that the legacy "Previous codes" likely
over-promises on ~635 codes. **Decision put to Zero (3 options): (a) keep both + a source-note, (b) BPS is
authoritative → demote/relabel the legacy pp28 element, (c) hold + adjudicate the 635 vs ground-truth
(tier-1, heavy).** He interrupted the option-picker with "salva tutto in /kbli-navigator" — so this is
PARKED here awaiting his choice; NO cure/reconciliation started (investigation was read-only). The **211**
figure used earlier was a narrower cut of this same phenomenon; the accurate numbers are 635 divergent /
560 visible.

**Still-open on the program**: Step 3 (per-code `bps_2020_ancestors` correction-key in the cure-spec
compilers) NOT started; item-10 AQL 0.010% awaits Zero; the legacy `previousCodes` has the SAME latent
vintage-link issue (it links pp28 2020 codes to 2025 pages) — pre-existing, candidate follow-up.

---

**W1 PUBLIC-SURFACE HONESTY PASS — SHIPPED & PROVEN-LIVE 2026-07-24 (PR #3049, squash `23fa765e61`).**
Context: a Codex session (rollout `019f83fc`) had been conducting a 7-work-package program (W0→W7) to
take the Navigator to BKPM-presentable. W0 (census/governance/role-contract) closed 2026-07-23; its W1
commits were authored locally but **never survived** (worktree lost, no branch). Zero's read of that
stretch — _"siamo da 10 giorni su W0"_ / _"molto controllo, zero miglioramenti visibili"_ — is the
standing constraint on this program: **W1+ must produce visible product change, not more governance docs.**
Reconciling W1's 5 declared targets against disk found only 2 real:

- **`46100`** — FALSE ALARM. The batch-B design's own REV-2 self-correction (`d7d9486007`, "46100/52101
  were not inconsistent") already retracted it; `52101`/`10433` were cured in #2786. Nothing to do.
- **`68112` / `93114`** — already cured and live (Fase-1 cure + #2926). Nothing to do.
- **"~30% Blocked in Bali" hero stat** (`apps/mouth/src/app/kbli/page.tsx`) — CURED. Was a hardcoded
  guess whose tooltip asserted the moratorium as settled law. Now **computed at render from
  `getAllCodes()`** (`baliL4.blocked` → 518/1559 = 33%; same in-memory cache `getSections()` already
  uses, zero extra I/O) so it self-corrects as cures land, and the copy matches the F15 posture +
  `KBLIProvenancePanel`'s existing "conservative posture" register: _"a working assessment, not a
  certified legal determination."_
- **PT PMA capital claim** in `buying-a-bali-villa-in-2026-…` (**EN/IT/ID/RU, all 4 locales**) — CURED.
  Asserted a flat "IDR 10bn minimum authorized capital", conflating the two BKPM 5/2025 thresholds.
  Now: **2.5bn paid-up at incorporation + a separate >10bn total investment plan per KBLI line**, and
  states the nuance the article had dropped — **for hospitality/property, land+building ARE inside that
  total** (they're excluded for other sectors). Grounded on two already-correct in-repo articles
  (`bkpm-regulation-5-2025-fdi.mdx`, `consulting-business-guide.it.mdx`) read BEFORE editing —
  deliberately NOT a regex sweep on "10 miliar" (rule #1/F-BKPM: E28A KITAS's 10bn is a genuine,
  unrelated immigration threshold and was verified untouched).

**PROVE-LIVE (both consuming surfaces, curl'd on prod):** `balizero.com/kbli` serves `~33%` + the new
tooltip · the villa article serves the corrected claim in EN and — via the **`?lang=` query param, NOT
a URL suffix** (locale routing gotcha, cost one false-negative probe) — in IT/ID/RU, stale copy gone in
all four. `llms-full.txt` deliberately NOT hand-committed: `npm run build` regenerates it from source
content, so the fix propagates on the next Vercel build (hand-committing it would have dragged 11 days
of unrelated derived drift + tripped the PII gate, which is exactly where the lost Codex W1 got stuck).

**Collateral (repo-wide, not KBLI):** this PR was blocked for hours by a red `npm audit` gate failing on
EVERY open PR — 3 new advisories (`hono` ≤4.12.26, `@hono/node-server` ≤2.0.9, `find-my-way` ≤9.6.0)
landed ABOVE the existing override floors, so the floors aged out silently (W98 / family #2). Diagnosed
and fixed here (#3052); a parallel lane shipped the same cure with strictly higher floors first (#3053,
`hono >=4.12.31`) so #3052 was closed as superseded — verified by CONTENT on main (W88), not by proxy.

**4th-SURFACE LEAK FOUND & CURED IN PROD — 2026-07-24, same session, no PR needed (data-plane
apply of already-merged cures).** Hunting for remaining W1-class public lies, a read-only census of
`kbli_documents` against canonical found the Lot-8/Lot-9 cures had landed on canonical + KG + Qdrant
but **skipped the 4th surface**: of the **217** codes whose canonical `per_skala` is `[]` (detached,
licensing disputed/unverifiable), **18 still carried populated `per_skala` rows in `kbli_documents`**
— which `chat_kbli` injects VERBATIM into the LLM context, i.e. the exact 50113 disease still live
on WhatsApp/webchat. All 18 were the sport/klub cluster: `91425` + `93113/93115/93121/93122/93123/
93124/93125/93126/93127/93128/93129/93192/93193/93194/93195/93197/93199`; none carried `_data_note`,
confirming the cure had simply never been run for them.
Cure: `kbli_documents_cure.py --only <18> --dataset <raw URL pinned to main SHA `5d689084d1`> --apply`,
run on Fly (the dataset is NOT in the image — pass a **commit-pinned** raw URL, never a moving `main`).
Dry-run first: 18/18 eligible, 0 skipped, all `[GAP]` class. All 18 verified eligible beforehand
(`per_skala_disputed_pp28_collision` marker + `intel_2026.whatYouNeed` present) so the tool wrote only
canonical-derived honest-gap prose — never an invented value (rule #9).
**VERIFIED INDEPENDENTLY after apply** (re-read via the read-only role, not the tool's own report):
the 18 → 0 licensing rows / 18 `_data_note`; forensic archive `kbli_documents_archive` captured 18
pre-cure rows; and the **global** invariant now holds — **217 detached codes, 0 still serving
licensing**. **PROVE-LIVE on the consuming surface**: `chat_kbli` for 93121 now answers _"the specific
risk tier and exact licensing workflows … are currently unconfirmed … We do not estimate or guess risk
tiers … verify directly at oss.go.id"_, and states the capital doctrine correctly (2.5bn paid-up +

> 10bn investment, BKPM 5/2025 superseding 4/2021 — #2813's generation-layer fix confirmed working).
> **Standing check for every future lot**: after a cure lands on canonical, re-run the
> detached-vs-`kbli_documents` census — a lot can be "closed" on 3 surfaces and still lie on the 4th.

**W1 is CLOSED. W2/Batch-B is now UNDERWAY and shipping (see the top LIVE-STATE entry: Phase-0 gate #3080,
step-2 populate #3082, step-4 surface #3095). The "still NO-GO" wording below is superseded — Zero GO'd it.**

**Batch A CLOSED 2026-07-21 (114/114, 0 remaining)** — the full "A-serving" 114-code sweep
(113 A-serving/pp28 + 80190 A-serving/orphan) is done. Final tally: 109 full detach + 2
tier-scoped partial detach (93114, 93191 — first production use of PR #2921's
`partial_detach` primitive, built after the SAME gap was confirmed twice, Lot 8 then Lot 9) +
3 certified-clean/no-cure (93111, 93112, 93119 — quarantine was a tooling artifact, not a
record defect; resolved via PP28 Pasal 8(1) grounding + derived_license inapplicability).
Lot 10 report: research/operations/2026-07-21-kbli-batch-a-lot10-conductor-gate.md. Program
closure synthesis: research/operations/2026-07-21-kbli-batch-a-closure.md.
**Residual: PR #2926** (one-off KG/Qdrant partial-detach for 93114/93191, audit-trail only —
production already correct, independently re-verified live) is OPEN, blocked by an unrelated
npm-audit CI gate that PR #2931 healed on main AFTER #2926's own CI ran — a rebase was pushed
2026-07-21 to pick up the fix; check PR #2926's current state before assuming still-blocked.
**What's NOT done:** Batch A was a SUBSET of the ~221 no-scope population (8 pilot + 114 Batch
A = 122 adjudicated; ≈99 genuinely untouched remain — supersedes the stale "~213" figure
below, which pre-dates Batch A's closure). Batch B had a SIGNED design (#2801); it has since been GO'd by
Zero and is shipping mechanically (Phase-0 gate #3080 · step-2 populate #3082 · step-4 surface #3095 — see
the top LIVE-STATE entry). The one open Zero-gate on Batch B is the Tier-4 AQL 0.010% default (#3080).

**Lot 7 (A-L7) — CLOSED 2026-07-20** (closure PR #2885, squash `7fc6c18f3c`, merged
2026-07-20T11:01:47Z — pure-docs: gate reports, corner updates, ledger entries, zero code/data
changes; needed 5 rounds of manual `git merge origin/main` conflict resolution against a
fast-advancing main, see PENDING-ARMS). The gate, cure, cross-family GLM Appendix A adjudication,
and the 41013 post-refinement re-run (refinement #2 VALIDATED, 41013 kept as a contract artifact,
refinement #3 FILED) had already landed on main via the prior lot-cycle PRs — #2885 formally closes
the corner narrative and ledger for the lot, nothing left open.

**Lot 8 (A-L8) — D6 gate SECOND SIGNED 2026-07-20 + cure MERGED** (gate PR #2892, squash
`66ee3932e4`; cure PR #2896, both on main; report
`research/operations/2026-07-20-kbli-batch-a-lot8-conductor-gate.md`):
15/15 codes adjudicated (13 members + 2 controls) — 0 certified, 13 quarantined, both calibration
floors breached (m1 0.615<0.75, m2 0.000 outside [0.2,0.85]) but root-caused as a genuine finding,
not a pipeline defect: this activity family (91425 + the whole 931xx sport/klub cluster) has
unusually poor PP28 primary-source-locatability. Findings: 1 genuine `payload_cross_contamination`
(91425 — pp28_sources cited a wrong neighbor code, conductor-eye image-verified), 6 genuine
`source_absent_in_vault` on exhaustive 21-file/11,208-page scans (93113/93115/93122/93123/93125/93126),
1 wrong-pointer via a reproducible "hot trap page" (93121, same trap page also hit control 63101 —
2nd sighting), 1 both-tiers-absent (93124), and 4 held UN-cured because the underlying crosswalk+
licensing is genuinely sound and only a synthetic derived field lacks formula coverage (93111/93112/ 93119) or the compiler lacks a tier-scoped detach primitive (93114) — detaching these would destroy
good data, not fix a defect (see PENDING-ARMS for both open items). Cure spec
(`scripts/kbli_filiera/cure_specs/batch_a_lot8.json`, 9 codes) **APPLIED to canonical via #2896**.
**Surfaces DONE** (KG detach + Qdrant clear + cache bust + prove-live, all independently
re-verified this session for the 9 cured codes).
**Red-team: Codex/agy both unavailable** (Codex re-authenticated but hard quota-limited until
2026-08-19 on this ChatGPT account; `agy` hung on two independent re-probes) — **Kimi K3 used as
cross-family substitute seat** instead of waiting a month, verdict **CONFIRMED-WITH-NOTES** (none
of the 13 dispositions refuted; 2 MEDIUM + 3 LOW audit-trail defects found and cured in the second
signing — canonical hash pin, disputed-key report/spec mismatch, a lampiran-letter mislabel, a
line citation, one typo). Full findings in the report's Adversarial review section. Also an
evidence-loss incident this cycle (first launch hit an empty evidenceRoot, all ~15 seats correctly
fail-closed rather than hallucinate — re-pulled and independently re-verified before relaunch,
PULL COMPLETE 15/15). **Cross-family Appendix A screen for Lot 8 — DONE** (PR #2909, Kimi K3
substitute seat — Codex/agy both dead at the time): verdict **m1 2/2 match**, one real gold-layer
staleness bug found and fixed in the same session; caveats explicitly declared (no Next.js build
run). **Lot 9 — DONE**: D6 gate SECOND SIGNING complete (PR #2911, Kimi K3 adversarial review,
none of the dispositions refuted) + cure APPLIED (PR #2913: 8 detach + 2 tier-scoped-held +
status_mapping/whatChanged fixes), both merged to main. Lot 9 evidence pins (now historical) were
at `/tmp/kbli-conductor-a1-0718/lot9-prelaunch-pins.md`.

**Where the 1,559 actually stand (grounded on the Filiera methodology census):**

- **1,338 / 1,559** carry OSS-native `ruang_lingkup` (vintage-2025 pure) → structurally safe from
  cross-vintage contamination. This is the trustworthy core.
- **~221 no-scope codes** (OSS ruang-lingkup 404) had `per_skala` **silently filled from PP28/curatela
  (vintage 2020), NOT OSS** (`_l2_status: no_oss_risk`, `_l2_source: null`). Each is a false-friend
  SUSPECT until crosswalk-adjudicated. **This ~221 set is the heart of the remaining risk.**
- The **`pma_status` layer** (Perpres 10/2021 + 49/2021) is ALSO vintage-2020 → a separate
  cross-vintage axis needing per-code crosswalk adjudication across the whole catalog (FATAL-2).
- The **68% KG dedup disease** + gold/editorial baked errors are orthogonal contamination layers.

**What is CURED & PROVEN-LIVE (the pilot slice — 8 of the ~221):** 68112 + the 7 quarantined
false-friends **49213, 51103, 51203, 20111, 50115, 60312, 64310**:

- **Risk residual CLOSED** (#2597, merge `4c6f43bc6b`, Fly **v3800** + Vercel READY): backend
  `_resolve_risk_profile()` = `qdrant_risk or licenses[0].risk or "Not classified"` (honest, not a
  false "Low"); frontend `getRiskLevel`/`getRiskBadge`/`RiskGauge` render "Not classified". Qdrant
  `kategori_risiko` cleared for the 6 no_oss (68112/51103/51203/50115/60312/64310); **49213/20111
  cleared too** after evidence review (both confirmed collisions). `inspect_kbli` cache busted →
  WA/webchat proven-live.
- **KG** (#2596 script MERGED; DB cured): all 8 have 0 REQUIRES edges, disputed targets archived in
  `properties._disputed_requires`, `licensing_status` → `PENDING_REGULATION`.
- **Canonical `per_skala` detached** (#2589 MERGED): `per_skala=[]` + `per_skala_disputed_pp28_*`
  preserved + `_data_note`; 4 copies synced, sidecar bumped.
- **`intel_2026.whatYouNeed` honest-gap** (2026-07-17, branch `agent/air-m5/mouth/kbli-whatyouneed`,
  commits `c724cd8bca` canonical + `344a928bed` gold — LANDING, push armed under M5 fleet
  contention): 7 canonical texts + **2 gold texts (49213, 50115 — gold MASKS intel_2026 on
  /kbli/<code>, LicensingSection parses gold.whatYouNeed directly)**, all Codex-gated PASS. The
  other 5 are not in gold. → after this lands + Vercel rebuild, the 8-code pilot is fully honest on
  every consuming surface.
- **KG dedup partial cure** #2528 landed (scoped); root fix is Fase 2 (below).
- **TRACK-P product/UI layer PROVEN-LIVE** (2026-07-18, PR #2632 + badge-fix PR #2643, both merged, `apps/mouth` only — data-plane untouched): every `/kbli/<code>` page now RENDERS the honesty contract. A **provenance badge** (verified 1,336 / crosswalk-pending 215 / not-classifiable 8) derived in `apps/mouth/src/lib/kbli-provenance.ts` from structured markers ONLY (`_l2_source` EXACT-match `OSS_RBA_resiko_2025`, `_l2_status`, `per_skala_disputed_*` keys — never prose; disputed wins precedence over a stale OSS marker on 49213/20111; unknown marker → `unverified_source`, no invented vintage). A **"Sources & Verification"** per-layer panel (source + KBLI vintage + verdict; PMA disclosed as Perpres 10/49 vintage-2020 audit-pending). A **"Regulatory Divergence"** section on the 8 cured codes (verbatim `_data_note` + detached rows as audit trail + citation chips conditional on markers). FAQ (visible + FAQPage JSON-LD), Article JSON-LD, both key-facts grids and every RiskBadge carry the crosswalk-pending qualifier; not-classifiable codes no longer claim "special/sectoral regime". Wording rule F12 enforced (404 = "not retrievable via OSS API", never "not published"; detach copy speaks only about OUR verification, never asserts regulatory absence). Codex GPT-5.6 adversarial gate, 7 rounds (2 BLOCKER + 6 MAJOR cured) → SHIP. Also fixed the `TransitionBadge` (Direct Match/Renumbered/Aggregated/New-in-2025) from hardcoded light-mode Tailwind to `--kbli-*` dark-theme tokens (PR #2643). **BOUNDARY (recorded so nobody re-investigates):** `kbli-explorer` (the AI-chat inspect surface) canNOT show this provenance client-side — it consumes `/api/v1/kbli-notebook/inspect/<code>` returning `KBLIDetail`, which carries NO markers (`risk_profile`/`licensing_status` only). Aligning it is a BACKEND payload change (expose the verification state in `inspect_kbli`), NOT an apps/mouth task. Cured codes already degrade correctly there via the #2596/#2597 backend cure. **Follow-ups still open (owner/lane-gated, not apps/mouth):** F12-conformant rewrite of the verbatim `_data_note` texts (data-plane, filiera compilers); PMA verdict re-label on PMABadge/hero across all 1,559 pages (FATAL-2 axis, Zero decision — Legge 5).

**PHANTOM CODES — a class no cure tool could reach (found + CURED + PROVEN-LIVE 2026-07-24, #3070/#3072/#3073):**

`kbli_documents` is a strict SUPERSET of the canonical catalogue: **1,563 rows vs 1,559 codes**.
The 4 extras are KBLI **2020** codes — `26120`, `60111`, `82920`, `85598` — carrying full 2020
licensing payloads. The router's direct-code path (`kbli_notebook_chat.py:715`) resolves ANY
5-digit code in the user's question straight against this table, so a phantom row WINS an
exact-match lookup. Live prod proof before the cure: **82920** → _"Yes, a PT PMA can absolutely
run this business"_ + per-scale risk tiers + Gubernur authority + ISO 9001 (the 2025 catalogue
split 82920 into 82921-82929 + 39002); **60111** → _"TERBUKA, 100% open to foreign ownership"_ +
a full ISR/Kominfo permit path + _"register your NIB under KBLI 60111"_ — for a **government**
radio-broadcasting code retired in 2025.

> **STRUCTURAL LESSON — why this survived every previous cure.** EVERY cure tool in the fleet keys
> off _"a canonical record exists"_: `kbli_documents_cure.py` skips on "no `per_skala_disputed_*`
> marker", `kg_kbli_license_fix.py` skips on `record is None` → "not in canonical dataset". That is
> exactly what a phantom code lacks, so **a code living only downstream is unreachable by all of
> them**. Any future cure tool must decide whether its scope is "codes the canonical knows about" or
> "rows that actually exist in the store" — and say so explicitly.

Cure: `backend/scripts/kbli_documents_phantom_cure.py` — TWO arms, `--only` mandatory, no sweep
flag, `--census` reports the phantom set without writing. Rows are rewritten into a
superseded-code notice (2020 payload archived under `*_superseded_kbli2020` + verbatim in
`kbli_documents_archive`); 2025 successors come ONLY from the canonical crosswalk fields
(`kbli_2020_source`/`pp28_sources`), each with its `mapping_note` verbatim — the crosswalk carries
weak auto-matches (39002 "Penyimpanan Karbon" ← 82920 "packaging" at score=71%) and neither silent
inclusion nor silent exclusion (W97) is acceptable. The `--kg` arm detaches **53 REQUIRES edges**
(26120=19, 60111=2, 82920=27, 85598=5), the channel `inspect_kbli` turns into `licenses` and
`_resolve_risk_profile` turns into the risk label.

**FULL CONSUMER MAP for the phantom class, censused 2026-07-24 — the phantom codes live in exactly
TWO stores.** The verified negatives are recorded here so no session re-derives them:

| Surface                                        | Phantom codes present? | Evidence                                                                 |
| ---------------------------------------------- | ---------------------- | ------------------------------------------------------------------------ |
| `kbli_documents` (→ `chat_kbli`)               | **YES — 4**            | 1,563 rows vs 1,559 canonical                                            |
| `kg_nodes`/`kg_edges` (→ `inspect_kbli`)       | **YES — 4 + 53 edges** | all 4 nodes live, `licensing_status: REGULATED`, `pma_status: TERBUKA`   |
| Qdrant (→ `search_kbli`)                       | NO                     | `search_kbli` returns only 2025 codes; zero phantom points               |
| canonical / `apps/mouth` `/kbli/<code>`        | NO                     | phantom absent by definition — pages are generated from the 1,559        |
| `apps/kbli-navigator/data/kbli-2025.json`      | NO                     | **byte-identical to canonical** (blob `2417c876`, same on `origin/main`) |
| `apps/kbli-navigator/lib/kbli-gold-content.ts` | NO                     | zero occurrences of any of the 4 codes                                   |

> **CORRECTION to the "Surfaces 5 & 6" block below (2026-07-24):** it describes surface 5 as rotted
> (1,563 records, zero quarantine markers, cure "in flight"). That is **STALE** — the cure landed:
> the file is tracked, is 1,559 records, and its blob is IDENTICAL to the canonical dataset on
> `origin/main` (verified by content per W88, not by branch name or PR state). Surface 6's gold
> override is likewise clean of phantoms, though its 68112/49213 override issue is a SEPARATE
> question this census does not speak to.

Cross-family adversarial gate: **Kimi K3 → SHIP-WITH-FIXES**, 2 MAJOR both fixed (metadata
neutralisation was a whitelist-of-two → now FAIL-CLOSED on any unrecognised metadata key; the
canonical catalogue was trusted blind though "phantom" is _defined_ by it → `validate_dataset()`

- `--apply` refused against the unpinned `main` URL + dataset sha256 recorded in every cured row).
  **The Codex seat is 401 token-revoked** (not quota) — needs an interactive `codex login`,
  `operator[GUI]`.

**APPLIED + PROVEN-LIVE on every consuming surface (2026-07-24, Fly v3910→v3912).** Both arms ran
on prod (dataset pinned to SHA `e6deb07a25`, never `main` — the script refuses `--apply` against the
unpinned URL). Independently re-verified by reading the DB with the read-only role, NOT the tool's
own report:

- `kbli_documents`: 4 rows → 0 licensing rows, `licensing_status: NOT_IN_KBLI_2025`,
  `pma_status: Verify at OSS`, `_data_note` + `*_superseded_kbli2020` archive present, the false
  `kode_kbli_2025` key removed.
- KG: **0 REQUIRES edges** left on the 4 nodes, 53 archived (19/2/27/5 — exact match to pre-cure),
  nodes marked `NOT_IN_KBLI_2025`.
- `chat_kbli`: answers "82920 is an obsolete KBLI 2020 code … you cannot use it on OSS today",
  lists the 2025 successors, refuses to guess risk tiers. ✅
- `inspect_kbli`: all 4 return `licenses: []`, `risk_profile: "Not classified"`,
  `licensing_status: NOT_IN_KBLI_2025`, `pma_status: Verify at OSS` — the plantation-contaminated
  packaging payload is gone. ✅

**Cache trap paid for here (now a tracked tool — `backend/scripts/kbli_inspect_cache_bust.py`,
#3072 + fail-loud fix #3073):** `inspect_kbli` caches the whole `KBLIDetail` under
`kbli_inspect_v2_{code}` with a **30-day** TTL (`get_kbli_ttl`), on Redis (survives restart). Two
gemini traps, both catalogued in memory `lesson_inspect_kbli_cache_poison_and_bust_redis_init_2026_07_24`:
(1) INSPECTING a cached surface BEFORE curing it poisons its entry for the TTL — my pre-cure
diagnostic call is why `inspect_kbli` 82920 kept lying after the DB was clean; (2) a one-shot
eviction tool that does NOT call `RedisManager.get_instance().initialize()` degrades to an empty
per-process in-memory LRU and reports a FALSE CLEAN ("0/4 had a cache entry" while Redis held them).
The tool now inits RedisManager, logs `cache backend: shared Redis`, and exits non-zero if REDIS_URL
is configured but unreachable. **RULE for every future KBLI cure on a cached surface: cure the store
→ `kbli_inspect_cache_bust.py --only <codes> --apply` → re-verify the surface. Curing the store is
not curing the surface.**

**Surfaces 4-6 + capital doctrine + Batch-B (M5 conductor-verified 2026-07-19):**

- **Surface 4 — `kbli_documents` Postgres table, CURED IN PROD** (#2796 merged + fly apply): table
  seeded 2026-02-18, no builder, injected VERBATIM into `chat_kbli`'s LLM context
  (`kbli_notebook_chat.py:635/:699`) — served fabricated licensing for quarantined codes (live
  proof: 50113 asserted Menengah Tinggi/KSOP/BKI/STCW + Rp10bn from the revoked BKPM 4/2021).
  Cure `backend/scripts/kbli_documents_cure.py` (provenance-bound, dry-run default, `--only`
  mandatory) applied to 86 codes (85 gap→`PENDING_REGULATION`, 49213 restored rows preserved);
  forensic archive `kbli_documents_archive` (86 rows, one-shot); PROVE-LIVE: `chat_kbli` 50113
  now serves the honest gap. PENDING-ARMS: whole-table refresh (~1,473 unmanaged rows), KG
  variant-node cleanup, `search_kbli` "Unknown" label.
- **Generation-layer capital doctrine corrected** (#2813, armed, in CI): `chat_kbli`'s prompt had
  Rp10bn-as-paid-up HARDCODED in 5 places; corrected to the BKPM 5/2025 two-threshold doctrine
  (modal disetor 2.5bn ≠ investment value >10bn/KBLI/location) + a new abstention rule (never
  estimate a risk tier by analogy).
- **Surfaces 5 & 6 — `apps/kbli-navigator` (knowledge.balizero.com; it is a Next.js/Vercel+Netlify
  app, NOT the "native desktop app" §5 describes — mislabel found during Batch-B design work,
  ALIGN-FLEET TODO): BOTH CURED ON MAIN — re-verified on `origin/main` 2026-07-24, this entry
  previously said otherwise and was STALE.** (5) `data/kbli-2025.json` now carries **1,559**
  records (not the rotted 1,563) and 68112 reads correctly — residential title, `per_skala: []`,
  `per_skala_disputed_pp28_mice` + `_l2_status` + `_data_note` markers present; the desync cure
  landed. (6) `lib/kbli-gold-content.ts` no longer overrides the cure: its 68112 entry is the
  honest-gap text that NAMES the collision ("code-number collision … MICE-venue rental … do not
  apply to residential leasing and have been removed"), and 49213 correctly frames AKDP/AKAP as
  the DIFFERENT regulatory basis it is excluded from. **Do NOT re-open these as work items.**
  Residual on this app: it is **SSO-gated** (`/kbli/<code>` → 307 → `kita.balizero.com/login`),
  so it is an INTERNAL/team surface, not an anonymous-public one — anonymous curl can never
  prove-live it (cf. [[discovery_nuzantara_rag_401_precedes_routing_2026_07_22]]); a real
  prove-live there needs authenticated browser QA.
- **Mouth gold cure LIVE** (#2794): 10 gold records' detached-code echoes cured
  (whatYouNeed/zantaraOpener/baliContext), PROVE-LIVE on 68123/60103; 63-phantom triage table
  `scripts/kbli_gold_remap_table_status.json` (48 unmapped / 8 ambiguous-SPLIT / 7
  single-candidate).
- **Batch-B pre-registration design SIGNED** (#2801 merged, REV-4b): determinism gate closed after
  4 Codex xhigh rounds + Gemini. **Phase-0 parser gate PASSED** (report
  `research/operations/2026-07-21-kbli-batch-b-phase0-parser-gate.md`: 20-page holdout, 100%
  precision/recall, cross-family Sonnet+Kimi K3 blind verification) and the parser+FULL-CORPUS
  crosswalk relation (`scripts/kbli_filiera/bps_crosswalk_parser.py` + `bps_phase0_gate.py`,
  `data/kbli-filiera/phase0/bps_crosswalk.json` — 1,559/1,559 codes with BPS ancestry) shipped
  2026-07-24 via PR #3083 (was orphaned in a local worktree, un-orphaned and merged this session).
  **Still open before Lot B-1 can dispatch**: (a) `populate_bps_ancestors.py`, the canonical-WRITE
  compiler that mutates `bps_2020_ancestors` from the relation — not yet built (step 2 of 3; the
  full-corpus PARSE is done, the canonical WRITE is not); (b) Tier-4 population count — requires
  applying the design's §1.5 tiering logic to the now-available relation, not yet run; (c) Tier-4
  AQL parameters (n/Ac/switching state) computed from that count + the measured 0.0 holdout error
  rate per the frozen ISO 2859-1 rule, then Zero's Legge-5 accept-or-override ratification — not
  yet computed; (d) 5 fresh POS controls, conductor-eye-adjudicated on raw Lampiran renders —
  explicitly non-delegable, not yet started. See §5.

**What is NOT done (the actual remaining program):** ~213 no-scope codes un-adjudicated · the
`pma_status` cross-vintage audit across the catalog · the KG 68% disease at the root · the 63
phantom gold-remap rows · Batches A(remainder)/B/C/D of the Filiera sweep. See §5.

**Batch-0 vault base DONE — extraction still BLOCKED (2026-07-18, LANE-B0 task #8, PR #2622 merged `17f360df4`):**
raw-evidence vault live on Mini `~/nuzantara-vault/` (bps 1 + oss 4,933 + pp28 21 blobs) ·
manifest committed `data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json` (4,955
entries, all sha256+provenance, deterministic; file sha256 `e7d25a37…`) · Tigris mirror
proven-live 4,959/4,959 at `nuzantara-backups/kbli-vault/` · OSS coverage 6,236/6,236
(code,endpoint) pairs — 1,303 absences at 3 probes each, no-scope set EXACTLY 221 (zero drift
vs census). **Open quarantines (proposed in PR #2622, NOT resolved):** BPS Vol.1 missing
(Turnstile → browser lane) · Perpres-annex compiler not built · absence ≥72h window needs one
probe after 2026-07-19T18:10Z · stray mirror copy in `nuzantara-warroom-images/kbli-vault/`
(pre-fix run) to delete. **EXTRACTION GATE — collapsed to ONE precondition (updated 2026-07-18):** the gate is now just **P0 membership** (#2640 LANDING; the Detect Secrets git-SHA false-positive on `canonical_revision` was fixed via a durable auto-triage rule for `data/kbli-filiera/membership/`, proven end-to-end; auto-merge armed SQUASH). Two prior "gates" dissolved: (a) **renders are NOT a bulk pre-build** — the PP28 300-dpi renders are produced **on-demand per-code at D2** from the sha256-pinned PP28 PDFs (`pdftoppm -r 300`, deterministic, offline); (b) the **OSS endpoint inventory is DONE** (6,236/6,236 pairs, in the manifest). **P1-v2 UNBLOCKED — LANE CLAIM (D12 anti-collision): the P1-v2 second vault wave is OWNED by the S2/Pro conductor session (MANDATO GARUDA), claimed 2026-07-19 on Zero's GO** (supersedes the 2026-07-18 HELD ruling _"aspetti dopo il Pilota A1"_ — Pilota A1 measured, GO issued). Scope of the claimed lane: fetch + sha256 + vault manifest ADDENDUM on Mini (via ssh) for Perpres 10/2021 + 49/2021 investment annexes, Bali (Gubernur letter B.27.000/642/PM/DPMPTSP) + Kepmenaker 228/2019, with DATED per-instrument status snapshots and per-instrument provenance. Facet rules (Zero, verbatim intent): `pma_status`/`l4_bali`/TKA facets stay **abstain fail-safe** (A1/A5/A6) and unlock ONLY per-code where the wave is grounded — **never a global lift**; current Batch-A lots continue in parallel under abstain until the wave is ready. **Wave status 2026-07-19: DELIVERED** — 8 instrument blobs fetched + sha256'd on the Mini vault (`~/nuzantara-vault/p1v2/`) with 4 dated per-instrument status snapshots; manifest addendum `data/kbli-filiera/manifest/vault-manifest-p1v2-2026-07-19.json` MERGED (#2811, hashes independently re-verified via ssh; claim PR #2808). Next: per-code facet-unlock design (fase 2 — no facet unlocks yet, abstain still in force everywhere). **Disjointness: the M5 Fable session owns Batch B (branch `agent/air-m5/docs/batch-b-design`) — this lane does not touch Batch-B artifacts; the M5 lane does not touch the P1-v2 vault wave.** First-writer-owns per scar D12. **⇒ Pilota A1 starts on the OSS+PP28+BPS core the moment P0 is on main.** Genuinely-deferred (NOT gates): BPS Vol.1 (Turnstile → browser lane), absence-window one probe after 2026-07-19T18:10Z, stray warroom mirror copy to delete.

**Batch-A Lot 1 conductor gate SIGNED, second signing post-red-team (2026-07-18, MANDATO S2
session):** final verdict **13/13 quarantine, 0 certified** on the first A-serving lot (a
contiguous taxonomy-ordered segment, divisions 01→39 — NOT a random sample; no extrapolation to
the full ~221 class claimed, but fail-safe: every no-scope code is a SUSPECT until proven). The
lane (same-family Sonnet D1/D5) had certified 8 clean; 7 were FALSE-clean on content evidence
(Codex refuter 2: 02402, 38222 · blind-GLM-with-vision 5: 05200, 01287, 02201, 08920, 36003) and
the 8th (19206) was quarantined under the plan's preregistered divergence rule (A-6(a): two
cross-family seats vs the conductor's own picked clean — caught by the mandated full-report
red-team, Codex sol FIX-FIRST 4 BLOCKER/4 MAJOR/4 MINOR, all cured not argued down). Disease
categories censused: **payload_cross_contamination** (licensing payload whose content belongs to
another activity), **unresolvable_source_pointer** (pp28*sources row not retrievable from the
pinned corpus as hunted — NOT asserted nonexistent; earned ABSENT needs the image-grade scan),
**mapping_metadata_false**, **split-generic-payload** (19206). Meta-pattern: \_same-family blind
agreement measures transcription fidelity, not truth; a provenance pointer is not a content
check* → cross-family IMAGE-GROUNDED blind D5 + D4 content-vs-scope check are now LANE protocol
(GO package §10). Calibration: FOUR declared breaches — m1 ❌ 0.385 (cross-family extractor IAA;
the lane's blindness measured), m2 ❌ 0.000, m3 ⚠️ new-category pause, m5 ❌ NEG 7/8 (49213
miss) — via plan amendments A-4/A-5/A-6; never silently resumed. **m5 HALT LIFTED (A-6(b)
RESOLVED, same session):** the 49213 NEG miss was adjudicated per-ancestor on image-grade renders
(49213-2025 = merge of {49214, 49219, 49413}-2020; all 3 PP28 regimes verified BY EYE identical —
NIB+SS, Bupati/Wali Kota — the unique case where a merge's ancestors converge, vs 01700 where they
diverge) → the miss is a certifiable-restore case, not a silent gap; restore of 49213 is a
scheduled data-plane cure (dedicated PR, `pp28_sources=['49214','49219','49413']`). Artifacts:
report `research/operations/2026-07-18-kbli-batch-a-lot1-conductor-gate.md` (signed, §12
receipts) · cure spec `scripts/kbli_filiera/cure_specs/batch_a_lot1.json` (13 codes, detach-only,
no substitute values, PMA/l4/TKA still abstain) · registry test
`scripts/tests/test_kbli_batch_a_lot1_registry.py` (module-gated on `_cure_applied()`) · Qdrant
clear tool `apps/backend-rag/backend/scripts/kbli_qdrant_risk_clear.py` (dry-run default,
`--codes` required). None of the 13 in gold (verified vs all 428); KG has 147 live REQUIRES edges
across the 13 (counted on prod) → detach via `kg_kbli_license_fix.py` post-apply. **GO GRANTED
(Zero, 2026-07-18, Legge 5): explicit "go" on the Batch-A remainder + EXTENDED GO ("quando
finisce lot 2 procedi con gli altri lot senza fermarti") — continuous lot-by-lot execution of the
whole remainder (~101 in-scope codes, lots 2→~9) under the amended lane protocol, no per-lot GO
needed; Zero is notified at Lot 2 kickoff. A-6(c) precondition (calibration registry v2
re-emission on the cured canonical) ships in the governance PR before the Lot 2 lane starts.**

**Batch-A SWEEP PROGRESS — Lots 1-5 (dense recap 2026-07-19, MANDATO S2 continuous run; supersedes the Lot-1-only block above for current state):**

- **91/114 original in-scope adjudicated across 7 lots — 91/91 QUARANTINED, 0 certified.
  L7 fully applied+surfaced (cured-and-live cumulative 91/1,559 incl. pilot).**
  Census by lot: L1 13 (div 01→39, gate report 2026-07-18-...lot1..., cure applied+surfaced) ·
  L2 13 (#2753 gate, #2761 cure) · L3 13 (#2768 gate, #2769 cure) · L4 13 (#2774 gate, #2776
  cure incl. runner innocence-PROMPT fix; 64955 wrong-parent flagship; ALL TEN 66xxx carry the
  identical cooperative-rating payload) · L5 13 (gate #2788 MERGED, cure #2778 merged incl.
  runner INNOCENCE_SCHEMA symmetric-blind fix; members 66192→70100) · **L6 13 (#2803 gate —
  incl. the 80190 certification REVOKED→re-quarantined, W100-L6 rule "conductor's eyes on the
  FULL canonical record for every certification"; #2800 cure incl. certification-contract gen-2:
  `exposed_facts_inventory` REQUIRED + fail-closed `factsInventoryUnverified`; surfaces 13/13
  PROVEN-LIVE, spot-check 80190)** · **L7 13 CLOSED end-to-end (gate #2837, cure spec+contract
  #2831, data-apply #2878, surfaces PROVEN-LIVE 2026-07-20 — conductor spot-check on the largest
  cluster 86201/27 disputed-edges + 86203/91424, independent of the applier's own report): 6
  source_absent {85403,85404,86109,86201,86202,86203} / 4 payload {85330 aviation PAGE-BLEED,
  85401 51108-fan, 86102, 91212} / 1 collision {90111, ISO-9001 matcher-trap} / 1
  illegitimate-inheritance {91222} / 1 unresolvable {91424}; Appendix A cross-family GLM
  adjudicated (m1 5/5 no verdict overturned, NEG surfaced 2 real editorial-layer deviations on
  52239/68127 — FILED, POS 2/2 clean); 41013 control re-run LIVE post-refinement (wf_644964d5-783):
  refinement #2 (derived-fact rule, Pasal 225(1) MT / 230 Tinggi / 124(4) derived-license)
  VALIDATED, 41013 converts to "contract artifact" but stays quarantined pending refinement #3
  (tier-label join, FILED). 96 KG REQUIRES edges removed (86201 alone = 27), Qdrant risk cleared,
  13 cache keys busted, `kbli_documents` 4th surface applied (13/99 cumulative, whole-table
  builder still missing). **In-scope remainder: 23** (of 221 total, invariant) → **2 lots to
  finish** (L8 12+1/L9 10 — see membership split below; L8 gated on refinement #2, now shipped).
  **[HISTORICAL — superseded]** this whole dense-recap block is dated 2026-07-19, mid-sweep; L8,
  L9, and L10 have since all CLOSED (see **Batch A CLOSED 2026-07-21 (114/114, 0 remaining)** at
  the top of this section, which is the current top-line state) — "2 lots to finish" no longer
  applies, kept here only as the sweep's own historical log.
  Surfaces: L1-L4 + L6 + L7 applied and PROVEN-LIVE (KG REQUIRES edges removed, Qdrant risk
  cleared, cache busted, backend inspect + mouth SSR eye-verified per lot); **L5 surfaces
  INDEPENDENTLY RE-PROVEN 2026-07-19** (prod KG query: 13/13 zero REQUIRES edges +
  `PENDING_REGULATION` + disputed archived; live `inspect/66192` returns risk "Not classified",
  licenses []). Governance: calibration **v3\*\* on main (#2777, supersedes conflicted #2772) — NEG
  47 salt "v3", POS 8, `pos_preverification_required`, burned-set 16 (extended to 119+ post-L7 D0
  back-reconstruction, see Lot 8 pins).
- **Per-lot cycle (proven 5×, ~2h):** lane Workflow (launcher `/tmp/kbli-conductor-a1-0718/
lotN-launcher.js`, byte-exact membership injection via Python, canonical-sha fence) → conductor
  D6 gate + by-eye renders → FIRST signing → codex sol xhigh red-team (FULL-output capture, W97)
  → cures → SECOND signing (now with immutable artifact manifest: sha256 of raw/journal/renders/
  canonical + runner blob — L5 innovation, keep it) → cross-family GLM 5.2 pass (m1 sample +
  m5-NEG + m5-POS w/ conductor exposed-codes screen) → Appendix A adjudication → gate PR →
  cure PR (conductor gates the diff, then arms auto-merge) → surfaces → next lot.
  **W100 held 5/5 lots: every first signing was FIX-FIRSTed; substance (quarantine verdicts)
  survived every pass — the errors live in the conductor's audit trail, never in the verdicts.**
- **Program-level discoveries (L4-L5):** (a) cooperative-payload ROOT traced: PP28 lampiran row
  66292 is KBLI-2020-vintage ("Pemeringkat UMKM dan Koperasi", true 2025 home = 66198); one
  vintage-blind digit-string join poisoned 17+ codes across div 66. (b) The 68-division fan
  (2020-68111 → 7 children incl. BOTH halves of the pilot's 68112 collision: residential←68111,
  MICE→68124) is conductor-eye-verified on the BPS table — the collision factory. (c)
  Vision-read STRUCTURED labels (mapping_type) are soft — verdict bits + citations are the
  load-bearing signal; never use structured labels as concordance keys (L4 Appendix A meta-note).
  (d) The metadata-crosswalk disease also lives in the 1,336 "verified" OSS-native set
  (FATAL-4 candidate — Zero/Legge-5 product decision pending). (e) Innocence-control blindness
  took TWO generations to fix: prompt leak (#2776) then SCHEMA leak (#2778 symmetric pipeline,
  runner-side normalization) — third instance of the fix-begets-twin-bug family; controls from
  L1-L5 are all recorded as ANCHORED NON-BLIND FIXTURES. **True-blind era (L6-L7): the symmetric
  path ran live; 59140/59201 RETIRED after 4 reuses; from L7 every lot draws FRESH controls,
  burned after one use. The L7 fresh pair proved the policy's worth: 20232 (picked for expected
  cleanliness) itself carries a false MATCH_LANGSUNG, and 41013 asserts fiktif_positif with no
  citable provenance (correct fail-closed demote → drove contract refinement #2).**
- **Standing infra state:** Redis lease registry NOAUTH from sessions → LEASE-GUARD SKIPPED
  declared in every gate with compensating isolation. Local vault mirror on Pro
  (`~/nuzantara-vault`) serves dossier_pull without Mini. GLM seat: TP1 `tp1-glm-5.2`
  (OpenAI-compatible base `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`, key loaded by `load_tp1_settings_key()` from `~/.qwen/settings.json`) — probe-first from staging BASE.
- **Standalone metadata cure-list BACKLOG (grows lot-by-lot, not yet a dedicated spec+PR — the
  only place this list is currently tracked; update here when it changes):** `01629` + `71204`
  (Lot 5 gate §m5-POS, 2026-07-19 — multi-parent crosswalk metadata false, evidence-gated) ·
  `59140` pp28-label (Lot 6 gate §3.4 — OSS-native, pp28_sources unverifiable, per_skala provenance
  sound by marker) · **`20232` (Lot 7 gate §3.4, 2026-07-19 — fresh SELECTED control, conductor-eye
  SPLIT on lampiran5_p156-156.png printed p.142: canonical `status_mapping='MATCH_LANGSUNG'`/"scope
  unchanged" refuted by two consecutive rows, 2025-20232 + 2025-20235; per rule #9 NOT detached in
  the Lot 7 cure — OSS-native, healthy per_skala).** All four are `metadata_only` candidates (same
  compiler action as 52101/46100/10433/`metadata_fixes_2026_07_19.json` — status_mapping/whatChanged/
  pp28_sources correction, per_skala untouched) pending a dedicated evidence-gated spec+PR; none has
  a canonical write yet.

**Governance flags:**

- **Filiera methodology**: panel CONCLUDED. Doc `research/operations/2026-07-16-kbli-filiera-methodology.md`
  (#2534 MERGED); execution program `research/operations/2026-07-16-kbli-garuda-filiera-workflow.md`
  (#2538 MERGED). **Phase GO is PER BATCH (Legge 5, Zero).** Pilot A1 (~the 8 above) done; the
  measured pilot report is the basis for the batch-A-remainder GO.
- **BKPM discrepancy findings stay INTERNAL** (Zero, 2026-07-16): the 68112 surat klarifikasi stays
  drafted in the drawer, not sent, without a fresh Zero GO.
- **PMA primary-verdict labeling — RULED (Zero, 2026-07-18, Legge 5):** the headline PMA verdict
  (hero PMABadge + verdict banner + Foreign-Ownership key-facts cells + OG status chip) STAYS a clean
  OPEN/RESTRICTED/CLOSED. The Perpres-10/49 vintage-2020 + crosswalk-pending status (FATAL-2 axis) is
  disclosed ONLY in the TRACK-P "Sources & Verification" panel (already live), NOT stamped on the
  headline verdict. Rationale: the PMA values are the in-force investment-list annexes (not the
  per_skala silent-fill disease), largely correct; the FATAL-2 per-code crosswalk refines the
  underlying values later. → the "PMA re-label" follow-up is CLOSED (ruled), not open — do not
  re-open without a fresh Zero GO.

- **data-plane guard LIVE** (#2550): only `scripts/kbli_filiera/` compilers may write the canonical
  KBLI dataset + `data/kbli-filiera/**`; interactive hand-edits BLOCKED. Registry
  `infra/claude-hooks/data-plane-registry.json` is the extension point. Kill switch
  `DATA_PLANE_GUARD_OFF=1`. (gold `kbli-gold-all.json` is NOT yet registered — editable, but pin
  every change with a regression test, cf. the 49213/50115 gold cure.)

**CHATKB cantiere `company-kbli-signed-lots` — 3-seat review (GLM+Claude+Codex), ARBITER-verified
(2026-07-19).** Dossier on M5:
`~/Desktop/CHATKB-CANTIERE-2026-07-19/company-kbli-signed-lots/{FINAL.md,gate-verdict.md,contested.md}`
(not shipped to `curated_qa` yet). **Established truth added to §2 below**: PP 28/2025
primary-verified via BPK registry `peraturan.bpk.go.id/Details/319773` ("Mencabut: PP No. 5 Tahun
2021") — the current in-force licensing instrument, GLM-live-checked. **Open follow-ups for this
corner (flagged only, nothing fixed here):**

1. **HIGH-PRIORITY unresolved**: 78109 and 80190 "TERBUKA 100%" ownership claims flagged against
   historical precedent (78xx labour-placement family; BUJP private-security regime) — two
   independent web passes found neither confirmation nor refutation. Needs a direct DPI-annex
   (Perpres 10/2021 jo. 49/2021 lampiran) read before either claim is committed client-facing.
2. **PROD self-contradiction risk**: live `inspect_kbli`/`chat_kbli` still serve the disproven
   contaminated payloads for 78109 (LPK-mixed, `risk_profile: "Menengah Tinggi"`, 16 license rows
   incl. the disproven LPK block) and 80190 (`risk_profile: "Tinggi"`) — KG/Qdrant resync pending.
   A live tool call mid-conversation can still contradict the cured dossier answer for either code.
3. **85321 crosswalk parent implausible**: the dossier's claimed true crosswalk parent {51108
   "Angkutan Udara Bukan Niaga" air-transport} is flagged implausible for a vocational-education
   code — re-check the BPS Vol.2 Lampiran 5 p.193 render. Confirmed separately: 85321's own title is
   "...Pemerintah" (government-operated type only); the private route is sibling code **85322**,
   whose ownership status is NOT yet verified.
4. **70100 ≠ passive holding**: the official OSS scope note for 70100 (Aktivitas Kantor Pusat)
   explicitly EXCLUDES passive holding-company activity → redirects to KBLI **64200**, whose
   ownership status is NOT yet verified.
5. **Q14/39001 provenance gap**: the dossier cites "BPS Vol.2 Lampiran 5 p.170, image-verified" for
   39001 with NO Lot number / workflow run-ID (every other code in this dossier cites one) — confirm
   the real Lot number for 39001 from `cure_specs`/workflow records before this row ships to
   `curated_qa`.

## 2. ESTABLISHED TRUTH (verified — do not re-litigate, do not re-derive)

1. **68112 = code-number collision** (image-verified 3× on official BPK PDFs): PP 28/2025 Lampiran
   I.L (Pariwisata) p.I.L.44 row 25 codes 68112 as "Penyewaan Venue MICE dan Event Khusus"; BPS
   7/2025 (KBLI 2025) reassigned 68112 to residential leasing. Residential in PP28 = **68111**
   (Lampiran I.H, PUPR). No residential 68112 exists anywhere in PP28's 21 lampiran.
2. **False friends confirmed beyond 68112**: 51103/51203 (space transport carrying KBLI-2020
   commercial-aviation licensing); 49213 (intra-city urban transport carrying the inter-city AKDP
   authority Gubernur, correct = Wali Kota/Bupati); 50115 (int'l sea tourism carrying the wrong AIR
   source 51107 which does not exist in PP28); 20111 (many-to-one merge single-source); 60312; 64310. High-concern suspects NOT yet adjudicated: 25200 (weapons/ammunition — dedicated
   regulatory review), 11× 47xxx retail family, 32114, 32906, 43216/43223. Sweep evidence:
   `research/operations/2026-07-16-kbli-false-friend-sweep.{md,json}`.
3. **~221 no-scope codes**: OSS ruang-lingkup 404 → their `per_skala` was silently filled from
   PP28/curatela, NOT OSS (`_l2_status: no_oss_risk`, `_l2_source: null`). Every one is
   false-friend-suspect until crosswalk-adjudicated.
4. **The official BPS conversion table (tabel kesesuaian KBLI 2020↔2025) EXISTS** — fetch fresh from
   bps.go.id (KBLI 2025 page; Codex red-team verified 2026-07-16). It is **one-to-many/many-to-one**:
   it narrows candidates but regulatory inheritance still needs per-activity adjudication (FATAL-1).
5. **The vintage defect is NOT only PP28**: Perpres 10/2021 + 49/2021 investment annexes are ALSO
   KBLI-2020-vintage → the whole `pma_status` layer needs the same cross-vintage treatment (FATAL-2).
6. **Permen BKPM 4/2021 is REVOKED** by Permen Investasi/Hilirisasi-BKPM 5/2025 (in force
   2025-10-02) → any Rp10bn-per-KBLI-per-location capital claims citing 4/2021 are stale-sourced
   (FATAL-3). Paid-up PMA = 2,5 mld under BKPM 5/2025; the >10 mld/KBLI/lokasi total is a SEPARATE
   rule; E28A 10 mld is an immigration rule — never sweep blindly on "10 miliar". Gold `baliContext`
   texts are at risk.
7. **OSS API 404 ≠ regulatory absence** (F12): could be changed UUID, lag, WAF, access control.
   `ABSENT` verdicts require corroboration (absence in PP28 lampiran verified on image, or crosswalk
   evidence). Wording for notes must say "no scope retrievable via OSS API (404), corroborated by
   <X>" — never bare "not published".
8. **KG diseases** (verified 2× on prod Postgres): perizinan nodes deduped BY NAME → 978 codes share
   ONE "NIB dan Sertifikat Standar" node whose kewajiban is agriculture text (852 edges); 187 agri-
   marked nodes reach ~1,065/1,568 codes. Router precedence bug: `props.get("uraian", description)`
   → properties.uraian wins; 930 codes drifted. The KG catalog has NO generator left in the repo
   (Fase 2 rebuilds it).
9. **Bali moratorium overlay (l4_bali)**: verdicts were derived from (possibly collision-derived)
   risk levels, and the Gubernur letter's binding legal effect is unproven (F15) — treat "blocked"
   as conservative posture, not certified fact; re-derive reasons when true risk is known.
10. **Gold/editorial layers bake upstream errors**: they keep asserting stale facts after the source
    is fixed, and don't name the marker (no "MICE" in the baked prose) — marker-based guards can't
    catch them. Re-grounding a source MUST emit an invalidation list of derived surfaces. **Gold
    takes precedence over intel_2026 for editorial fields on /kbli/<code>** (kbli-data.server.ts
    merges gold first; LicensingSection.tsx parses gold.whatYouNeed DIRECTLY) — so a canonical fix
    is invisible on a gold code until gold is cured too (49213/50115 lesson, 2026-07-17).
11. **PP 28/2025 is primary-source-verified as the current in-force licensing instrument**: BPK
    registry `peraturan.bpk.go.id/Details/319773` ("Mencabut: PP No. 5 Tahun 2021"), GLM-live-checked
    2026-07-19 during the CHATKB `company-kbli-signed-lots` 3-seat review. Supersedes any lingering
    "PP 28/2019" reference — the correct current-instrument citation for this corner.

## 3. ARTIFACTS & ACCESS (verified paths — check before use, cf. anti-hallucination)

- **Canonical dataset**: `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (1,559 codes; tracked
  symlink `source_documents/` → same; mouth copy `apps/mouth/data/` kept byte-identical by
  `scripts/sync_kbli_dataset.sh` + CI `check-kbli-dataset-sync`; 2 gitignored RAG runtime copies
  rebuilt in-container). Sidecar sha: `apps/mouth/data/kbli-dataset-version.json`. Per-record
  provenance: `_source`, `_l1_source`, `_l2_source`/`_l2_status`, `pma_source`, `pp28_sources`,
  `l4_bali`, `intel_2026`, `_data_note`, `per_skala_disputed_*`. **WRITE ONLY via
  `scripts/kbli_filiera/` compilers** (data-plane guard #2550). Cure compiler:
  `scripts/kbli_filiera/cure_canonical_collisions.py` (spec-driven `cure_specs/fase1_collisions.json`;
  detaches per_skala AND honest-gaps intel_2026.whatYouNeed, idempotent; `--apply` syncs + bumps
  sidecar).
- **Gold layer**: `apps/mouth/data/kbli-gold-all.json` (428 records, keyed by code) — served by
  `apps/mouth/src/lib/kbli-data.server.ts`; remap table `scripts/kbli_gold_remap_table.json` (63
  phantom rows). NOT data-plane-guarded — edit value-in-place + pin with a regression test.
- **OSS RBA API** (public app credential, zero PII): host `gw.oss.go.id`, header
  `user_key: $OSS_RBA_USER_KEY` (static gov-app credential — value in memory
  `discovery_oss_rba_kbli_api_extraction_2026_06_19`). Endpoints: `/v2/portal/kbli?id_version=<uuid>`
  (list), `/v2/portal/kbli/{uuid}` (detail), `/v2/portal/kbli/ruang-lingkup/{uuid}` (risk rows; 404
  legit for no-scope), `/relasi/{uuid}`, `/umku/{uuid}`. KBLI-2025 version uuid:
  `fff4053d-cbb0-51e9-9dc5-1e85b5740704`. Code→uuid map:
  `data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json`. TRAP: urllib honors system proxy — use
  `ProxyHandler({})` or `curl --noproxy '*'`.
- **PP 28/2025 lampiran corpus**: peraturan.bpk.go.id Download ids **394930–394950** (21 files:
  Lampiran I.A–I.V by MINISTRY sector — letters ≠ KBLI category letters! — + II/III/IV; body PDF
  381375 has zero KBLI codes). **OCR TRAP: digit 1 renders as t/l/I ("68112"→"681t2") → `grep <code>`
  false-negatives. For any load-bearing digit: `pdftoppm -f <p> -l <p> -r 300 -png` + visual read.**
- **BPS crosswalk** (Fase 1 engine, F1): tabel konversi KBLI 2020↔2025, publication 2026-04-22 on
  bps.go.id — ingest fresh as a first-class dataset before the sweep.
- **Backend KG**: Postgres `kg_nodes` (`kbli:<code>`, `perizinan:<hash>`) + `kg_edges` (REQUIRES).
  Read-only: `scripts/pg.sh` / MCP `postgres-nuzantara` (combo `nuzantara_readonly`, proxy
  `127.0.0.1:15432`). Cure/resync scripts: `apps/backend-rag/backend/scripts/kg_kbli_license_fix.py`
  (dry-run default, `--apply` gated, `--only` mandatory, canonical-driven) + `kg_kbli_resync.py`.
- **Regression tests**: `scripts/tests/test_kbli_false_friend_registry.py` (all 8 codes: detach +
  audit + marker discipline + gold cure for 49213/50115; folds in the original 68112 test) +
  `scripts/kbli_filiera/tests/test_cure_canonical_collisions.py` (the whatYouNeed compiler). Extend
  the registry for every new false friend; never a bare-substring guard (scar #3: guilt+innocence
  corpus mandatory).
- **Filiera program state**: `data/kbli-filiera/` — dossier event-logs, quarantine ledger,
  `batch-reports/` signed reports (censuses, verdicts, IAA, gold-set hits).
- **Specs**: methodology `research/operations/2026-07-16-kbli-filiera-methodology.md` (#2534) ·
  execution/workflow `research/operations/2026-07-16-kbli-garuda-filiera-workflow.md` (#2538) ·
  "Operazione Garuda 1559" (GPT-5.6 Sol, 2026-07-14) — Garuda certifies internal consistency;
  Filiera adds external truth.

## 4. OPERATING RULES (blood-bought — violating these re-opens closed wounds)

1. **Vintage-aware identity**: `KBLI2020:X ≠ KBLI2025:X`. Any cross-vintage join goes through the
   BPS conversion table; bare-digit joins are forbidden (CI-lint). Applies to PP28 AND Perpres 10/49
   AND Kepmen 228/2019 TKA-categories AND any pre-2026 source.
2. **Crosswalk narrows, context adjudicates**: the citing entry's use-case decides, never
   title-similarity ("il contesto batte il titolo" — 63120→63900 lesson). Signature of a wrong
   remap: mapping_type=SPLIT applied as single code + boilerplate reasoning.
3. **Silence → corroborated abstention**: a 404/missing row is recorded as gap ONLY with a second
   independent signal; NEVER silently fill from another vintage/source (that silent fill IS the
   July disease).
4. **Detach > plausible remap**: "un phantom dichiarato è onesto, un rimappato sbagliato è una bugia
   in produzione."
5. **Digits from scans: image-verify** (pdftoppm 300dpi + eyes). pdftotext of BPK scans is evidence
   of TEXT, never of DIGITS.
6. **Consumer-map before scoping any data fix**: canonical → mouth `/kbli/<code>` SSR · **gold →
   same pages, and gold WINS over intel_2026** · KG/Qdrant → WA/webchat via `inspect_kbli` ·
   **`kbli_documents` (Postgres) → `chat_kbli` LLM context via
   `_fetch_parent_documents_from_kbli_table()` + direct 5-digit lookup
   (`apps/backend-rag/backend/app/routers/kbli_notebook_chat.py:635,699`) — the 4th surface,
   cured by `kbli_documents_cure.py` (#2796, 2026-07-19) — and **RECONCILED 2026-07-24: all 217
   canonical-detached codes now serve 0 licensing rows here (was 18 leaking, see LIVE STATE)**;
   whole-table builder still missing (PENDING-ARMS)** · intel_2026/editorial → baked prose · `apps/kbli-navigator`
   app (knowledge.balizero.com — Next.js, NOT a native desktop app, see LIVE STATE) → its own
   `data/kbli-2025.json` fork AND its own `lib/kbli-gold-content.ts` override layer (**both CURED
   on main, re-verified 2026-07-24 — still consumers to check on every future cure, but not open
   work items**) · NB sources. Fix the class across ALL consumers or explicitly
   park the rest; "merged" ≠ "live" ≠ "every surface".
7. **Derived layers need invalidation**: after correcting any source fact, list which derived fields
   (gold whatYouNeed, editorial, l4_bali reason, KG properties, NB) were generated FROM it and
   schedule them; guards on markers won't catch baked prose.
8. **False-friend fix pattern** (use as-is): `per_skala` → `[]` + preserve old block under
   `per_skala_disputed_<source>` + `_data_note` with corroborated wording + honest-gap
   intel_2026.whatYouNeed (+ gold whatYouNeed if the code is in gold) + entry in the registry test +
   innocence controls (legit neighbor codes with similar markers must not be touched).
9. **No new licensing values without provenance**: never author risk/license/authority values from
   plausibility — either a sourced row (locator+vintage) or an honest "not yet defined". Client-facing
   honest-gap prose gets a Codex cross-family gate (generator≠grader) before ship.
10. **Ship-lifecycle**: per CLAUDE.md §2 — the session reviews, merges, arms, deploys, proves live.
    Sensitive data raises the adversarial gate, never parks the merge on a human. GO is per-batch
    (Legge 5) for the sweep; the ship of an already-GO'd batch is fully the session's.

## 5. THE PLAN — the completion programme (REWRITTEN 2026-08-01; supersedes the A/B/C/D batch-sweep roadmap)

> Zero's mandate, verbatim: _"voglio che organizzi un piano decisivo di completamento. Non mini serie
> di azioni"_ (2026-08-01). What follows is what the MEASUREMENT says, not what the previous roadmap
> assumed. Garuda still certifies INTERNAL consistency and Filiera still adds EXTERNAL truth; the
> end-state is unchanged — every rendered fact government-sourced-with-locator OR an honest declared
> gap. What changed is the SHAPE of the remaining work.

### 5.0 The three axes are NOT three sweeps of 1,559 — measured 2026-08-01

Live number: `python3 scripts/kbli_filiera/kbli_coverage_scoreboard.py`. At the time of writing:

| axis          | honest               | what the number means                                                                                                                                                                                        |
| ------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **licensing** | **1,559/1,559** 100% | 1,337 OSS-2025-sourced · 217 declared gaps · 5 PP28-located/vintage-pending. **Zero codes carry cross-vintage licensing in silence.**                                                                        |
| **crosswalk** | **1,338/1,559** 86%  | mechanical BPS ancestry WITH a lampiran locator, rendered as "provenance only, not a licensing claim". **0 adjudicated** — honest, not a defect, because the page makes no inheritance claim. 221 have none. |
| **PMA**       | **15/1,559** 1.0%    | **13** records name a per-code basis (`pma_official_basis`), 2 declare themselves unverified, and **1,544 assert a foreign-ownership verdict with nothing on the record saying where it came from.**         |

Three consequences, and they reorganise the whole programme:

1. **The licensing axis is closed for honesty IN THE DATA — the SURFACE is a separate claim, and the
   adversarial gate refused to let the two be merged.** The "99 codes still to adjudicate" this corner
   has been carrying are DECLARED GAPS in canonical, not lies in it; moving them from gap to verified
   value is product improvement, and F4's refresh loop does it for free when OSS publishes the scope.
   But data-honest ≠ page-honest: the conformance detector compares row COUNTS and `licensing_status`,
   never the `content` markdown the bot injects verbatim, so a stale licensing claim can survive inside
   a document whose row count is legitimately zero. And the gate found a live over-claim on the web
   surface — `LicensingSection` printed **"None retrievable (404)"** for gap codes while `no_oss_risk`
   is written for a missing dump line, ANY non-200 or `success:false`, i.e. an HTTP status we did not
   necessarily observe (corner rule F12, which the provenance panel's own comment quotes correctly
   while the panel then named the status anyway). Cured in this ship on all three strings. The
   content-level check is NOT built: ledger line, not a claim.
2. **The PMA axis is the remaining exposure, and it is the most-read fact on the product.**
   `pma_source` reads the identical string `"Perpres 10/2021, 49/2021"` on all 1,559 records — a layer
   annotation that can never explain a per-code verdict, the exact shape that made `moratorium.rule`
   useless as evidence on 111 pages (§1 L2.10). Curing it is ONE document parse + a join, not 1,559
   judgments — and the evidence is already on disk: the Perpres 10/2021 + 49/2021 lampiran were
   fetched and sha256-pinned into the Mini vault on 2026-07-19 and the manifest says, verbatim,
   _"fetched whole, NOT unzipped/parsed/extracted this pass"_.
3. **The crosswalk is not a third sweep — but it does NOT retire, and the first draft of this plan got
   that wrong.** pp28 feeds LICENSING on **5** codes, all adjudicated: that measurement stood up to the
   cross-family gate. What the gate refuted was the INFERENCE drawn from it. `pp28_sources` also drives
   the rendered **"Previous codes (KBLI 2020)"** element (`kbli-data.server.ts:323` → `page.tsx:891`)
   and the PMA provenance verdict (`kbli-provenance.ts:99`), and **121 codes have pp28 as their ONLY
   source of 2020 ancestry** (measured: 1,384 records carry `pp28_sources`, 221 carry no BPS ancestry,
   121 sit in both sets). So Batch B **re-aims** rather than retires: from "478 codes of licensing
   risk" to "121 codes whose rendered ancestry rests on a single unverified source, plus the 560-page
   BPS-vs-pp28 divergence". Recorded plainly because the error is instructive: I measured ONE consumer
   and generalised to all of them — the consumer-map rule this corner states (§4 rule 6), applied
   against its own author.

### 5.1 F0 — THE SCOREBOARD ✅ SHIPPED 2026-08-01

`scripts/kbli_filiera/kbli_coverage_scoreboard.py` + `_coverage_basis.py`, ratchet baseline at
`data/kbli-filiera/coverage-baseline.json`, armed in `kbli-filiera-vault-compilers.yml` (the `paths:`
trigger carries the canonical dataset, so a data-plane commit that strips provenance cannot dodge it).

Completion stops being "we finished the lots" and becomes a number that can only go up. The ratchet is
ONE-WAY and asserts nothing about whether a number is good: PMA may sit at 1% forever as far as CI is
concerned. A gate that stayed red until the programme finished would be muted within a week.

### 5.2 F1 — SIGILLA: make regression impossible BEFORE producing more truth

The defect under **every** scar in §1 is that the truth exists in six copies cured one at a time
(canonical, gold, the kbli-navigator fork, `kbli_documents`, KG, Qdrant). Every lot paid the same tax:
"cured on 3 surfaces of 4".

- ✅ **Detector shipped**: `scripts/kbli_filiera/kbli_surface_conformance.py` — read-only, compares
  canonical against `kbli_documents` by STATE (every row judged, every canonical code asked for),
  never by a list of codes. Exit 1 on divergence, exit 4 on cannot-verify.
- ⬜ **Derivation**: the six surfaces become BUILT from canonical rather than patched. Detection first
  is deliberate — it makes any new divergence loud immediately, while the builder is a bigger job.
- ⬜ **Arm the detector on a schedule** (it needs DB access, so it cannot live in CI): cron on Pro/Mini
  with a Telegram alert. Until then it is a manual run, and that is a ledger line, not a claim.

**What the detector found on its first run (2026-08-01), neither of which was in this corner:**

- **8 `pma_status` divergences**, canonical vs the store `chat_kbli` injects verbatim into the LLM
  context. Three are permissive: `50122`/`50123`/`50126` (sea cabotage) read **TERBUKA** in the table
  while canonical carries an **adjudicated 49% cap** quoting Perpres 10/2021 Lampiran III. Their
  siblings `50111`/`50121` read TERBATAS — so the answer a client gets depends on the last digit.
  The other five (`02101`, `02102`, `03110`, `03120`, `73100`) are restrictive-direction. **6 of the 8
  sync to an adjudicated basis; 2 (`02101`, `03120`) only sync to canonical's own value, which itself
  carries `pma_cap_verified: false` — the cure must not claim a truth fix on those two.**
- **80 codes where the channel serves NO licensing while canonical holds verified OSS-2025 rows** —
  **687 rows** in total, all from the trusted 2025-native core, including high-traffic activities
  (`82400` MICE organisers, `55400`, `56400`, the `65xxx` insurance family, `85xxx` education). Not a
  lie — the `content` column literally says `Perizinan: N/A` — but the WhatsApp/webchat channel is
  materially poorer than the website on codes where our data is at its best.

**Root cause of both, measured: 1,423 of the 1,563 rows (91%) have never been touched by any cure.**
Every cure to date ran `--only <named list>`, totalling 140 rows. This is the corner's own
meta-pattern — "the selector is the disease" — landing a fourth time, on the cure that closed the third.

### 5.3 F2 — THE PMA AXIS: the parse nobody has run (the bulk of the remaining work)

Same machine that already worked for the BPS crosswalk (Phase-0 gate: 20-page holdout, P=R=1.0,
cross-family blind verification):

1. Parser over the vaulted Perpres 10/2021 + 49/2021 lampiran → relation `(entry, cap, condition,
LOCATOR, vintage)`.
2. Acceptance gate on the BPS schema — holdout + cross-family blind + red-team. **No join before the
   gate is green.**
3. Join onto the 1,559 **through the BPS crosswalk** — never a bare-digit join (§4 rule 1). Three
   outcomes per code: covered-with-locator / ambiguous / no entry → declared gap.
4. **Only the ambiguous bucket** gets the expensive D0–D6 treatment below. That number is unknown
   today and **producing it is F2's first deliverable** — not a promise about its size.

**Why this is the phase that pays: it extinguishes FOUR of the six questions currently waiting on
Zero** (the "unverified cap" qualifier, the 17 `CHIUSO_PMA_NO_BESAR` codes, the 24 verdicts standing
on a disowned basis, the FATAL-2 re-label). Those questions exist because we have no locator. With a
locator they are not decided — they are answered.

#### 🟢 F2 LIVE STATE (2026-08-02) — step 1 DONE for both operative annexes

**The instrument was in no vault, and step 1 above said "the vaulted Perpres" as if it were.** Measured
2026-08-02: the vault held 22 PDFs (21 PP-28 lampiran + one BPS table) and **zero** naming either
Perpres, while `perpres-foreign-caps.json` recorded `transcribed_from: "page images rendered at
200dpi"` with no path, no URL, no sha256, and no `fetch-log.jsonl` line anywhere mentioned the
instrument. So the module whose docstring promises the PMA axis "a checkable source" named a source
nobody could reach. `vault_fetch_perpres.py` (PR #3529) pins all six BPK downloads —
`161562`-`161565` (49/2021 body + its three replacement annexes) and `154474`/`154475` (10/2021, the
annex zip marked `superseded`, arts. 3-5 replaced it) — with the declared role cross-checked against
the filename the server actually returns.

**Lampiran II (Koperasi/UMKM reservation) is COMPILED, not transcribed** —
`parse_perpres_lampiran2.py` → `data/kbli-filiera/perpres-umkm-reservation.json`: **181 rows from 180
ticks, 0 unresolved** (one tick carries two codes; `ticks` and `rows_emitted` are separate fields
because folded into one the output read "181 of 180"). The text layer is corrupted _deterministically_
and both halves of the inversion are derived from evidence, not assumed: the substitution table by
unique-candidate resolution (consistent over 33 observations, `t`→`1` twenty times and never anything
else), the DIALOKASIKAN/KEMITRAAN split inside a measured empty band (no tick between x=101 and 107).

`perpres_umkm_reservation_relation.py --check` buckets it — **and the buckets are the product, a flat
"N codes are wrong" would be the third defect this axis has produced**:

| bucket              | n      | what it means                                                                                        |
| ------------------- | ------ | ---------------------------------------------------------------------------------------------------- |
| `whole-row`         | **67** | live code, one readable activity, no grade qualifier, published open → **Zero's question (Legge 5)** |
| `segment-qualified` | 25     | reserves a construction grade, not the code                                                          |
| `retired-2020-code` | 30     | no 2025 descendant, no live page renders it                                                          |
| `kemitraan-no-bar`  | 57     | a partnership duty is **NOT** a foreign-ownership bar                                                |
| `agree`             | 2      | `47111`, `47222` — the two `kbli_eye` already names reserved                                         |

Those 2 in `agree` are the innocence control: the relation **corroborates what is already
known-correct** before naming 67 divergences. `segment-qualified` is a declared FLOOR — a qualifier can
live in the numbered parent heading (row 35 governs `42911`/`42912`/`42913`) and those rows are left in
the owner's list on purpose, because withdrawing a question on an inference is worse than asking one
too many.

**Lampiran III's 41 transcribed caps are now CORROBORATED by a second instrument** (PR #3530). Its
text layer is usable after all — same deterministic corruption, so invertible with the Lampiran II
table — and it is a different reader on a different day, which is what W100 demands (same-family
agreement certified 7 false-clean of 8 on this very programme). Result, asserted by MEMBERSHIP and not
by count: **40/40 codes agree in both directions**, and **37/40 caps** are positionally reachable and
all 37 match; the other three (`26513`, `30300`, `30400`) sit in a five-code stack and were read off
page 1 directly, so they are NOT claimed as cross-instrument. Standing guard:
`tests/test_perpres_l3_cross_instrument.py`, which SKIPS with an explicit CANNOT-VERIFY naming the
fetch command when the vault is absent.

#### 🟢 F2 step 3 DONE — the negative locator, and what the BODY actually says

**SHIPPED AND PROVEN LIVE 2026-08-02** (#3532 merged `223a8471`, #3536 the page-reader corpus;
#3531 closed as content-on-main — main was AHEAD on 3 of its 7 files and the 4 "lost" lines were
ones the later commit deliberately superseded, so merging it would have REGRESSED main; verified
blob-per-file, never by ancestor or patch-id, W88).

The citation is on the page. `/kbli/56101` reads `Basis: Perpres 10/2021 Pasal 3(1)(d) — no annex
names this activity`; `/kbli/55203` reads `Perpres 49/2021 Lampiran II (Koperasi/UMKM) via
KBLI-2020 55193`; `/kbli/11010` reads `Pasal 2(2)(b) (as amended by 49/2021) — closed by name`.
65 distinct citations over 1,559 codes, 0 without one. Additive: no verdict, cap or label moved.

**TWO consuming surfaces, not one — and the second was nearly missed.** `page.tsx:347` renders the
visible line, but `api/kbli/gold/[code]/route.ts:31` serialises the whole `pma` object, so the field
rides along into that JSON. Both were proven against a baseline recorded BEFORE the merge
(`'Basis:'` = 0 with the code present 3× as the positive control; `pma` carrying 6 keys and no
`citation`), and with a negative control per page (each carries **0** occurrences of `Pasal 6(3a)`,
which belongs to `46333` — so it is not a blanket string).

**Merging did not publish it.** The production deployment was `READY` for 25 minutes while
`balizero.com` — and the project's own `mouth-git-main` alias — still served `1050e5c99`. Git-created
production builds on this project land `readySubstate: STAGED` and never self-promote (ledgered
2026-07-30); the session ran `POST /v10/projects/<id>/promote/<dpl>` → HTTP 201 and prod moved within
15s. Read `/api/health`'s `.commit` (baked from `VERCEL_GIT_COMMIT_SHA`, recomputed per request) as
the arbiter — a `?cb=` query does NOT bust the page cache on this route, so the header is not one.

`perpres_body_default_relation.py --check`. This is the locator for the ~1,288 codes **no annex
names** — the block that until now carried `pma_source: "Perpres 10/2021, 49/2021"` with no article
behind it, i.e. a blanket attribution rather than a citation. Three corrections came out of reading
the body instead of assuming it:

**1. "Absent from both annexes" is NOT "residual".** The body names six codes itself, and 49/2021
inserted both lists: **Pasal 2 ayat (2) huruf b** → `11010`/`11020`/`11031` tertutup (the alcohol
INDUSTRIES); **Pasal 6 ayat (3a)** → `46333`/`47221`/`47826` under "persyaratan Penanaman Modal
lainnya", a fourth regime that is deliberately not a percentage and not in Lampiran III. Two of the
six (`11031`, `47826`) are not in the 2025 catalogue at all and the module reports that rather than
absorbing it. Note also **`46333` publishes TERBUKA/100%** while the body puts it in that
strictly-controlled category — the same defect `47221` (correctly TERBATAS/special) does not have.

**2. The default is real and it has a citation.** **Pasal 3 ayat (1) huruf d + ayat (2)**: the
residual category "dapat diusahakan oleh semua Penanam Modal". 49/2021's Pasal I touches Pasal 2,
Pasal 6 and the three lampiran — **Pasal 3 and Pasal 7 are untouched**, verified in the amending
instrument itself (W90: the ground truth ages too).

**3. Pasal 7(1) gives a REVIEW QUEUE, not a bar — and the first draft got this wrong.**
**Pasal 7 ayat (1)**: "Penanam Modal asing **hanya dapat** melakukan kegiatan usaha pada **Usaha
Besar**". I first read that as `no Besar ⇒ no PMA` and wrote it as a citation. **An independent
cross-family legal review refuted it before ship, and the refutation is right on the text**: the
article conditions the INVESTOR and its project — it can stop a PMA that cannot qualify as large —
but it does not convert the activity into one closed to foreign investment; only a reservation, a
cap, or a rule making large-scale operation unavailable does that. And `per_skala` is OSS
**licensing** data: "OSS publishes no Besar row" is not the legal fact "this activity cannot be
conducted at Besar scale" — the same conflation the module's own three-state `besar_state` refuses
one level down, committed one level up. So the output is a queue of **23 codes published open with
no Besar row** (villa, homestay, youth hostel, kedai minuman, management consultancy, rumah pijat,
hair salon, beauty care, sports facilities), each carrying two questions: does an actual
reservation/cap apply, and can it in fact be run at Usaha Besar? Ledgered `operator[business]`. The
safe interim treatment is a caveat on the page, never a re-label to closed.

**The 23 are not one population — measured by WHO names them (2026-08-02).** The queue was handed to
Zero as 23 undifferentiated codes, which overstates what has to be decided: splitting it with the
module's own selector (`pasal7_review_flags`, never a hand-rolled re-read of `per_skala`), then
joining each annex-named code to `perpres-umkm-reservation.json`, gives **three tiers of evidence,
not one**:

- **`95291`** (Vermak pakaian) — the annex names the **2025** code itself, `whole-row`. A reservation
  genuinely applies; only the Besar question is open.
- **`43110`** (Pembongkaran) — the annex names the 2025 code, but the row is `segment-qualified` to
  construction grade _madya_, so the reservation does **not** cover the whole code.
- **7 codes** — `55201` `55203` `55209` `79903` `96100` `96210` `96220`: the annex names a **retired
  KBLI-2020** code (`55130` `55193` `55199` `79921` `96200` `96111` `96112`), and the attachment to
  the 2025 code is **our crosswalk**, declared `mechanical-only`. The instrument never wrote these
  digits — same 102-code dependency as above, here landing on the daily-question codes.
- **14 codes** — named by nothing at all. Only the factual "can this be run at Usaha Besar?" question
  remains, and our data cannot answer it.

All nine annex-named rows sit in the **`dialokasikan`** column (an actual reservation), none in
`kemitraan` (a partnership duty, **not** a foreign-ownership bar — the distinction §L2.11 paid for).

**🔴 AND THE REFUTED READING IS ALREADY LIVE — the caveat is not the open question (PROVEN on prod
2026-08-02).** This section says "the safe interim treatment is a caveat on the page, never a
re-label to closed", which presumes the page is currently neutral. **It is not.** `curl` on
`balizero.com/kbli/55203` (Vila) returns, client-facing:

> 🚫 **Reserved for MSME — closed to PT PMA** · "This activity is reserved for micro/small/medium
> enterprises and closed to a PT PMA · **confidence HIGH**" · reason: _"OSS has no Usaha Besar scale
> row -> reserved for UMKM; a PT PMA (Usaha Besar by law) cannot register. [structural]"_ · prose:
> _"In Bali, that path is closed today for a PT PMA."_

That reason **is** `no Besar ⇒ no PMA` — verbatim the inference the cross-family legal review
refuted two paragraphs above. It is not a dataset annotation: `l4_bali` reaches the client through
the page body, the 🚫 badge, the **OG image** (`api/og/kbli/[code]/route.tsx:38`) and the blocked-%
on the **index** (`kbli/page.tsx:36`).

Measured on the rendering dataset (`KBLI_2025_FINAL_CLEAN.json` → `baliL4`): **39 codes** carry
`CHIUSO_PMA_NO_BESAR`, all with `blocked: true`.

- **22 of them ARE this queue**, every one at `confidence: HIGH` — villa, homestay, youth hostel,
  kedai minuman, management consultancy, rumah pijat, salon, barber, laundry, tailoring.
- **17 are the empty-`per_skala` codes**, all at `confidence: LOW` — 13 of them the `931xx`
  sports-club family. The confidence field already separates the two, which is the one honest part.
- **23 − 22 = 1**, and it is `93114` — exactly the code this section already flags as left
  `APERTO_BALI_RISCHIO_ALTO` on the evidence that closes the other 22. The numbers close.

**So the question put to the codeowner has the wrong shape.** It was asked as "does an actual
reservation apply — should we add a caveat?"; the product **already answers it to clients in the
affirmative, at HIGH confidence, on the daily-question codes**. The live options are keep / soften /
withdraw a claim that is already being made, not whether to start making one. Still `operator[business]`
(a re-label of client-facing pages is Legge 5) — but it is now a decision about a live assertion, and
the sequencing changes with it: this outranks the caveat wording, because a caveat added under a 🚫
badge would qualify a verdict the same page states as HIGH-confidence fact.

**The other 17 are worse, and the dataset says so itself.** Cross the 39 against the module's
three-state `besar` and the split is **perfect, with no mixing**: the 22 at `HIGH` are `besar:
absent` (OSS publishes scale rows, none of them Besar — a weak fact, but a fact); the 17 at `LOW`
are `besar: unobserved` — **`per_skala: []`**, no scale rows at all. Two things follow, both
measured on the rendering dataset and confirmed on prod:

- **All 17 carry, in their own `reason` text, the phrase _"the verdict cannot currently be
  re-derived"_** (the risk-tier rows it was read from were set aside as unverifiable for KBLI 2025).
  The record states the verdict is unsupported **and the page still renders the categorical 🚫
  badge**; the only difference from the 22 is the word `LOW` printed beside it. Checked live on
  `70100` (Kantor Pusat — a code clients actually use) and `93121`.
- **7 of them assert a POSITIVE fact the record cannot support**: _"OSS has no Usaha Besar scale row
  **(only Mikro/Kecil/Menengah)**"_ — a claim about which rows OSS publishes — on codes whose
  `per_skala` **and** `per_skala_legacy` are both empty. `52211` (Terminal Darat) and six `931xx`
  sports clubs. Saying "only Mikro/Kecil/Menengah" is claiming to have read rows that are not in the
  record: not a debatable reading of Pasal 7, a statement contradicted by our own data.

That last group is a different kind of defect from the queue: the queue is a **legal reading** the
codeowner must rule on (Legge 5), while "we saw only M/K/M" is a **factual assertion our data
refutes**. Kept together here and NOT patched in this pass — the fix still edits client-facing text
on live pages, so it goes through the adversarial gate with the rest — but it should be ruled on
first and separately, because no ruling on Pasal 7 makes that sentence true.

**🔴 AND THERE IS A FIFTH SURFACE, WHICH ANSWERS THE OPPOSITE — 39 of 39 (2026-08-02).** The count
of "four consuming surfaces" above is what `l4_bali` reaches. **The channels are a fifth, and they
do not carry it at all.** Asked the single most common commercial question this agency receives —
_"Can a foreigner open a villa rental business in Bali with a PT PMA? KBLI 55203"_ — `chat_kbli`
(the WhatsApp/webchat path) answers on prod:

> **"Yes, a foreigner can absolutely open a villa rental business in Bali using a PT PMA"** …
> "KBLI 55203 is **TERBUKA (Open) to 100% foreign ownership**."

The same product, same code, same "in Bali" question, **opposite verdicts**. And the channel is not
ignoring Bali: it renders a whole "Bali Reality Check" section (zoning, banjar, PBG, nominee) — it
considers Bali and says yes. Both sides even start from the SAME premise, `PT PMA = Usaha Besar by
law`: the page turns it into a bar, the channel into a capital threshold.

Structural, not one LLM sample — measured read-only on `kbli_documents`, the store `chat_kbli`
injects verbatim, over all 39: **rows 39 · carrying `l4_bali` 0 · `pma_status = TERBUKA` 39 ·
content mentioning any bar 0.** Innocence control, so the negative means something: the same store
correctly carries `TERTUTUP` for `11010`/`11020`/`47222` and `TERBATAS` for `50111`. It is not blind
to restriction in general — it is blind **specifically to the Bali layer**, at an agency whose whole
market is Bali.

Note the direction before "fixing" it: the page's verdict is the **refuted** reading, so the channel
may be closer to the law — but it qualifies nothing, and answers "absolutely" on codes we
internally treat as disputed. Two over-confident surfaces pointing opposite ways; the divergence is
itself the signal. This is why (a) and (b) below cannot be ruled on by looking at the page alone.

**The channel does not merely LACK the verdict — it carries prose pushing the other way, and that
is measured, not inferred.** The KG's rich `kbli` nodes key on `properties->>'kode'` (the
`KBLI <code>`-named rows are empty skeletons — a first pass keyed on `name` read **0 of 39** and was
measuring the dedup disease, not the data). Keyed correctly: **38 of 39** present, **all 38**
`pma_status: TERBUKA`, **0** carrying `l4_bali`, and **13** carrying a `baliContext`. That field is
**editorial market prose, not a legal verdict** — `55203` reads _"**🏝 The Bali Villa Market (Reality
Check)** — Villas ARE Bali's tourism identity: Seminyak, Canggu, Ubud…"_, `93122` lists Bali's golf
clubs. And it reaches the channel: `kbli_documents.content` contains both _"Reality Check"_ and
_"tourism identity"_ verbatim. So the LLM answering on WhatsApp is handed an enthusiastic market
description of exactly the activity the page marks 🚫, with no verdict beside it — which is why its
answer has a "Bali Reality Check" section and still says **yes**.
_(Correction to my own measurement, kept because it is the failure this corner exists to catch: I
first counted "3 baliContext mentioning a bar" using `ILIKE '%Besar%' OR '%clos%' OR '%MSME%'` —
those match ordinary words like "closest". Reading the 13 in full, **none** states a restriction.
Family #3 in my own probe.)_

**🟢 THE HONEST WORDING ALREADY EXISTS IN THE PRODUCT — on the index, and it never reaches the code
page (2026-08-02).** `/kbli` carries a "Blocked in Bali" card whose `title` reads, live:

> _"Bali Zero's **conservative posture** on the 13 May 2026 provincial moratorium: low and
> medium-low-risk activities are treated as closed to foreign-owned companies (PT PMA) pending
> clearer national guidance — **a working assessment, not a certified legal determination**. Every
> code page shows our current verdict."_

That is exactly the register this queue needs: it names the claim as OURS, gives a basis, and
refuses to pass as a legal finding. **The code page states the same verdict at `confidence HIGH`
with a categorical 🚫 and no such qualifier.** So the cure does not have to invent a wording — the
product already wrote one, one surface away from where the verdict is rendered.

**But the two surfaces give DIFFERENT REASONS for the same verdict, and the index's is measurably
too wide.** The code page attributes closure to **scale** (`no Usaha Besar row`); the index
attributes it to the **moratorium + risk tier**. Measured on the rendering dataset: the 22 closed
codes that have scale rows are indeed all low/medium-low risk (11 `Rendah` + 11 `Menengah Rendah`,
the other 17 have no rows at all) — so the index's rule is _consistent_ with them. It is its
CONVERSE that fails: **405 codes carry only low/medium-low risk, and just 22 are rendered closed —
383 are not.** Read literally, the index tells a client that low-risk activities are treated as
closed, when the product does that to **22 of 405** (5.4%). The operative criterion is low risk
**AND** no Besar row; the index states only the first half.

Net: **the index has the honest register and the wrong rule; the code page has the right rule and no
register.** Neither surface is fit to be copied wholesale, and the fix is to combine the halves that
already exist rather than to draft anything new — which is why this belongs to the same ruling as
(a) and (b) below, not to a separate "wording" task.

**⚠️ The obvious cure is a trap: "sync `l4_bali` to the channels" would propagate the REFUTED
reading onto a fifth surface.** Sequencing matters more than the wiring here — rule the verdict
first, wire second, or the tidy-looking fix ships the error further. The wiring itself is
understood and small (grounded this session, so nobody has to re-derive it): the router builds its
LLM context on **two** branches and neither has a place for a Bali layer —
`kbli_notebook_chat.py:388` emits only `code / title / description / pma_status / risk_category`,
and the `full_content` branch above it passes the row's `content` verbatim, which is exactly the
field measured at **0 of 39** mentions. Nor is the omission a policy choice: `kbli_documents` has no
general populator at all (only the two `*_cure.py` scripts write to it), so the store was seeded
before the Bali overlay existed and simply never re-synced. **The gap is mechanical, the fix is
not** — do not let the ease of the wiring pull the decision forward.

**Reconciliation, because two numbers here differ by one and both are correct:** `besar absent` is
**24** = 10 `named-in-annex` + 14 `residual-besar-absent`. The queue is **23** because the tenth,
**`79110`** (Agen Perjalanan), is already `TERBATAS` — it is not "published open", so it never enters
a queue about codes published open. (Measured with the report's own field, `besar`; a first probe
keyed on `besar_state` returned **0 of 24** and was measuring its own poverty, not the data.)

| locator (which instrument names it) | n       | OSS scale data (NOT a verdict) | n      |
| ----------------------------------- | ------- | ------------------------------ | ------ |
| `named-in-annex` (L-II / L-III)     | 270     | besar **observed**             | 1318   |
| `priority-lampiran-i` (Pasal 3(1)a) | **175** | besar **absent**               | **24** |
| `residual-besar-observed`           | 882     | besar **unobserved**           | 217    |
| `residual-besar-unobserved`         | 214     |                                |        |
| `residual-besar-absent`             | 14      |                                |        |
| `body-tertutup` / `body-other-req.` | 2 / 2   |                                |        |

**4. Lampiran I was omitted, and that cost 175 wrong citations** — the same review caught it. A code
in `Daftar Bidang Usaha Prioritas` is **Pasal 3(1)(a)**, so "named by nothing" was quietly including
category (a) and citing the residual article `3(1)(d)` for 175 codes. Priority _incentivises_ and
restricts nobody, so no ownership verdict was wrong — the **locator** was, which is this module's
entire product: the blanket-attribution defect reproduced one annex to the left.
`parse_perpres_lampiran1.py` compiles the code set only (194 codes, 46/70 pages, page-1 sample
guard); a restriction outranks a priority listing, so the 46 codes in both report as reserved.

**Locator and scale are TWO AXES, and the first draft collapsed them.** As a partition the report
found only 14 — because for the ten codes that are BOTH annex-named and Besar-less the scale question
vanished into the winning bucket, and those ten are villa/homestay/salon/beauty, the daily questions.
Same lesson as the enum: a third state is a separate axis or it is invisible.

**The crosswalk is load-bearing**: the annexes speak KBLI 2020, so **102 codes** reach a restriction
only through `bps_2020_ancestors` (`55203` Vila via `55193`). Joining on identity alone would have
published all 102 as open — freedom the law does not grant. Declared and not laundered: every
crosswalk block says `mechanical-only` / `not-adjudicated`, and 221 records have none at all.

**Our own overlay already took this reading, and misapplies it in BOTH directions**: of the 39
`l4_bali.status == CHIUSO_PMA_NO_BESAR`, **22 are corroborated** by observed scales, **17 close on an
EMPTY `per_skala`** (a gap in our data reported as a bar in law), and **`93114` is left
`APERTO_BALI_RISCHIO_ALTO`** on the evidence that closes the other 22. The rule is not the disease;
the selector is (family #3). Ledgered.

**Declared limits** (the body's own carve-outs, none of them visible in a KBLI record, so the module
cannot decide them): **Pasal 8(1)** — Lampiran III does not apply inside a KEK, and 8(2) moves the
Pasal 7 floor for tech start-ups there; **Pasal 6(4)** — the cap does not bind investments approved
before the Perpres, nor investors with treaty privileges. It speaks for a NEW investment, general
regime, outside a KEK.

**And the rule that governs any application of all this**: a fourth `pma_status` value would render
as **"Open"** on all 1,559 pages (`kbli-data.server.ts:365` returns `"open"` for anything but
TERBATAS/TERTUTUP). Third states are separate axes, never new enum members. Corollary the reporter
now enforces: "open" is read as _what the renderer calls open_, never as `== "TERBUKA"` — a null
status renders open and a TERBUKA-only filter is blind to exactly the codes the page is most
generous with.

### 5.4 F3 — the two decisions that survive, and they come AFTER F2

- **(a)** the **560** codes rendering two different predecessors side by side (official BPS vs the
  legacy pp28 element): keep both with a source note / BPS authoritative / adjudicate.
- **(b)** how the page states whatever residue F2 leaves in "declared gap".

Deliberately not asked now: asking now means deciding on the large population. F2 shrinks it.

### 5.5 F4 — root and upkeep

- **KG generator** — it does not exist; edges are deleted by hand and the 68% dedup disease is still
  at the root. **Quantified read-only 2026-08-02, and the shape is a clean discriminator**: of
  **13,633** `entity_type='kbli'` nodes only **1,558 carry any data** (11.4%) — and `entity_id`
  predicts it perfectly: every `kbli:<code>` row is rich (1,558/1,558), every other form is empty
  (`kbli_<code>` 5,950 · `kbli_kbli_<code>` **double-prefixed** 4,986 · other 1,139, all with zero
  `pma_status`). **The 12,075 empty ones are not inert orphans: 9,882 of them are reachable by an
  edge** (against 1,556 reachable rich nodes), so a traversal landing on one reads nothing and
  degrades to `"Verify at OSS"` — honest, but the answer is lost. Extracting the code from the id
  also yields **8,156 distinct entities against a 1,559-code catalogue**, of which 6,598 have no
  rich node at all: 3,455 not numeric, 2,032 digits of the wrong length, and **1,111 well-formed
  5-digit codes with no data anywhere** (the phantom-code family, an order of magnitude above the
  77 already ledgered on the gold side).
  _Two probe corrections worth keeping._ **(1)** A first pass keyed on `name` reported **0 of 39**
  KBLI nodes carrying `pma_status`: the rich rows are named by their TITLE (`VILLA RENTAL (AKTIVITAS
VILA)`), only the empty skeletons are named `KBLI <code>` — the probe was measuring the dedup
  disease and calling it absence. Key on `properties->>'kode'`. **(2)** I suspected
  `kbli_notebook_chat.py:1089` (`name ILIKE $1 OR entity_id ILIKE $1` … `LIMIT 5`, no `ORDER BY`)
  could drop the rich node behind duplicates. **Measured and REFUTED**: max rows per code is **3**,
  so no code exceeds the limit. Recorded as refuted rather than dropped, so nobody re-derives the
  same suspicion — but any future `LIMIT` on that query is one duplicate-family away from becoming
  real, and the free fix is to order by `entity_id LIKE 'kbli:%' DESC`.
- **Refresh loop** OSS/JDIH: the 221 no-scope watchlist self-resolves when OSS publishes a scope, and
  the 217 declared gaps become verified values **with no human work**. This is the only path by which
  the "99 missing" close themselves.

### 5.6 What this plan RETIRES (say it out loud, it contradicts signed work)

- **Batch B as a 478-code LICENSING sweep** — that thesis is defused by measurement (pp28 load-bearing
  on licensing: 5 codes). It is **re-aimed, NOT retired**: the cross-family gate showed pp28 still
  solely carries the rendered 2020 ancestry on 121 codes, so the batch shrinks and changes target
  rather than disappearing. This narrows a SIGNED design (#2801 REV-4b); its Phase-0 parser and the
  populate step stay — they are what made the measurement possible.
- **Batches C/D as sweeps** (~1,438) — never had a measured risk thesis. If the scoreboard grows one,
  they come back.
- **The Tier-4 AQL ratification waiting on Zero** — it sampled a sweep we no longer run.
- **"99 codes to adjudicate"** → 217 declared gaps that F4 closes for free.

### 5.6bis This plan was gated before it shipped, and the gate changed it

Generator ≠ grader (CLAUDE.md §6): the plan's four claims went to **Codex GPT-5.6-sol at xhigh,
instructed to refute**. It returned three blockers, two of which changed this document and one of
which changed the code:

- **C4 refuted** — the Batch-B retirement did not follow from a licensing-only measurement (above).
- **C2 narrowed** — "closed for honesty" is true of the data, not proven of the rendered surface;
  it also found the live `(404)` over-claim, now cured.
- **The ratchet was gameable and this was reproduced, not argued**: wiping `per_skala` on all 1,342
  codes with rows turns every one into `declared_gap`, which is honest, so the count-only gate scored
  a PERFECT 1,559/1,559 while the entire verified licensing layer was destroyed — green light,
  measured on the real dataset. Fixed with a per-code STRONG-state arm (a code that held a government
  locator may never stop holding one), plus catalogue-shrink, duplicate-code, adjudication-fall and
  guarded-`--update-baseline` arms.
- **C3 survived**, with its wording tightened to what was measured: "PMA is the largest MEASURED
  exposure — 1,544 of 1,559 records bare", not "the real remaining exposure".

Declared limits of that gate, so nobody reads it as more than it was: its capture begins at finding
**#2**, so finding #1 was lost and is NOT accounted for here; and it could not reach the production
database, so nothing it says about deployed state was verified by it.

### 5.7 The arithmetic that makes this decisive and the previous roadmap not

Batch A adjudicated 114 codes in ~4 days of full conductor attention, per-code, paying the 4-6-surface
tax every lot. At that rate three axes × 1,559 is **~4 months** sequential with a human gate per lot.
This plan runs **one parse** where the previous one ran 1,546 judgments, and puts the invariant BEFORE
the production instead of after.

---

### Seats (unchanged — they govern F2's ambiguous bucket) — family-independent by design

- **Mente immobile / final gate**: **Opus 5** (xhigh effort, interactive) — RULED 2026-08-20, was
  Fable 5 (Fable is out of the workflow, CLAUDE.md §5) — batch plans + acceptance
  criteria, quarantine adjudication, the final EMPIRICAL gate against raw vault evidence, sign-off.
  Never extracts, never writes data. Window dead → program SUSPENDS at a batch boundary (durable
  state carries; no weaker substitute for the final gate).
- **Extractor**: **Sonnet 5** (implementer tier) — reads located rows, writes candidate facts.
- **Vision locator**: **qwen2.5vl:7b** (Ollama on Mini) — page/row triage on 300-dpi renders,
  LOCATOR ONLY, never the reader.
- **Red-team**: **Codex GPT-5.6-sol** (xhigh, read-only sandbox) — attacks mapping proposals + batch
  reports. Family-independence: extractor ≠ refuter ≠ red-team FAMILIES per batch.
- **Operator**: **Zero** (Legge 5) — publish decisions, consents, the F3 editorial calls.

### Per-code scientific protocol — dossier D0→D6 (workflow doc §3)

Retained because F2's ambiguous bucket is exactly what it is for. Each batch pins a vault-manifest
revision; per-code lease `agent_lock:kbli-dossier:<code>`.

- **D0 Evidence pull** (deterministic): vault items for the code — BPS row, dated OSS snapshot, PP28
  lampiran rows. Endpoint inventories + negative controls so ABSENT is corroborated, not assumed.
- **D1 Crosswalk adjudication**: NO deterministic acceptance, not even 1-to-1 (uraian-equivalence
  check) — the 2020 ancestor is a candidate, the use-case adjudicates.
- **D2 Extraction** (image-verified, self-confirming): qwen2.5vl locates the row → Sonnet reads it;
  self-confirming to resist locator poisoning.
- **D3 Assembly** (deterministic): strict schema, per-fact provenance (locator + vintage) + confidence.
- **D4 Discrepancy & completeness scan**: cross-layer comparison; completeness invariants catch
  omission blindness.
- **D5 Independent verification** (anti-correlation): the refuter does BLIND re-extraction, does not
  grade its own work; divergence → quarantine. Cross-family and image-grounded, never a review of the
  text-pack (W100).
- **D6 Batch gate**: deterministic censuses + gates G13–G17 → **Opus 5 xhigh-effort final empirical
  gate** (RULED 2026-08-20, was Fable) against RAW vault evidence, never seat summaries →
  sign-off → compiler emits canonical vNext.

### Definition of DONE (unchanged, now machine-computed)

Every one of the 1,559 codes: risk / licensing / PMA / Bali facts each carry a government locator +
vintage OR an honest declared gap; zero silent cross-vintage fill; KG regenerated from a real
generator; gold/editorial invalidated-and-rebuilt where their source changed; a running refresh loop.
The first clause is now `kbli_coverage_scoreboard.py`, and CI defends it.

## 6. WHO IS WHERE / MEMORY POINTERS

- Sessions are ephemeral; the durable state is on disk (this file + `data/kbli-filiera/` + the memory
  files below). A Codex red-team seat is on-demand: give it THIS file + the artifact under review.
- **Deep-dive memories**: `ops_kbli_fase1_cure_applied_residual_risk_editorial_2026_07_17` (the 8-code
  cure state, all layers) · `discovery_kbli_49213_akdp_collision_pilot_a1_2026_07_17` (pilot A1) ·
  `discovery_kbli_68112_code_collision_pp28_vs_bps_2026_07_16` ·
  `discovery_kbli_noscope_codes_per_skala_not_from_oss_2026_07_16` ·
  `discovery_kg_perizinan_name_dedup_disease_2026_07_16` ·
  `lesson_kbli_remap_gate_context_beats_title_2026_07_16` ·
  `feedback_merged_is_not_live_consumer_map_first_2026_07_16` ·
  `discovery_oss_rba_kbli_api_extraction_2026_06_19` ·
  `feedback_session_owns_full_ship_lifecycle_2026_07_16` · `fact_bkpm_5_2025_paidup_capital_2_5_mld_2026_07_16`.
