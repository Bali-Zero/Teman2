# FACTS-FOR-THE-TREE — the ten seq-21 qualification facts

> **Audience: W-VO-Q** (the window that adds the interview questions in
> `apps/mouth/.../_lib/tree.ts`, `flow.ts` and `fact-mapper.ts`).
> **Pack:** `rulepack-prod-021.source.json`, payload
> `c21a2aaaa33b939284a8d2ddaedef1f0c22859b3b3a87c9042b48c92814467cf`,
> `valid_period.from = 2026-09-15T00:00:00Z`. Unsigned, unactivated.
> **Registry:** `backend/services/visa_engine/enums.py::FactPath` is now 60 paths
> (56 applicant + 4 derived); every fact below is a `BOOLEAN`, `PiiClass.PERSONAL`,
> and carries a rollout default of `UNKNOWN / NOT_ASKED` in `models.py`, so an
> interview that does not yet ask them sends nothing and breaks nothing.

## Why these ten exist, in one paragraph

Nine of the 38 products in the catalogue had **zero** `ELIGIBILITY` rules, which
makes them structurally unrecommendable: `evaluate_product`'s `declared_coverage`
is the union of `covered_purposes` over a product's ELIGIBILITY rules, so a
product with none claims nothing and is feasible for nobody. What each of them
had instead was a `REQUIRE_REVIEW` rule gated on `intent.requested_product_code`
— a fact `fact-mapper.ts` hard-codes to `UNKNOWN(NOT_ASKED)`, so the gate was
dormant and the product invisible. seq-21 retires those nine review rules and
gives each product one SUPPORT rule keyed on **one qualifying fact**. Until the
tree asks for that fact, the rule is `on_unknown: NEEDS_INPUT` — the engine asks
rather than denies. **These ten questions are what turn nine dormant products
into nine reachable answers.**

## The table

`unlocks` = the product code that becomes a candidate when the fact is `true`
and the rule's other premises hold. `rule` = the seq-21 rule id that reads it.

| #   | fact id                                     | question (EN)                                                                                                                                                     | question (ID)                                                                                                                                                                        | unlocks                                            | rule                               |
| --- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- | ---------------------------------- |
| 1   | `sponsor.government_invitation`             | Do you hold a written invitation from an Indonesian central-government body, issued to you for your special expertise?                                            | Apakah Anda memiliki undangan tertulis dari instansi pemerintah pusat Indonesia yang diberikan kepada Anda sebagai tenaga ahli?                                                      | **E33A**                                           | `el.e33a.government-invitation`    |
| 2   | `sponsor.government_collaboration`          | Do you have a confirmed collaboration commitment with an Indonesian government body or institution, based on your special expertise?                              | Apakah Anda memiliki komitmen kolaborasi yang terkonfirmasi dengan instansi atau lembaga pemerintah Indonesia, berdasarkan keahlian khusus Anda?                                     | **E33B**                                           | `el.e33b.government-collaboration` |
| 3   | `sponsor.world_figure_invitation`           | Has an Indonesian government body invited you as a world figure — a person of international standing?                                                             | Apakah instansi pemerintah Indonesia mengundang Anda sebagai tokoh dunia — seseorang dengan reputasi internasional?                                                                  | **E33C**                                           | `el.e33c.world-figure-invitation`  |
| 4   | `sponsor.diplomatic_household`              | Is your employer a foreign diplomat posted in Indonesia, and is the role in that diplomat's household?                                                            | Apakah pemberi kerja Anda adalah diplomat asing yang bertugas di Indonesia, dan posisinya berada di rumah tangga diplomat tersebut?                                                  | **E23U**                                           | `el.e23u.diplomatic-household`     |
| 5   | `sponsor.trade_office`                      | Is your sponsor a foreign trade or economic representative office in Indonesia?                                                                                   | Apakah penjamin Anda adalah kantor perwakilan dagang atau ekonomi asing di Indonesia?                                                                                                | **E23V**                                           | `el.e23v.trade-office`             |
| 6   | `investment.establishes_indonesian_company` | Will you establish a company in Indonesia as part of this investment?                                                                                             | Apakah Anda akan mendirikan perusahaan di Indonesia sebagai bagian dari investasi ini?                                                                                               | **E28B**                                           | `el.e28b.company-establishment`    |
| 7   | `investment.capital_market_only`            | Is your investment held only in capital-market instruments, without establishing a company?                                                                       | Apakah investasi Anda hanya ditempatkan pada instrumen pasar modal, tanpa mendirikan perusahaan?                                                                                     | **E28C**                                           | `el.e28c.capital-market`           |
| 8   | `investment.foreign_branch_or_subsidiary`   | Are you establishing a branch or a subsidiary of a company that already exists outside Indonesia?                                                                 | Apakah Anda mendirikan kantor cabang atau anak perusahaan dari perusahaan yang sudah ada di luar Indonesia?                                                                          | **E28D**                                           | `el.e28d.branch-or-subsidiary`     |
| 9   | `investment.ikn_subsidiary`                 | Will the company you are establishing be a subsidiary located in the new capital, IKN (Ibu Kota Nusantara)?                                                       | Apakah perusahaan yang Anda dirikan merupakan anak perusahaan yang berlokasi di Ibu Kota Nusantara (IKN)?                                                                            | **E28F**                                           | `el.e28f.ikn-subsidiary`           |
| 10  | `investment.meets_published_threshold`      | Does your investment meet every published financial minimum for the route you chose — the capital amount, and the annual turnover where that route publishes one? | Apakah investasi Anda memenuhi seluruh batas minimum keuangan yang dipublikasikan untuk jalur yang Anda pilih — jumlah modal, dan omzet tahunan jika jalur tersebut mensyaratkannya? | **E28B · E28C · E28D · E28F** (conjoined with 6–9) | all four `el.e28*` rules           |

