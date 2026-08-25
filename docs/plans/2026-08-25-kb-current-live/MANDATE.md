# MANDATE — the knowledge base answers correctly, as of 2026-08-25

> For an **Opus 5 orchestrator session**, fresh context.
> Procedure: `docs/factory/ASSEMBLY-LINE.md`. Where this mandate and that file conflict,
> this mandate wins **for the KB only**.
> Everything marked MEASURED was measured on 2026-08-25 against production. Re-measure
> before you plan — these counts move under you.
> Supersedes `docs/mandates/2026-08-25-kb-refresh-squads.md` (deleted in the same commit):
> same work, but its deliverable was prose in `research/`, which is exactly the artifact
> the assembly line forbids.

---

## 0. What product this is

Not a corpus. **A person asks Bali Zero a question and gets the right instrument, the right
article, and a citation that is still in force.** The corpus is the implementation.

So the unit of done is never "N documents ingested". It is a probe question answered
correctly out of `legal_unified` — the collection the retrieval path actually reads.

**A count is not coverage.** MEASURED: 84,361 points, of which 31 documents answer with
their own commentary in the article slots — 2,042 fragments. Those documents count as
present and are wrong.

---

## 1. WORK ITEM ZERO — nothing opens until this closes

`legal_unified_2026`: **15,410 points, written nightly by
`infra/eventbus/regulatory_ingest_runner.py`, read by nothing.** That string appears nowhere
in `apps/backend-rag/backend/` outside the runner; `backend/core/collection_registry.py`
maps every legal alias to `legal_unified`. A year of nightly collection is in a drawer.

Close it in one day: measure it (distinct documents, dates, payload shape, and how much is
ALREADY in `legal_unified` — compare by `document_id` **and** by content, never by count),
decide one of promote / point a reader at it / retire, execute, and land a test that fails
if the runner ever again names a collection the registry does not map.

Open no lane before this closes. Otherwise the whole campaign lands in the same drawer.

### CLOSED 2026-08-26 — and the paragraph above is wrong about the verb

**Status: closed.** The measured record is `kb/inventory/legal_unified_2026.yaml`
(`kind: retired_collection`), read by `test_kb_inventory_contract.py` and
`scripts/kb/kb_inventory_probe.py`. Decision: **`retire_as_target`**. Enforcement:
`scripts/ci/ingest_target_lint.py` — 16 declared ingest entrypoints, every target
resolving through the registry, 0 undeclared; exercised by 22 tests in
`backend/tests/unit/core/test_ingest_target_registry.py`. Nothing may name that
collection again without failing CI.

**Read the paragraph above as history, not as fact.** It says the collection is
"written nightly." It is not, and the correction changes what the cure had to be:

- The collection is **frozen, not filling** — 15,410 points / 18 documents,
  byte-identical to the figures recorded on 2026-05-16 in
  `research/nb-lifecycle/2026-05-16-r5-phase2-indexing-parity.md:202`. Nothing has
  been written to it in over three months.
- The nightly watcher **ingests nowhere at all**. `~/scripts/regulatory-watcher-run.sh`
  contains zero occurrences of qdrant / upsert / ingest / embed; it writes a delta
  JSON and a Telegram alert. The runner that _names_ the collection has never run
  and could not: it builds its FileHandler at import and its log file does not
  exist, and the ingestion service refuses any target outside
  `ALLOWED_CANONICAL_COLLECTIONS`.

So this was never "a drawer nobody opens." It is a dead 2026-05-16 artifact **plus
a regulatory watcher whose findings have never reached the KB by any route** — which
is the larger defect, and it is NOT cured here. It is `WIZ-1` in that inventory's
`open_findings`, severity high, and it stays open.

**Do not promote this collection wholesale.** 11 of its 18 documents carry an
identity contradicting their own text: a Klaten regency price schedule labelled
"Permenkumham 22/2023 — Visa dan Izin Tinggal", a Tegal office-correspondence
manual tagged `category: visa` and titled "Golden Visa C-318". Five of those broken
identities are **already in `legal_unified`**, the collection production reads
(`WIZ-3`) — a live retrieval defect, not a stranded-content one.

**Nothing was deleted, and nothing may be** on this evidence: the containment proof
hashes only fragments of ≥40 normalized characters, so shorter fragments are
unproven, and §4.6 says one uncovered fragment means do not delete.
`deletions_authorized: false` is recorded in the file itself.

Eight findings (`WIZ-1`..`WIZ-8`) were measured here and handed to lanes rather than
cured inside this item. They are the reason this section closes without the campaign
being over.

