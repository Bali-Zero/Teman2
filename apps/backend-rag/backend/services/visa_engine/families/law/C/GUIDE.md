# Guide — Family C (single-entry visit visas)

Law cards: `apps/backend-rag/backend/services/visa_engine/families/law/C/<CODE>.json` (verbatim, imigrasi.go.id/wna/daftar-visa-indonesia/<CODE>, sha256-pinned, 2026-10-17).
Every question below exists because a Law card condition needs it. Max 3 questions.

```
Q1  What will you do in Indonesia?
    ├── Holiday / visit family & friends ............ C1
    ├── Business meetings ........................... C2
    ├── Explore an investment ....................... C12
    ├── Social / volunteer activity ................. C6
    ├── Perform music
    │     └── Q1b  Performer or crew? ............... C7A | C7B
    ├── Perform other arts / talent ................. C7C
    ├── Sport event
    │     └── Q1b  Athlete or official? ............. C8A | C8B
    ├── Speak at an event (speaker / lecturer) ...... C10
    ├── Skill test with an Indonesian employer ...... C18
    └── Internship
          └── Q1b  For your studies or for skills? .. C22A | C22B

Q1c (gates, asked only for the codes named)
    C1, C2  Do you hold a national passport, or another travel document
            (stateless, emergency passport, other non-national document)?
              national_passport → no sponsor question
              other_document    → Q2 (sponsor)
    C8A, C8B  Is the sport activity non-commercial (government invitation,
              international championship, international sports organisation event)?
              no → not covered by this visa (verdict NOT_COVERED)

Q2  Does an Indonesian organisation sponsor you?      (every code except C1/C2 with a national passport)
    no  → this visa is not possible without a sponsor
    (answers are option keys "yes" / "no"; any other value asks again)

Q3  How many days do you need?                        (a positive whole number; anything else asks again)
    ≤ stay on the Law card ............ OK
    ≤ stay + extensions ............... OK, with extension
    more .............................. not possible on this visa
```

Leaf table (from the Law cards):

| Code            | Sponsor                                                             | Stay | Extension       |
| --------------- | ------------------------------------------------------------------- | ---- | --------------- |
| C1              | no (exceptions: stateless, non-national passport, listed countries) | 60   | up to 180       |
| C2              | no (same exceptions)                                                | 60   | up to 180       |
| C6              | yes                                                                 | 60   | up to 180       |
| C7A / C7B / C7C | yes                                                                 | 30   | no              |
| C8A / C8B       | yes                                                                 | 60   | up to 180       |
| C10             | yes                                                                 | 60   | up to 180       |
| C12             | yes                                                                 | 180  | up to 12 months |
| C18             | yes                                                                 | 90   | no              |
| C22A / C22B     | yes                                                                 | 180  | 12 months total |

Paths: 13 visas, each with the gate and sponsor branches that apply and 3 stay outcomes. Every path becomes one test; the extra gates (travel document, non-commercial sport) have their own tests.
Documents (passport validity, 3-month bank statement, photo, letters) are a checklist on the result screen, not questions.

TO VERIFY before shipping:

- C1/C2 "listed countries" that need a sponsor: the list is behind a link that was not captured, so a national passport of a listed country is not detected yet.
- C12 price: requested from Adit (2026-10-17).

Decided:

- C18 = 90 days, not extendable (Zero ruling 2026-10-17). Supporting: imigrasi.go.id/C18 "Masa tinggal ... maksimal 90 hari" and fee line "Masa tinggal 90 hari (tidak bisa diperpanjang)"; Bali Zero price list 2026 "90 days". Conflicting, kept for the record: same page "Jenis visa" paragraph says 60 days extendable/convertible; our Kepmen extraction (`research/legal/2026-05-26-kepmen-visa-taxonomy/02-cross-ref-pnbp.md:141`) lists 60. Re-check if Imigrasi corrects the page.
