---
date: 2026-08-19
domain: visa
client_case: none — engine doctrine work (E5 increment 4, seq-10 cure claims)
sources:
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31C (live fetch 2026-08-19T04:22:00Z)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C2 (live fetch 2026-08-19T04:21:51Z)
  - research/visa/doctrine-factory/e5/inc4-pack-edits/freshness-restamp-2026-08-19.md
  - research/visa/doctrine-factory/claims/e2b-batch3-claim-ledger.md (CL-C2-03, CL-E31C-01, CF-16)
discovered_by: agent.air-m5.backend-rag.visa-e5-seq10
adversarial_review: codex
---

# inc4 claim ledger — C2 / E31C cure batch (seq-10)

This is the "E31C/C2 doctrine batch" the CP3 decision package named as the seq-10
prerequisite for curing the two lint residuals. Method note, disclosed up front: these
claims are grounded by **QW-5-method live fetches of the OFFICIAL_PORTAL pages the rules
already cite** (verbatim transcriptions in
`e5/inc4-pack-edits/freshness-restamp-2026-08-19.md`), not by NB-2 queries — the same
grounding route the seq-9 fold used for the E31E re-sourcing
(`inc3-pack-edits/e31e-source-edits.json`), chosen because the facts at issue are
requirement-list facts whose authoritative surface IS the portal page (`40523028` /
the C2 page), and the pack's own `source_refs` cite exactly those records. State
vocabulary per `source-hierarchy-draft.md` §3.2; compilable states are `VERIFIED` /
`VERIFIED-WITH-CAVEAT` only (`claim_ledger.py:61`).

---

**CL-E31C-02 — E31C requires official proof of the parents' legally registered
marriage.** The E31C page's Persyaratan khusus requires, verbatim: *"Bukti perkawinan
orang tua berupa: Bukti pelaporan atau pencatatan pada Perwakilan Republik Indonesia
atau instansi yang berwenang di bidang pencatatan sipil dan akta perkawinan yang telah
diterjemahkan dalam bahasa Indonesia oleh penerjemah tersumpah; atau Buku nikah atau
akta perkawinan yang dikeluarkan oleh kementerian atau lembaga berwenang (jika
perkawinan dilakukan di wilayah Indonesia)."* — official proof of the parents' legally
registered marriage, two routes: (a) registration/recording at an Indonesian
Representative Office or the civil-registration authority plus a sworn-translated
marriage certificate, or (b) an Indonesian-issued marriage book/certificate. A marriage
that is not legally registered cannot satisfy either route, so
`family.marriage_registered == true` is a necessary condition for E31C.

- Source: source_record `40523028-431b-5ae0-a937-277882f0f243`
  (`imigrasi.go.id.e31c.daftar-visa-indonesia`, OFFICIAL_PORTAL, re-verified live
  2026-08-19T04:22:00Z, CURRENT) + `e3572ad2-08a9-55bd-b818-353b3e9db715` (Kepmen
  M.IP-08.GR.01.01/2025 Klasifikasi Visa, framing corroborator — E31C's category is
  "child of legal mixed marriage", the marriage's legality being definitional).
- **State: VERIFIED.** Products: E31C. Provenance:
  `inc4-qw5-recheck-e31c` (2026-08-19, reader-2 fetch, raw-HTML cross-checked).
- Backs: `el.e31c-mixed-marriage-parents` (tightened `when`, seq-10) and
  `hf.e31c-marriage-not-registered` (`REQ_PARENTS_MARRIAGE_REGISTERED`, seq-10).
- Note: `CL-E31C-01` (identity, VERIFIED-WITH-CAVEAT) and `CL-E31BCDEF-01`
  (CONFLICTING, NB-2-source only) are about the product's *identity label*; this claim
  is about a *requirement* and does not depend on resolving that identity conflict —
  the requirement is read directly off the page the pack cites for this product.

---

**CL-E31C-03 — E31C's penjamin is the Indonesian-citizen parent.** The E31C page
requires a sponsor (*"Anda membutuhkan penjamin/sponsor untuk mengajukan visa ini"*)
and its checklist items 1 and 9 identify who that is, verbatim: *"Surat permohonan visa
dari ayah/ibu Warga Negara Indonesia"* (the visa application letter comes from the
Indonesian-citizen father/mother) and *"Kartu Keluarga (KK) ayah/ibu Warga Negara
Indonesia"* (the WNI parent's Family Card). The sponsoring parent is therefore the
Indonesian-citizen parent: `family.sponsor_nationalities ∩ {ID}` (with
`family.relation_to_sponsor == PARENT`, the field's applicant-side naming per
E31C.md §3.3).

- Source: same two records as CL-E31C-02 (portal live fetch + Kepmen framing).
- **State: VERIFIED-WITH-CAVEAT.** Products: E31C. Provenance: `inc4-qw5-recheck-e31c`.
- Caveat (Codex refuter finding 4 / Kimi finding 3, 2026-08-19): the quoted items
  prove a WNI parent must exist and supply the application letter and the Kartu
  Keluarga; that the formal *penjamin* must BE that parent is an inference (the page
  does not exclude a different penjamin). Typical-case reading, carried as a
  `caveats` entry in `inc4-rule-manifest.json` per the compiler's
  VERIFIED-WITH-CAVEAT contract.
