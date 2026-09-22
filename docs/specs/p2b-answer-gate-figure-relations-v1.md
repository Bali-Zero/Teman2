# P2b — when a numeral in an answer is a CLAIM about a code's cap (v1)

Consumer: `Sources/KBLIAnswerGate.swift` in the KBLI Navigator app repo (M5,
`/Users/balizero/Desktop/logo/kbli-navigator-app`, **no remote**), the clause-level `%` binding
block of `check(...)`. Tests: that repo's gate suite. This document is the monorepo's half of the
cure; the code half belongs to the lane that owns the app, and this file is what it executes.

This document exists because the cure for this class already shipped and the class is still
there. Commit `3e4ca59` — _"fix(gate): cure the four over-match classes killing verified-true
answers (P2b floors ii+iii)"_ — put four carve-outs in the gate, α β γ δ, each with the
benchmark question that motivated it named in a comment. Measured on 2026-09-22, the gate file
is **byte-identical on all seven branches** of the app repo (sha256 `dddadb5bb3ae…`), including
`k2/gamma` at `69933ab`, which is the build the last benchmark ran. And that run still shows
Q13 runs 1 and 3, and Q22 run 3, killed by `percentCodeMismatch` — the same class, after its
own cure. Superscar #2 as it applies to cures rather than crons: shipped is not fixed.

Below, every clause is quoted verbatim from
`scripts/kbli_bench/results/2026-09-14-k2-gamma/p2b_answers.jsonl` and every rejection reason
is the one the run recorded.

## 1. What the shipped carve-outs do, and where each one stops

|     | shape it admits                                                       | where it stops                                               |
| --- | --------------------------------------------------------------------- | ------------------------------------------------------------ |
| α   | a code cited only to state its ABSENCE (`statesAbsence`)              | codes only — it has no twin for figures                      |
| β   | a clause with no code binds to the last verifiable code before it     | binding is the fix; the figure is still read as an assertion |
| γ   | N codes, one figure, all caps equal                                   | unchanged for N == 1                                         |
| δ   | a figure that echoes the question's own, **beside** a substantive one | withdraws the moment the echo stands alone in its clause     |

δ withdraws on purpose. Its comment says why: _"if every figure is an echo, they all stay in
play"_, so that `49222 mengizinkan 51%` — an assertion dressed as an echo — cannot walk through.
That reasoning is right about the danger and wrong about the discriminator. It separates the two
cases by COUNTING figures in the clause, and what separates them is the RELATION the clause puts
the figure in.

## 2. The two residual shapes

### 2.1 δ′ — the echoed figure alone in its clause

> `Navigator hanya memuat lima KBLI ini, jadi tidak dapat menyimpulkan bahwa semua sektor boleh
untuk kepemilikan asing 51%.` — Q13 run 1

> `Jadi kepemilikan 51% dapat tercakup oleh catatan ini.` — Q13 run 3

Both clauses cite no code, so β binds them to the last verifiable code named before them
(`87303` and `63900`, cap 100 each). Both carry exactly one figure, `51`, which is the
question's own — `Klien asing mau pegang 51% saham PT`. δ discounts an echo only when a
substantive figure remains in the same clause; here none does, so `51` is verified against a
cap of 100 and the answer is refused as `percentCodeMismatch`.

The answer was correct. It is the answer the corpus asks for: it denies the universal and
declines to generalise from five records.

### 2.2 ε — the negated figure

> `Posisi produk untuk Bali adalah OPEN_IN_BALI; ini hanya menyatakan posisi Bali menurut
adjudikasi produk, bukan izin otomatis untuk 100% asing.` — Q22 run 3,
> rejected `percentCodeMismatch(25200, claimed 100, actual 49)`

The clause says the opposite of 100%. The gate reads the numeral and binds it to 25200, whose
cap is 49. Run 1 of the same question survives only because it phrased the same denial without
a numeral (`bukan bahwa kepemilikan asing otomatis terbuka penuh`) — so today the gate is
punishing an answer for being specific about what it is denying.

α already settled this principle for CODES: a negated mention is not a claim, which is why
`68200 tidak ada dalam katalog` passes. The figure path never got the twin. That is W132 in the
product's own gate: the documented cure that never reaches the other half of the same idea.

## 3. The rule

Both shapes are decided per FIGURE, never per clause — a clause may carry one figure that is a
claim and one that is not, and any rule that judges the clause as a whole gets one of them wrong.

### 3.1 Cap-predicate (the entity, not a spelling)

A figure is **predicated** when a cap-predicate lemma governs it in the same clause:

```
batas | dibatasi | maksimal | paling banyak | hingga | sampai | mengizinkan | memperbolehkan
cap   | limit    | maximum  | at most       | up to  | allows | permits
```

Left boundary mandatory. Indonesian prefixed and suffixed forms of `batas` (`dibatasi`,
`batasnya`, `membatasi`) are the same entity and are in; `pembatasan wilayah` is not about
ownership but is admitted — the rule errs toward treating a figure as a claim, which is the
fail-closed direction.

