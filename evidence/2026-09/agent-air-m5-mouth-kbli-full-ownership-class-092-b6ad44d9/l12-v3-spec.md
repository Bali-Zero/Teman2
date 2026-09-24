# L12 v3 — spec written at suspension (2026-09-25)

P7 (branch `agent/air-m5/mouth/kbli-full-ownership-class-0925`) is SUSPENDED under
`docs/rules/operations.md` §8. The 50134 data cure passed every data check in both fresh
gates (scope, truth, copies, census, tests, other rules). The surface that went red three times is
L12's grammar:

| Round | Candidate                                                     | Verdict         | What broke inside the written promise                                                                                                                                                                                                                                                             |
| ----- | ------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | v1, a token window                                            | Codex FIX-FIRST | a negation elsewhere in the sentence cleared the claim; "owned by Indonesians" was flagged                                                                                                                                                                                                        |
| 2     | v2, a permission predicate governing an object (`5d73779a7e`) | fresh Opus FAIL | negated "granted", the month "May", bare "Indonesians", "hold all of", hyphenated "wholly-owned"                                                                                                                                                                                                  |
| 3     | v2 plus its cure (`720f125daf`)                               | fresh Opus FAIL | 8 guilt sentences missed, 8 innocent sentences flagged. The causes: "can never / no longer", "During/Last/Every May", a subject scoped to the whole sentence, the foreign-owner word list, a negated Indonesian subject, adverbs inside "is allowed to", "its shares", and the "No." abbreviation |

Every round cured the sentences it was shown, and the next gate found new ones. The design itself
is the problem: it tries to judge English permission semantics (negation scope, subjects, months,
abbreviations) with regex, and each new innocence route opens a new under-match. The corpus for
both directions is in `l12-gate2-probes.py` (16 MISS on `720f125daf`).

## v3: recall-first on the object, innocence by a reviewed pin, no grammar

1. **Detector.** On a record whose numeric `pma_max_asing` is below 100 (int or float, never bool),
   or whose `pma_status` is not `TERBUKA`, split every `intel_2026` string leaf into sentences. A
   sentence is a HIT when it contains a full-ownership OBJECT. The object vocabulary is the only
   regex left: v2's objects, plus the spellings the gates found ("its/their shares", hyphenated
   forms, "hold all of"). There is no predicate, negation, subject, question or month logic.
2. **Innocence = a reviewed pin.** `data/kbli-filiera/l12-reviewed-sentences.json` holds a list of
   `{code, path, sentence_sha256, verdict: "innocent", reason, reviewed_by, reviewed_at}`. The
   sha256 is taken over the sentence after whitespace is normalised. A hit whose
   (code, path, sha256) is pinned passes. Any other hit is a blocking finding. A pin whose sentence
   no longer exists is a finding too (a stale pin), so the file cannot rot.
3. **Seed.** On the cured canonical there are exactly 6 hits on 6 codes today, all correct
   negations ("…80% ceiling…, not full ownership", "cannot hold the entire company", "cannot be
   wholly foreign-owned", …). They become the 6 seed pins, each with its reason. The 50134 original
   sentence is never pinned. It is the guilt fixture, pinned by sha256 to the cure spec's
   `old_sha256`.
4. **Cost of an over-match.** New prose that mentions full ownership on a capped code turns CI
   red until a reviewer pins the sentence or cures it. That is the intended behaviour for a claim
   with legal weight. A new sentence costs one pin. A false negative in a grammar costs a live
   overclaim.

## Acceptance

- Object recall is 100%: every GUILT and INNO sentence in `l12-gate2-probes.py`, the C4B list
  included, is a HIT at maxa=49 when it is not pinned. Nothing in that corpus is judged "innocent
  by grammar". Measured at suspension: the v2 object vocabulary already recalls 77 of the 79
  sentences. The 2 it misses are the "hold all of / 100% of its shares" forms.
- The 6 seed pins clear exactly the 6 current hits. The pre-cure canonical has exactly one unpinned
  hit, `50134.intel_2026.whatYouNeed`. The cured canonical has 0.
- A stale pin is a finding (unit test: change one pinned sentence and assert the finding).
- 50142 (TERBUKA/100) is never read: "a foreign-owned PT PMA can hold 100%" stays outside scope.
- L10 and every other rule stay byte-identical (the v2 check 7 method).
- The data cure commits (`cda53ca234`, `a386cd430a` data part) are reused unchanged.

## Re-open in one pass

Branch from a fresh `origin/main`. Cherry-pick the data cure (`cda53ca234`) and the
registry/batch-A re-stamp from `a386cd430a`. Replace the v2 L12 block with v3, as specified
above. Write the 6 pins. Run one fresh Opus gate against this file. Do not run a fourth grammar
round.