## The premises each rule ALSO carries — do not drop them from the branch

A rule only fires when every conjunct is TRUE, and the premises below are the
ones that make it DEFINITELY FALSE for an applicant the product does not
concern. They are all facts the tree already asks; the branch that asks a new
question must keep asking them.

| rule                               | purpose premise                | sponsor / route premise             | qualifying fact |
| ---------------------------------- | ------------------------------ | ----------------------------------- | --------------- |
| `el.e23u.diplomatic-household`     | `intent.purposes ⊇ EMPLOYMENT` | `sponsor.type = INDIVIDUAL`         | 4               |
| `el.e23v.trade-office`             | `intent.purposes ⊇ EMPLOYMENT` | `sponsor.type = GOVERNMENT`         | 5               |
| `el.e33a.government-invitation`    | `intent.purposes ⊇ EMPLOYMENT` | `sponsor.type = GOVERNMENT`         | 1               |
| `el.e33b.government-collaboration` | `intent.purposes ⊇ EMPLOYMENT` | `sponsor.type ∈ {GOVERNMENT, NONE}` | 2               |
| `el.e33c.world-figure-invitation`  | `intent.purposes ⊇ INVESTMENT` | `sponsor.type ∈ {GOVERNMENT, NONE}` | 3               |
| `el.e28b.company-establishment`    | `intent.purposes ⊇ INVESTMENT` | fact 6 = true                       | 10              |
| `el.e28c.capital-market`           | `intent.purposes ⊇ INVESTMENT` | fact 7 = true                       | 10              |
| `el.e28d.branch-or-subsidiary`     | `intent.purposes ⊇ INVESTMENT` | fact 8 = true                       | 10              |
| `el.e28f.ikn-subsidiary`           | `intent.purposes ⊇ INVESTMENT` | fact 9 = true                       | 10              |

## Where to ask them, and the trap to avoid

- Facts **1–3** belong on the branch that already asks `sponsor_category` and
  gets `GOVERNMENT` or `NONE`; facts **4–5** on the same question's `INDIVIDUAL`
  and `GOVERNMENT` answers. Asking all five unconditionally would ask a tourist
  about a diplomatic household.
- Facts **6–10** belong on the `invest` branch, after the existing
  investment-vehicle question. Facts 6–9 are independent booleans on purpose —
  an applicant establishing a company AND holding capital-market instruments is
  real, and a single-valued "route" question would force a false choice. Fact 10
  is asked once, after whichever routes were selected.
- **`fact-mapper.ts` must map a "no" to `KNOWN false`, not to `unknownFact`.** A
  false answer makes the rule DEFINITELY FALSE and the product simply not
  offered; an `unknownFact` leaves the rule UNKNOWN and the engine will ask the
  question again, which on these `on_unknown: NEEDS_INPUT` rules is a loop.
- **The rules never appear in `intent.requested_product_code`.** Nothing in
  seq-21 reads that fact for these nine products (the nine review rules that did
  are retired), so the tree must not start setting it on their account.

## What proves this file rather than asserts it

`backend/tests/services/visa_engine/test_seq21_pack.py`:

- `TestTheNineProductsAreReachable::test_each_target_product_is_supported_on_its_gold_fixture`
  builds one fact bag per product from a REAL corpus walk plus the row above,
  and asserts the engine names the product.
- `...::test_an_unknown_qualification_asks_instead_of_supporting` withdraws the
  qualifying fact from each of those nine bags and asserts the product
  disappears and the outcome becomes `NEEDS_INPUT` — the exact state the
  interview must cure by asking the question.
- `TestSponsorTypeAloneIsNotEvidence` strips the qualifying conjunct out of the
  rules and shows 16 corpus walks then gain products on no evidence: that is the
  measurement of what these ten facts are load-bearing for.

## Honest limits

- The 84-walk corpus does **not** carry these facts, so the census is unchanged
  (67 SUPPORTED / 15 NO_SUPPORTED_PATH / 2 NEEDS_INPUT) and the distinct-product
  count stays 17. Adding the questions is what moves it; the nine gold fixtures
  above are the proof that the pack side is ready.
- Each SUPPORT rule declares only the ONE purpose it gates on
  (`covered_purposes`), not the product's full catalogue coverage. An applicant
  declaring `{EMPLOYMENT, TOURISM}` therefore still cannot reach E33A, because
  `COVER_ALL_DECLARED_PURPOSES` needs both covered. Widening that is a pack
  decision for a later sequence, not an interview one.