---

## 2. The five artifacts — nothing else survives

**The catalogue is a data file, not a document.** This is the single change from the first
draft of this mandate. A readable table is GENERATED from the YAML by a script; the YAML is
the truth. Prose in `research/` that no gate reads does not get written.

| Artifact                    | For the KB                                                                                                                                                                                                                                                 | Consumed by                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `kb/topics/<t>.yaml`        | who asks, the questions this topic must never get wrong, primary metric, ≤3 guardrails, kill criterion, owner decisions log                                                                                                                                | G0 owner signature; the probe generator                                             |
| `kb/journeys/<t>.yaml`      | the probe set: question → expected `document_id` + article + one verbatim phrase that MUST appear in the answer's context                                                                                                                                  | the gauntlet job, CI                                                                |
| `kb/inventory/<t>.yaml`     | the catalogue AS DATA: every instrument in scope — type/number/year, date in force, status (in-force / superseded-by / revoked), presence (present / absent / wrong-identity / damaged), official URL, and for every gap the reason it could not be closed | the coverage gate; the probe generator; a rendered table for a human under pressure |
| ingestion code + tripwires  | the parser/identity fixes each lane needs                                                                                                                                                                                                                  | CI                                                                                  |
| `kb/ops/probe_retrieval.py` | the scheduled probe + dead-man switch                                                                                                                                                                                                                      | prod                                                                                |

Evidence of a topic being current is the probe job's output, never a hand-written report.

---

## 3. The eight stages, mapped

**G0 — INTENT.** Per topic, the orchestrator drafts `topic.yaml` including **the questions
this topic must never get wrong** (aim for ~20). These are owed by Zero, and **nothing
blocks on them**: draft them as a prepared proposal, build against the draft, collect the
signature at the end (§7). Gate: a named asker, a falsifiable metric, ≤3 guardrails, a kill
criterion.

**G1 — GROUND.** Every instrument in the inventory is tagged `verified` / `assumption` /
`unknown`. Gate: **no `unknown` may control an answer a client is given.** An instrument
whose identity is an assumption is not ingested; it is an inventory row with a reason.

**G2 — JOURNEY, red first.** `journeys/<t>.yaml` is written BEFORE any ingestion, **by a
different family than the one that will ingest it.** Gate: the probe suite runs against
production TODAY and fails RED cleanly — a probe that is green before the work is a probe
that proves nothing. Every sad path is named and owned: wrong identity, superseded article
answering with old text, commentary answering as law, no answer at all.

**G3 — CONTRACT freeze.** The inventory schema, the probe schema, and the payload contract
(both generations, §4.1) are frozen. Later changes go through the orchestrator.

**G4 — PARALLEL BUILD.** Lanes per §5. PRs ≤~200 logic lines. **One cross-family refuter per
PR**, dispatched against an EXTRACTED artifact at a fixed commit — never a live ref, never
while the generator is still writing (`ASSEMBLY-LINE.md`, verification economics).

**G5 — GAUNTLET.** The full probe suite green **against the real production collection** —
not a fixture, not a mock. A mock that answers where production errors is not a test:
MEASURED 2026-08-25, seven green tests over 100% broken ingests, every one mocking the call
the server was rejecting. Verdict is binary: SHIP or a one-paragraph BLOCK.

**G6 — SHIP.** The corpus IS production, so "flag off" has no analogue and reversibility
takes its place: **every mutation is reversible until the probe is green.** Snapshot the
points you are about to retire to a file, keep the snapshot 7 days, and never retire the old
copy before the new one answers the probe. Rollback = restore the snapshot.
Then the 5%-real-users step, in KB form: **the Bali Zero person who actually answers clients
in that domain asks five real questions through the real surface and confirms.** That is an
owner/team gesture (§7), and it is what declares a topic current — not a green test.

**G7 — OPERATE.** `kb/ops/probe_retrieval.py` runs on schedule against prod and pages on a
BUSINESS invariant: "every probe question in this topic still returns its expected
instrument". Dead-man switch: probe silent 24h → alert. An answer that degrades is an
incident, and every incident ends in a changed test, contract, monitor or runbook — never in
a narrative doc.

---

## 4. The contract every lane obeys — each rule was paid for