### 3.2 δ′ — echo

A figure equal to one of `questionFigures` does not consume the clause's figure budget when
**either**:

- another figure in the same clause survives verification (this is δ, unchanged); **or**
- it is the only figure in the clause **and no cap-predicate governs it**.

If a cap-predicate governs the lone echo, it stays in play and is verified normally. That is
what keeps `49222 mengizinkan 51%` and `batas untuk 49222 adalah 51%` refused.

### 3.3 ε — negation

A figure inside the scope of a negation lemma is not a claim:

```
negation: bukan | tidak | belum | tanpa | not | never | no
scope:    from the negation token to the end of the clause OR to the first contrastive
          conjunction, whichever comes first
contrastive: melainkan | tetapi | tapi | namun | but | rather | instead
```

The contrastive boundary is the whole safety of this rule. `KBLI 25200 tidak dibatasi 49%,
melainkan 100%` negates 49 and ASSERTS 100; a scope running to the end of the clause would
discount both and let a fabricated cap through the one door the benchmark must never open.

If every figure in a clause is discounted by 3.2 or 3.3, the clause carries no percentage claim
and is skipped — exactly as a clause with no figure at all is skipped today.

## 4. Guilt and innocence

Guilt = the pre-cure gate refuses a correct answer, and after the cure it passes. Innocence =
an invented cap is STILL refused. Both halves are required; the corpus below is written to be
transcribed into the app's gate suite one case per row. Context for all rows: package
`{49222, 63900, 74999, 77400, 87303}` all at cap 100, plus `25200` at cap 49;
`questionFigures = {51}`.

| #   | clause                                                                               | today  | required   | why                                                              |
| --- | ------------------------------------------------------------------------------------ | ------ | ---------- | ---------------------------------------------------------------- |
| G1  | `jadi tidak dapat menyimpulkan bahwa semua sektor boleh untuk kepemilikan asing 51%` | reject | **pass**   | δ′ — lone echo, no cap-predicate (Q13 r1, verbatim)              |
| G2  | `Jadi kepemilikan 51% dapat tercakup oleh catatan ini.`                              | reject | **pass**   | δ′ (Q13 r3, verbatim)                                            |
| G3  | `bukan izin otomatis untuk 100% asing`                                               | reject | **pass**   | ε — negated figure (Q22 r3, verbatim)                            |
| G4  | `ini tidak berarti 100% terbuka`                                                     | reject | **pass**   | ε, English-free variant                                          |
| I1  | `49222 mengizinkan 51%`                                                              | reject | **reject** | δ′ does not apply: a cap-predicate governs the echo              |
| I2  | `batas untuk 49222 adalah 51%`                                                       | reject | **reject** | idem, `batas`                                                    |
| I3  | `KBLI 25200 tidak dibatasi 49%, melainkan 100%`                                      | reject | **reject** | ε scope closes at `melainkan`; 100 is asserted and wrong         |
| I4  | `batas kepemilikan asing 25200 adalah 100%`                                          | reject | **reject** | plain fabrication, untouched by either rule                      |
| I5  | `tidak ada batas; KBLI 49222 hingga 60%`                                             | reject | **reject** | ε does not reach past `;` — a new clause, affirmative            |
| N1  | `Untuk KBLI 74999, 51% berada di bawah batas nasional 100%`                          | pass   | **pass**   | δ unchanged — two figures, 100 verifies (Q13 r1, verbatim)       |
| N2  | `kepemilikan dapat melebihi 49% dengan persetujuan Menteri Pertahanan`               | pass   | **pass**   | β unchanged — code-less clause, carried 25200, 49 == 49 (Q22 r1) |
| N3  | `68200 tidak ada dalam katalog KBLI 2025`                                            | pass   | **pass**   | α unchanged                                                      |

Rows N1-N3 are regression anchors: the three carve-outs that already work must keep working,
and a cure measured only on its own four rows is how δ shipped without covering δ′.

## 5. What this does not decide

- **Whether an echoed figure is TRUE of the code.** `51% rientra nel limite` is admitted as
  not-a-claim, not as a verified statement. The judge grades it; the gate only stops asserting
  that the gate verified it. Floor (i) is unaffected — no path here admits a figure that a
  record contradicts, because a discounted figure is never bound to a record at all.
- **Spelled-out numerals.** `seratus persen` remains `unverifiablePercentClaim`, unchanged.
- **Negation scope across a sentence boundary.** Out of scope by construction: the gate's unit
  is the clause, and I5 pins that this is deliberate rather than an oversight.
- **Whether Q13 and Q22 then grade `correct`.** They may not — Q13's judge reason on the
  passing run names a separate framing defect. Curing the gate removes a wrongful ABSTENTION;
  accuracy is a different floor and this spec does not claim it.
