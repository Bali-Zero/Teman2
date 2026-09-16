# P2b — what counts as quoting a moratorium total (v1)

Consumer: `scripts/kbli_bench/score_p2b.py`, `moratorium_scope_check`, criterion
`quotes_a_moratorium_total`. Tests: `scripts/tests/test_score_p2b.py`, the `test_spec_*` block.

This document exists because the code asked for it. The comment above `COUNTED_NOUN` on
`origin/main` ended: _"The spec this needs is 'what counts as quoting a total', written down — not
another alternation."_ Seven council rounds had produced seven matching defects on that one
criterion. This is the eighth finding, and it is the first one that is not about the alternation.

## 1. Why seven rounds did not settle it

Every round patched the **noun**: widened to activities/sectors, withdrawn, then bounded with `\b`
on both sides. The cause was the **relation**. The criterion only asked that the numeral and the
noun sit within 40 characters of the same clause:

```python
re.search(rf"\b(518|48)\b[^.;]{{0,40}}{COUNTED_NOUN}", cl)
```

Forty characters of proximity is not a count. Measured on `origin/main` (the merged #6428,
`054c780b8b`), these all **convicted** and none quotes a code total:

| clause                                   | what it means                         |
| ---------------------------------------- | ------------------------------------- |
| `biaya rp 48 juta untuk kode baru`       | 48 million rupiah for a new code      |
| `pasal 48 mengatur kode etik perusahaan` | article 48 governs the code of ethics |
| `518 halaman berisi daftar kode`         | 518 pages contain the list of codes   |

And round 6's right-hand `\b` opened the opposite error: `48 kodenya terkena moratorium` convicted
before that round and escapes after it, because `-nya` is a word character.

The direction matters. `decidable_pass` is `all(required.values()) and not totals`, so a false
positive fails a correct answer and a false negative **inflates the benchmark score**. Retiring the
criterion is not neutral either: it would make `not totals` always true, inflating the score
systematically.

**Diagnosis.** A two-valued guard on a three-valued question must be wrong somewhere. Some clauses
quote a total unambiguously, some unambiguously do not, and some cannot be settled without reading
for meaning. Seven rounds searched for the boundary between the first two while the third class
absorbed the errors.

## 2. The rule

### 2.1 Entity

Numeral in `{518, 48}`; noun whose stem is in `{kbli, kode, code, codes}`.

The noun is an entity, not a substring. **Left boundary mandatory**: excludes `barcodes`, and in
Indonesian excludes the prefixed verbs `mengkode`, `dikode`, `berkode`, which are not the noun. On
the right, a **closed set of Indonesian enclitics** precedes the boundary:

```
(?:nya|ku|mu|kah|lah)?
```

`-nya` is the commonest suffix in the language; `kodenya` is the noun. A bare right-hand boundary
loses it. Plural reduplication (`kode-kode`) needs nothing extra: the hyphen is already a boundary.

### 2.2 Relation

The numeral must be the **count** of the noun, not a number that happens to be near it. Two
adjacent forms only:

- **numeral then noun**, optionally through a counter: `518 kbli`, `48 kode`, `48 kodenya`,
  `48 buah kode`, `48 jenis kode`
- **noun then numeral**, and here an explicit quantity connective is **required**, because
  `kode 48` reads as naming a code rather than counting one: `kode sebanyak 518`,
  `kode berjumlah 48`, `codes totalling 518`

The 40-character window is abolished. Only whitespace, hyphens or a listed connective may sit
between the two.

### 2.3 Outcome — ternary

| outcome     | condition                                                 | effect on `decidable_pass` |
| ----------- | --------------------------------------------------------- | -------------------------- |
| convicted   | the adjacent form of 2.2 matches                          | **False**, unchanged       |
| undecidable | numeral and noun coexist in the clause but not adjacently | **nothing**                |
| clear       | they never meet in a clause                               | nothing                    |

The third outcome is not new machinery. `moratorium_scope_check` already defers permanence and
universality to the judge, with a stated reason, after three regex defects each. Quoting a total is
the third member of the same family. The criterion is stated to the judge verbatim in
`CLASS_RULE_EXPECTATIONS["bali_moratorium_scope"]`, so the deferral has a consumer rather than
being a place where a criterion is quietly dropped.

### 2.4 The undecidable net is deliberately WIDER than the entity

Added 2026-09-14 after the gate on the PR that introduced this document measured a hole in it.

The first implementation built the coexistence probe from the same `COUNTED_NOUN` as the entity, so
the net inherited the entity's boundary. A noun form the entity does not recognise could not reach
`undecidable`; it fell through to `clear`. Measured, all four of these are real quoted totals and
all four were `clear`:

| clause                                  | why the entity misses it                                   |
| --------------------------------------- | ---------------------------------------------------------- |
| `ada 48 kode2 terkena moratorium`       | `kode2` is standard Indonesian shorthand for `kode-kode`   |
| `ada 518 kbli2 yang diblokir`           | same shorthand                                             |
| `ada 48 kodepun terkena moratorium`     | the `-pun` clitic, joined spelling, outside the closed set |
| `kodenyalah 48 yang terkena moratorium` | stacked `-nya` + `-lah`                                    |

`clear` means a **missed total**, and §1 of this document says a false negative inflates the
benchmark score. So the net's noun is `\b(?:kbli|kode|codes?)\w*` — stem plus any word-character
tail — while the entity keeps its closed enclitic set. The asymmetry is the rule, not an oversight:

- an unrecognised noun form is **handed to the judge**, never convicted by the scorer and never
  silently cleared;
- the entity is not widened, because widening what CONVICTS is a spec change by criterion 6 below;
- one set used twice is not a set guarded by a wider one. That was the defect.

The left boundary still binds both: `barcodes`, `mengkode`, `dikode` reach neither outcome, because
the noun never starts there.

## 3. Fixtures, measured

All seventeen run against both versions on 2026-09-14. `main` is `origin/main` at the merge of
#6428; `spec` is this document implemented.

| clause                                            | main          | spec            |
| ------------------------------------------------- | ------------- | --------------- |
| `Ada 48 kode terkena moratorium.`                 | convicted     | convicted       |
| `Ada 48 kodenya terkena moratorium.`              | **clear**     | **convicted**   |
| `518 KBLI diblokir.`                              | convicted     | convicted       |
| `518 codes are blocked.`                          | convicted     | convicted       |
| `There are 48 codes affected.`                    | convicted     | convicted       |
| `Kode sebanyak 518.`                              | convicted     | convicted       |
| `48 buah kode.`                                   | convicted     | convicted       |
| `48 kode-kode.`                                   | convicted     | convicted       |
| `Biaya Rp 48 juta untuk kode baru.`               | **convicted** | **undecidable** |
| `Pasal 48 mengatur kode etik perusahaan.`         | **convicted** | **undecidable** |
| `518 halaman berisi daftar kode.`                 | **convicted** | **undecidable** |
| `48 dari kode yang berstatus itu.`                | **convicted** | **undecidable** |
| `There are 48 new barcodes affected.`             | clear         | clear           |
| `Mengkode 48 baris.`                              | clear         | clear           |
| `Dikode 518 kali.`                                | clear         | clear           |
| `Foreign ownership is allowed in 48% of sectors.` | clear         | clear           |
| `See page 518 for affected activities.`           | clear         | clear           |
| `Ada 48 kode2 terkena moratorium.`                | clear         | **undecidable** |
| `Ada 518 kbli2 yang diblokir.`                    | clear         | **undecidable** |
| `Ada 48 kodepun terkena moratorium.`              | clear         | **undecidable** |
| `Kodenyalah 48 yang terkena moratorium.`          | clear         | **undecidable** |

Five clauses change, twelve do not. One false negative closes, four false positives become
undecidable, and nothing that was already right moves. The last two are the false positives round
5's widening produced; they are kept as fixtures so a future widening cannot reintroduce them
unnoticed.

`48 dari kode yang berstatus itu` — _48 of the codes with that status_ — is very probably a total,
and the _probably_ is the point. A judge reads it; a regex does not.

## 4. Out of scope, and still declared

Untouched, and this spec does not pretend otherwise:

- **A count does not name a set.** `l4_bali.blocked` is true on 518 records conflating five causes;
  48 are the codes whose status names the moratorium. Neither answers "which KBLI". The existing
  `declared_gap` stands.
- **`reduceRow` caps two list fields at six items**, so a fully served row is still not fully shown.
- **`per_skala` needs row identity, not row count**, which is a contract on both sides.

## 5. Acceptance criteria

1. The seventeen fixtures of section 3 are tests, each naming which of the three outcomes it must
   reach.
2. Each false positive has a test that is red on `origin/main` and green with the spec. The
   behaviour table in section 3 is the proof, not the test names.
3. `48 kodenya` has a guilt test that goes red if the bare right-hand boundary returns.
4. A test proves an undecidable clause does not lower `decidable_pass`, and another proves a real
   quoted total still does.
5. A test proves the criterion reaches the judge, because a deferral with no consumer is a claim.
6. No eighth alternation: widening the noun set or the enclitic set of the ENTITY means editing this
   document first.
7. The undecidable net stays strictly wider than the entity. A test must go red if the net is made
   to reuse `COUNTED_NOUN` again: reverting that one line is the mutation, and the four §2.4 clauses
   are what it must break.