**4.1 Measure BOTH payload shapes, always.** `legal_unified` holds two generations of the
same law: modern (top-level `document_id`, `chunk_key`, `section`) and legacy
(`{metadata, text}`, no `chunk_key`). MEASURED: `UU_6_2011` had 258 healthy modern points
AND 261 legacy points of which 118 were damaged — a probe filtering only `document_id`
reported "0 damaged". Query `document_id` **and** `metadata.document_id`, every time. On a
flat collection a Qdrant filter ADDS `metadata.X` next to `X`, so both indexes must exist;
an unindexed key does not return "0 results", it returns **HTTP 400**.

**4.2 "Not in the KB" is a measurement.** Search by identity (`type_abbrev`/`number`/`year`),
by title text, and by a distinctive verbatim phrase. Three misses, then it is missing. A
document can be present under a WRONG identity — this corpus holds a 2024 tax circular filed
as a 2002 law — so absence under the right name is not absence.

**4.3 The label is never the thing.** A filename is not an identity (every Indonesian
ministry restarts its numbering each year) — extract identity from the document's own title
block. `peraturan.go.id` answers **HTTP 200 with a 74KB HTML error page** for a missing
document: judge a download by its first four bytes (`%PDF`), never by its status code. A
NotebookLM audit detects duplicate TITLES, not duplicate CONTENT.