- Backs: the `family.sponsor_nationalities` conjunct of the tightened
  `el.e31c-mixed-marriage-parents` (seq-10).
- Consistency: E31C's product metadata `sponsor_types: ["INDIVIDUAL"]` (a natural
  person as penjamin) agrees; E31A's live spouse rule uses the identical
  nationality-of-sponsor predicate for the same-family product.

---

**CL-E31C-04 — E31C's own product name states the mixed-nationality basis
directly: WNA-WNI (foreign parent x Indonesian parent).** The E31C listing on the
live portal titles the product itself *"E31C Visa Keluarga Anak Hasil Perkawinan Sah
WNA-WNI"* — child of a legally-registered WNA-WNI (foreign-citizen x
Indonesian-citizen) marriage. This is definitional at the product-identity level,
independent of which named individual signs as the formal penjamin (the open
question CL-E31C-03's caveat carries): the product does not exist for a child of two
co-national parents, of either citizenship. It corroborates, from an independent
textual location on the same page, the same underlying fact CL-E31C-03 grounds from
the checklist items — that the SET of parents must include at least one Indonesian
citizen.

- Source: same page as CL-E31C-02/03
  (`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31C`), product-title
  heading, verbatim: *"E31C Visa Keluarga Anak Hasil Perkawinan Sah WNA-WNI"*.
- **State: VERIFIED.** Products: E31C. Provenance: this session (2026-08-23),
  independent re-fetch via raw `curl` (not the earlier reader-2 fetch) — done
  specifically to check a finding relayed by the team-lead from a separate blind
  grader's own independent `curl` fetch of the same page; both fetches agree on
  this text.
- Backs: the `family.sponsor_nationalities` conjunct of
  `el.e31c-child-mixed-marriage-support` (seq-13) and the paired
  `hf.e31c-sponsor-not-indonesian` HARD_FILTER (seq-13) — an ADDITIONAL, independent
  grounding alongside CL-E31C-03, not a replacement (CL-E31C-03's caveat about
  penjamin identity remains open and is not resolved by the product title).

---

**CF-17 — CONFLICT (OPEN): C2 sponsor requirement, three-way.** The candidate claim
"C2's sponsor is corporate (`sponsor.type == EMPLOYER`)" — the claim the CP3 package
said seq-10 should attempt for `el.c2.corporate-sponsor-type` — cannot be authored:
the evidence is three-way contradictory.

1. **Live C2 portal page** (2026-08-19T04:21:51Z), Penjamin section verbatim: *"Anda
   tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini. Kecuali anda:
   Berstatus tanpa kewarganegaraan (stateless); atau Pemegang dokumen perjalanan bukan
   paspor kebangsaan; atau Warga negara dari negara tertentu yang ada di dalam daftar
   ini."* — NO sponsor by default; the exceptions are applicant-status-driven, never
   entity-type-driven. No corporate-sponsor language anywhere on the page; the
   relationship letter may come from *"instansi pemerintah atau lembaga swasta"*.
2. **`CL-C2-03`** (e2b-batch3, VERIFIED-WITH-CAVEAT, PROSE_ONLY): a penjamin is
   legally mandatory for C2 per Permenkumham 11/2024 Pasal 1(18), operationally an
   inviting Indonesian company.
3. **Product metadata** in the pack: C2 `sponsor_types: ["EMPLOYER"]` — a Bali Zero
   working classification, not evaluator-consumed (enums.py:498-509) and not itself a
   sourced claim.

- **State: CONFLICTING.** Products: C2. Provenance: `inc4-qw5-recheck-c2`.
- Consequence for seq-10 (recorded, executed): no compilable claim grounds a
  sponsor-type tightening → `el.c2.corporate-sponsor-type` is RETIRED (its deduped
  condition is canonical-JSON-identical to `el.c2.business`'s entire `when`, so
  retirement is behavior-preserving; see `cure-c2-e31c.json`). `el.c2.business`'s own
  `family.sponsor_confirmed` gate is KEPT — conservative direction (the engine asks
  for more, never grants on less) — and re-opening it is exactly this CF's future
  doctrine question, alongside CF-16 (onshore conversion).

---

## Adversarial review

Seat: **Codex (GPT-5.6-sol, cross-family)** — single shared round over the whole inc4
edit set (this ledger + `freshness-restamp-2026-08-19.md` +
`cure-c2-e31c.json`/`source-restamp-edits.json`), ordered to refute: quote fabrication,
claims broader than their quoted evidence, the VERIFIED states (should any be
VERIFIED-WITH-CAVEAT?), the CF-17 three-way framing, and the retirement's
behavior-preservation argument. Findings and dispositions recorded in
`e5/inc4-pack-edits/cure-c2-e31c.md` §Adversarial review.