**4.4 Identity before content.** The identity guard (`_assert_identity_unclaimed`, #4869)
refuses to write onto a `document_id` held by a different source filename. It is right and
must not be disarmed. To replace an edition with a fuller one: prove containment FIRST (same
article numbers, same openings), retire the old, then write. Downloading under the SAME
basename as the stored original avoids the false positive entirely.

**4.5 A document goes in whole or not at all.** #4896 makes a partially-read scan raise
instead of storing an amputated law. Do not reach for `allow_partial=True`. A scan that will
not read is an inventory row, not a workaround.

**4.6 Never delete without a containment proof.** Prove the text survives elsewhere fragment
by fragment and print the ratio. MEASURED precedent: 42/42 and 261/261 before the two
deletions of 2026-08-25. One uncovered fragment means do not delete — report instead.

**4.7 The embedding model is frozen.** `text-embedding-3-small`, 1536 dims. Changing it
invalidates the whole index; any proposal is a separate mandate with a re-indexing plan.

**4.8 Drive is read through the DELEGATED identity** (`ServiceAccountDriveService`, which
calls `with_subject`). A bare service-account client lists **0 files** and 404s on files that
same credential uploaded minutes earlier — a blind probe reports an empty archive rather than
an inaccessible one. Archive `BALI ZERO/PERATURAN` = `1VswtJMuDWN8BIK9Jahmf19RteikLXlhO`.

**4.9 A test nobody names does not run.** MEASURED 2026-08-25: a new top-level directory was
globbed by no workflow, so ten contract invariants ran nowhere and the defect they existed to
catch shipped. Count the COLLECTION (0 tests = exit 0); `importorskip` inside a gate is
green-on-empty; green from one cwd is not green.

**4.10 Generator ≠ grader.** Whoever gathered or ingested a topic never verifies it.

---

## 5. Lanes — 7 defined, at most 4 open at once

Integration branch `feature/kb-current`, local-first: cut from fresh `origin/main`, pushed to
origin nightly as backup (**no status PR**), each lane a worktree merging into it, **only the
orchestrator merges there**, morning rebase on main, refuters review the day's integrated
diff **every evening**, and the landing on `main` is a short train of pre-approved PRs.

⚠️ **Do NOT arm `gh pr merge --auto` on PRs into the integration branch.** It has no required
contexts, so the same gesture that is correct into `main` means "merge on green" — and green
on an integration branch certifies nothing this mandate cares about. MEASURED on the GARUDA
line, 2026-08-25: a 15-file customer-facing PR merged before the orchestrator read a line of
it. The evening pass IS the gate; if an evening pass is skipped, the next day's train does
not go out.

| Lane  | Topic                  | Scope                                                                                | Builder         | Refuter (other family) |
| ----- | ---------------------- | ------------------------------------------------------------------------------------ | --------------- | ---------------------- |
| **A** | Immigration & visa     | UU 6/2011 + amendments, Permenkumham / Permen Imipas, stay-permit types, circulars   | Sonnet 5        | Kimi K3                |
| **B** | Company & KBLI         | UU 40/2007, PT/PMA formation, BKPM, OSS, KBLI 2020/2025, capital rules               | Sonnet 5        | Sol                    |
| **C** | Tax                    | UU KUP / PPh / PPN, PMK, e-Faktur & Coretax, expatriate-relevant treaties            | Terra           | DeepSeek (TP1)         |
| **D** | Property & land        | UU 5/1960, Hak Pakai / HGB / leasehold, PP 18/2021, zoning, Bali Perda               | Sonnet 5        | Gemini 3.1 Pro         |
| **E** | Employment & HR        | UU 13/2003 as amended by Cipta Kerja, Permenaker, RPTKA/IMTA, BPJS                   | Kimi-for-coding | Sol                    |
| **F** | Compliance & reporting | LKPM, statutory deadlines, annual filings, sanctions                                 | Sonnet 5        | Kimi K3                |
| **P** | **Parser capability**  | the two damage classes no topic lane can fix alone (§6) — platform work, not a topic | Sol             | Kimi K3                |

Each topic lane owns its own repair: **a topic cannot be declared current while its own
documents answer with their commentary.** There is no separate repair squad.

Queueing: WIP ≤2 PRs per lane; a lane blocked over 2h gets split or re-scoped by the
orchestrator, not pushed harder.

---

## 6. The damage already measured — re-verify, do not re-derive

MEASURED across all 84,361 points: **31 documents, 2,042 fragments.** Detection signal: a
point whose `section` is not `penjelasan` and whose text contains `Cukup jelas`.

- **Repairable now** (marked elucidation boundary + source obtainable). Two worked examples to
  copy: `UU_40_2007` (202 points / 109 poisoned → 379 clean, 195 articles + 184 commentary,
  161 distinct articles, Pasal 32 restored to the Rp 50.000.000 rule) and `UU_6_2011` (413
  clean; the local PDF had NO elucidation at all — the Drive edition proved a superset, 145
  identical articles + 154 commentary articles, and the legacy copy was retired after a
  261/261 containment proof). Remaining candidates measured MARKED: `UU_11_2020`, `UU_3_2022`,
  `UU_23_2002` — the last two also carry an identity problem (§4.2).
- **Lane P, class 1 — unmarked boundary.** `UU_17_2008` (Pelayaran) has **471** occurrences of
  "Cukup jelas" and **zero** occurrences of the word "PENJELASAN" in the extracted text;
  `UU_66_2024` likewise. No word-based rule can find that boundary — it needs a structural
  signal (e.g. the run of `Pasal N` entries whose entire body is a note), with its own guilt
  AND innocence tests.
- **Lane P, class 2 — annexed instruments.** `UU_6_2023` is a ~5,300-character conversion act
  with the entire Cipta Kerja (1.33M characters) attached and two separate elucidations. The
  indexer has no concept of an annexed instrument. 726 damaged fragments wait on it.
- **Sources gone.** 20 documents were ingested from `/tmp/legal_uploads/` (deleted) or from
  `/Users/antonellosiano/Desktop/...` (the laptop decommissioned 2026-05-05). `apps/kb/data/**`
  holds **0 PDFs** and git has no history of them. The Drive archive recovers 9 by exact
  filename ⇒ **11 of 31 repairable today, 1,375 fragments of 2,042.** The rest is §4.2 work:
  re-acquire officially, then ingest.

---

## 7. Owner switchboard — nothing blocks on these; build, collect signatures at the end

| #   | Decision                                                | Prepared proposal                                                           | Owner gesture                    |
| --- | ------------------------------------------------------- | --------------------------------------------------------------------------- | -------------------------------- |
| 1   | The ~20 questions per topic the KB must never get wrong | orchestrator drafts from real client traffic; lanes build against the draft | read, sign                       |
| 2   | The official PDF of UU 25/2007 (Investment Law)         | measured absent from the corpus and from every machine                      | supply or approve re-acquisition |
| 3   | `legal_unified_2026` (§1)                               | measurement + one recommendation                                            | approve                          |
| 4   | Team confirmation per topic (G6)                        | five real questions, asked by the person who answers that domain            | ask, confirm                     |
| 5   | Superseded instruments: remove or mark?                 | recommendation with the retrieval consequence of each                       | pick                             |

An amended article still answering with its old text is worse than silence — decision 5 is
not cosmetic.

---

## 8. Definition of done, and stopping

**A topic is current when** every instrument in force is present under its correct identity
and whole; every superseded one is removed or marked; the inventory lists both sets with
dates; and **the probe suite for that topic is green against production** and has stayed
green for 48h under the scheduled job. Point four is the only one that proves the other
three.

**Stopping**: rule 8 — three reds for the same cause on the same surface and the item
SUSPENDS with one ledger line and the lane moves on. A lane that finds a defect outside its
topic writes an inventory row and does not chase it. Business decisions belong to Zero.
