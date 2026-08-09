---
date: 2026-08-09
domain: operations
topic: kbli-25refused-rewrite-pack-part1
client_case: none — internal `kbli_documents` data-quality follow-up, Mandate 10, part 1 of 3 (agriculture/food/tech/finance/creative), requested by Zero via team-lead
discovered_by: kbli-docs-flip subagent, Mandate 10 (team-lead directive, on Zero's request)
sources:
  - "Postgres `kbli_documents` (prod, via `mcp__postgres-nuzantara__query`, read-only role) — live `content`/`judul`/`metadata` for the 8 codes in this file, queried this session; byte-level check via `position(E'\\n' in content)` confirmed the stored text contains ZERO real newline characters for every code in the licensing-absent-25 population (see §0 below — a new finding, not part of the mandate's ask)"
  - "data/source_documents/KBLI_2025_FINAL_CLEAN.json — canonical 2025 dataset; full `per_skala` (risk tier / authority / timeline) array and top-level `pma_*` fields read for all 8 codes"
  - "apps/backend-rag/backend/scripts/kbli_documents_cure.py — the selector this mandate re-derives (`licensing_absent_codes()`) and the auto-rebuild gate it deliberately did NOT clear (`rebuild_reason()`, `CONTRADICTED_LICENSING_CLAIM_RE`) for these rows"
  - "scripts/kbli_filiera/kbli_surface_conformance.py — SNAPSHOT_SQL query re-derived directly against prod to re-measure the population (see §0)"
adversarial_review: codex
---

# KBLI 25-refused rewrite pack — part 1 of 3 (agriculture / food / tech / finance / creative)

Mandate 10: for each code the `kbli_documents_cure.py --all-licensing-absent` selector found but refused
to auto-rebuild (hand-written prose, not a machine-template and not matching the tool's literal
contradiction regex), produce a card: current prose verbatim, the canonical licensing rows the channel
doesn't serve, a contradiction verdict, and a proposed rewrite. **Proposals only — nothing in this file
was applied to `kbli_documents`.**

## §0 — Population re-measured, not assumed (2026-08-09)

Re-ran the exact selector logic live against prod (SQL from `kbli_surface_conformance.py::SNAPSHOT_SQL`,
executed via the read-only Postgres MCP role, cross-joined against the local canonical dataset — same
computation `licensing_absent_codes()` performs): **still exactly 25 codes**, and the list is byte-identical
to the 2026-08-02 report referenced in the mandate:
`03231 03232 03233 56400 62900 65111 65121 74192 85102 85510 85520 85571 85572 85573 85574 85575 85579
85693 85694 90200 90310 91122 96230 96300 96400`. No delta to declare.

**Side finding, out of scope for this mandate but too material to omit**: querying live `content` for these
25 rows, `position(E'\n' in content) = 0` for every one of them — the stored text has **zero real newline
characters**. What WhatsApp/webchat serve today for these codes is a single run-on line where "WHAT IT
MEANS:" and "BALI CONTEXT:" read as glued-on labels with no paragraph breaks. A broader sweep
(`length(content) > 100 AND position(E'\n' in content) = 0`) found **312 rows** across the whole table with
this same defect — far larger than the 25 in scope here. This is a genuine, previously-undocumented
client-facing rendering defect (distinct from the licensing-absence question this mandate investigates) and
is flagged to team-lead separately; it is not fixed in this pack, and the rewrite drafts below are written as
clean prose from scratch, so they do not inherit it.

## Method per code

1. Quote the live `content` verbatim (it has no real newlines — quoted as stored).
2. Summarize canonical's `per_skala` risk/authority/timeline rows, deduplicated by scale-tier (the raw JSON
   repeats near-identical rows across `scope_uraian` sub-clauses of the same official activity).
3. Verdict: **CONTRADICE** (the prose asserts something canonical's rows disprove), **COMPATIBILE** (prose
   and canonical agree or the prose's claim is independently corroborated by a canonical field), or
   **SILENTE** (prose says nothing canonical could contradict — it just never surfaces licensing at all).
4. A rewrite draft: keeps every hand-written disambiguation/warning, adds the canonical risk/authority/
   timeline picture, English/factual, no marketing language.

---

## 03231 — Pembudidayaan Ikan Bersirip (Selain Ikan Hias) dan Biota Air Payau Lainnya yang Tidak Dilindungi

**Prosa attuale (verbatim, no real newlines in the stored row):**
> KBLI 03231: BRACKISH WATER FINFISH FARMING (PEMBUDIDAYAAN IKAN BERSIRIP AIR PAYAU)nnWHAT IT MEANS:nFarming
> fish like Milkfish (Bandeng) and Snapper in brackish water systems. Includes hatchery and nursery
> operations.nnBALI CONTEXT:nNorth Bali (Buleleng) is the brackish water capital. Milkfish (Bandeng) are a
> staple for the local market and vital for live bait in the tuna industry.

**Canonical licensing (20 raw rows, deduplicated):** Mikro/Kecil → **Menengah Rendah**, Otomatis. Menengah/
Besar → **Menengah Tinggi**, 3 hari. Authority spans Bupati/Walikota, Gubernur, and Menteri/Kepala Badan
depending on scale/scope. `pma_status = TERBUKA`.

**Verdetto: SILENTE.** The prose never mentions risk tier, timeline, or foreign-ownership status — it says
nothing canonical could contradict, but a client reading it learns nothing about licensing at all.

**Bozza:**
> **What it means**: Brackish-water finfish farming (milkfish, snapper) and related non-protected species —
> land preparation, hatchery/nursery operations, grow-out, and harvest.
>
> **Licensing**: Micro/Small scale — Menengah Rendah (medium-low) risk, NIB issued automatically. Medium/
> Large scale — Menengah Tinggi (medium-high) risk, NIB + Sertifikat Standar within 3 working days. Authority
> is shared across Bupati/Walikota, Gubernur, and central ministry depending on scale and operating area.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: North Bali (Buleleng) is the province's brackish-water aquaculture center. Milkfish
> (bandeng) supply both the local table market and the live-bait trade for Bali's tuna fishing fleet.

---

## 03232 — Pembudidayaan Ikan Hias Air Payau yang Tidak Dilindungi

**Prosa attuale (verbatim):**
> KBLI 03232: PEMBUDIDAYAAN IKAN HIAS AIR PAYAU YANG TIDAK DILINDUNGInnWHAT IT MEANS:nBreeding non-protected
> freshwater ornamental fish. This includes raising, breeding, and harvesting fish for sale or further
> breeding in various water bodies.nnBALI CONTEXT:n

**Canonical licensing (8 raw rows, deduplicated):** Mikro/Kecil → **Menengah Rendah**, Otomatis. Menengah/
Besar → **Menengah Tinggi**, 3 hari. `pma_status = TERBUKA`.

**Data-quality flag found reading the official `uraian` itself (added after adversarial review — codex,
confirmed independently against `KBLI_2025_FINAL_CLEAN.json`):** canonical's OWN description is internally
inconsistent on water type. The title and the second uraian sentence both say *air payau* (brackish): *"...
menggunakan air payau sebagai media budi daya"*. But the FIRST uraian sentence says *"...pembenihan, dan
pemanenan ikan hias **air tawar** yang tidak dilindungi"* — freshwater. This is a defect in canonical
itself, not something this pack can resolve; the rewrite below follows the title + the media-of-cultivation
sentence (brackish), consistent with 03231/03233's sibling framing, but this conflict should be raised with
whoever maintains the canonical dataset rather than silently resolved here.

**Verdetto: SILENTE on licensing**, plus a data-quality note: the "BALI CONTEXT" section is **empty** — the
label is present with nothing after it, a gap the rewrite should actually fill rather than reproduce.

**Bozza:**
> **What it means**: Breeding, raising, and harvesting non-protected ornamental fish in brackish water —
> for retail sale or further breeding stock, not for food. (Canonical's own `uraian` calls this species
> "air tawar"/freshwater in one sentence and "air payau"/brackish in the next — flagged above; this draft
> follows the brackish reading, matching the code's title and its sibling codes 03231/03233.)
>
> **Licensing**: Micro/Small — Menengah Rendah risk, automatic NIB. Medium/Large — Menengah Tinggi risk,
> NIB + Sertifikat Standar within 3 working days.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: [genuinely no source material exists in the current row — this is an honest gap to fill
> with real research, not invented copy; flagged here rather than silently carried forward.]

---

## 03233 — Pembudidayaan Tumbuhan Air Payau yang Tidak Dilindungi

**Prosa attuale (verbatim):**
> KBLI 03233: PEMBUDIDAYAAN TUMBUHAN AIR PAYAU YANG TIDAK DILINDUNGInnWHAT IT MEANS:nGrowing non-protected
> freshwater aquatic plants such as Gracilaria spp. This includes cultivation for carbon sequestration and
> selling carbon credits from these activities.nnBALI CONTEXT:n

**Canonical licensing (4 raw rows):** Mikro/Kecil → **Menengah Rendah**, Otomatis. Menengah/Besar →
**Menengah Tinggi**, 3 hari. `pma_status = TERBUKA`.

**Verdetto revised after adversarial review (codex, independently confirmed): not plain SILENTE — the
stored prose contains a factual error, separate from licensing.** Unlike 03232, canonical's `uraian` for
03233 is internally CONSISTENT: it says *"air payau"* (brackish) throughout, with no "air tawar" mention
anywhere. Yet the stored `content` calls this "**freshwater** aquatic plants" — flatly wrong against an
unambiguous source. The original rewrite draft happened to already say "brackish-water" (a lucky accidental
correction, not a deliberate one — the original draft never flagged that it was fixing an error). Recorded
here explicitly rather than silently: this is a genuine content defect in the live row, not just an
absent-licensing gap.

**Bozza:**
> **What it means**: Cultivating non-protected brackish-water aquatic plants (e.g. Gracilaria seaweed) —
> including cultivation specifically for carbon sequestration and the sale of resulting carbon credits.
>
> **Licensing**: Micro/Small — Menengah Rendah risk, automatic NIB. Medium/Large — Menengah Tinggi risk,
> NIB + Sertifikat Standar within 3 working days.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: [no source material in the current row — genuine gap, not filled with invented copy.]

---

## 56400 — Aktivitas Jasa Intermediasi Penyediaan Makanan dan Minuman

**Prosa attuale (verbatim):**
> KBLI 56400: AKTIVITAS JASA INTERMEDIASI PENYEDIAAN MAKANAN DANnnWHAT IT MEANS:nFood trucks and mobile
> street food — preparing and serving food from motorized or non-motorized vehicles, carts, or mobile
> stalls. This includes food trucks, mobile kitchens, street food carts, and pop-up food stalls that can
> relocate. If your food operation moves on wheels or is designed to be mobile, this is your code.nnBALI
> CONTEXT:nFood trucks are having a moment in Bali...

**Canonical `uraian` (official BPS text, read in full)**: *"Kelompok ini mencakup aktivitas penyediaan jasa
intermediasi makanan dan minuman yang mempertemukan klien dengan jasa penyedia makanan dan minuman
berdasarkan balas jasa atau komisi, dengan penyedia jasa perantara TIDAK menyediakan makanan dan minuman
tersebut... jasa reservasi restoran... TIDAK MENCAKUP pengoperasian platform daring yang mengizinkan orang
untuk memesan layanan pengiriman makanan (lihat 5330)."* — this is a **commission-based intermediation
platform that connects clients with food/beverage providers** (e.g. restaurant reservation services) and
explicitly EXCLUDES both (a) actually preparing/serving food, and (b) online food-delivery-ordering
platforms (that is code 53300 instead).

**Canonical licensing (3 raw rows — no Mikro tier exists for this code in canonical, and all 3 rows are
scoped to `"Selain Penyelenggara Perdagangan Melalui Sistem Elektronik (PPMSE) dan Penyelenggara Sarana
Perantara (PSP)"`, i.e. NON-electronic-platform intermediaries only — confirmed via `scope_uraian` after
adversarial review flagged the earlier draft for glossing over this):** Kecil/Menengah → **Menengah
Rendah**, Otomatis. Besar → **Menengah Tinggi**, 7 hari. `pma_status = TERBUKA`.

**Verdetto: CONTRADICE — not merely a licensing gap, a topic mismatch.** The stored prose describes an
entirely different business (operating a mobile food truck) than what code 56400 actually covers (a
commission-based matchmaking service between clients and F&B providers, e.g. table-reservation platforms).
A food-truck operator using this code would be filing under the wrong KBLI entirely. This is the most
severe finding in this file's group and should be prioritized.

**Bozza (genuine rewrite, not a patch):**
> **What it means**: Food and beverage intermediation services — platforms or agencies that connect clients
> with food/beverage providers on a commission or fee basis, WITHOUT preparing or serving the food
> themselves. Restaurant reservation services are the named example. This explicitly EXCLUDES online
> platforms that let users order food delivery (that is code 53300) and excludes actually running a food
> business (a food truck, a restaurant, a mobile kitchen — those are separate codes entirely).
>
> **Licensing**: these tiers apply only to intermediaries NOT registered as a PPMSE/PSP (Penyelenggara
> Perdagangan Melalui Sistem Elektronik / Penyelenggara Sarana Perantara — Indonesia's electronic-trading
> system operator status). Small/Medium scale — Menengah Rendah risk, automatic NIB. Large scale — Menengah
> Tinggi risk, NIB + Sertifikat Standar within 7 working days. No Micro-scale entry exists in canonical for
> this code. If the intermediation runs THROUGH a registered PPMSE/PSP electronic system, canonical has no
> corresponding row under this code at all — that variant likely needs separate confirmation against
> Indonesia's e-commerce/PMSE licensing framework rather than this table.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: [the removed food-truck content should be re-homed to whichever code actually covers
> mobile food service — that research is outside this mandate's scope, but leaving it here misdirects
> anyone reading this code.]

---

## 62900 — Aktivitas Jasa Teknologi Informasi dan Komputer Lainnya

**Prosa attuale (verbatim):**
> KBLI 62900: AKTIVITAS JASA TEKNOLOGI INFORMASI DAN KOMPUTER LAINNYAnnWHAT IT MEANS:nThe catch-all code for
> IT services that don't fit anywhere else...nnBALI CONTEXT:nUse this code with caution. If you're doing app
> development (62192), AI (62194), cybersecurity (62201), or IT consulting (62209), use those specific
> codes...

**Canonical licensing (4 raw rows):** Mikro/Kecil/Menengah → **Rendah**, Otomatis. Besar → **Menengah
Rendah**, Otomatis. `pma_status = TERBUKA`.

**Verdetto: SILENTE.** The prose's own warning against misusing this catch-all is good, accurate content —
it names real sibling codes and correctly frames this as a residual bucket. It just never states the actual
risk tier.

**Bozza:**
> **What it means**: The residual/catch-all code for IT and computer services not covered by a more specific
> 62xxx code.
>
> **Licensing**: Micro/Small/Medium — Rendah (low) risk, automatic NIB. Large — Menengah Rendah risk,
> automatic NIB.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: Use this code with caution — app development is 62192, AI is 62194, cybersecurity is
> 62201, IT consulting is 62209. Some Bali business consultants recommend adding 62900 as a SECONDARY code
> alongside a specific primary code for flexibility, but it should never be your only code.

---

## 65111 — Asuransi Jiwa Konvensional / 65121 — Asuransi Umum Konvensional

Grouped: same regulator, same PMA cap, same licensing shape — only the product line differs.

**Prosa attuale, 65111 (verbatim):**
> KBLI 65111: ASURANSI JIWA KONVENSIONALnnWHAT IT MEANS:nConventional life insurance activities...nnBALI
> CONTEXT:n...Foreign life insurers can own up to 80% — but must meet minimum local market capitalization...

**Prosa attuale, 65121 (verbatim):**
> KBLI 65121: ASURANSI UMUM KONVENSIONALnnWHAT IT MEANS:nConventional general (non-life) insurance
> activities...nnBALI CONTEXT:n...OJK requires minimum equity of Rp 250 billion for general insurers...

**Canonical licensing (both codes, 4 raw rows each):** ALL scales → **Tinggi** (high) risk, timeline
*"Sesuai ketentuan OJK/BI"* (per OJK/BI regulation, i.e. outside the standard OSS clock).
`pma_status = TERBATAS`, `pma_max_asing = 80`, `pma_cap_verified = True`, official basis: *PP 14/2018 Pasal
5(1) jo. PP 3/2020 Pasal I angka 1* — foreign ownership capped at 80% of paid-up capital, listed insurers
(perseroan terbuka) exempt, pre-2018 holdings above 80% grandfathered.

**Verdetto: COMPATIBILE — and independently verified, not just uncontradicted.** The prose's "80%" claim
matches canonical's own `pma_max_asing` exactly, and canonical marks it `pma_cap_verified: True` with a
named legal basis. This is well-sourced hand-written content; the rewrite below only adds the missing risk
tier and the exact regulatory citation.

**Bozza (65111):**
> **What it means**: Conventional life insurance — term, whole life, endowment, and unit-linked products
> covering death, disability, or survival to a specified age.
>
> **Licensing**: All scales — Tinggi (high) risk. Timeline and process follow OJK/BI regulation directly,
> outside the standard OSS risk-based clock.
>
> **PMA**: Restricted — foreign ownership capped at 80% of paid-up capital (PP 14/2018 Pasal 5(1) jo. PP
> 3/2020 Pasal I angka 1). Listed insurers (perseroan terbuka) are exempt from the cap; holdings above 80%
> from before 2018 are grandfathered without further increase. **The 80% cap is not the only constraint**:
> the operator must also separately meet OJK's minimum local capital/equity requirement (see below) —
> clearing the ownership cap does not by itself clear the capital-adequacy bar.
>
> **Bali context**: Life insurance penetration in Indonesia remains under 3% of GDP. Post-Jiwasraya/AJB
> Bumiputera, OJK has tightened capital requirements (minimum equity Rp 500 billion, rising to Rp 1 trillion
> by 2028 under POJK 23/2023). Bali's expat community drives demand for international health and life
> products.
>
> *(Fix after adversarial review: the first draft of this rewrite silently dropped the original stored
> prose's specific claim that foreign insurers "must meet minimum local market capitalization" — folding it
> into a generic OJK-equity citation elsewhere. Both claims are hand-authored content already present in the
> live row; restored above rather than left merged away.)*

**Bozza (65121):** same Licensing/PMA blocks as above, with:
> **What it means**: Conventional non-life insurance — property, liability, motor vehicle, non-life health,
> travel, cargo, and other non-life products.
>
> **Bali context**: Property and vehicle insurance are Bali's highest-volume general-insurance lines — fire/
> flood/earthquake cover matters near Mount Agung and Batur. Travel insurance is required for many visa
> applications and is largely sold through tour operators and airlines. OJK requires minimum equity of Rp
> 250 billion for general insurers (rising to Rp 500 billion by 2028).

---

## 74192 — Aktivitas Desain Grafis/Komunikasi Visual

**Prosa attuale (verbatim):**
> KBLI 74192: AKTIVITAS DESAIN GRAFIS/KOMUNIKASI VISUALnnWHAT IT MEANS:nGraphic Design / Visual
> Communication...nnBALI CONTEXT:n...KBLI 74192 provides a clean, 100% PMA-open avenue to set up a legal
> entity...

**Canonical licensing (4 raw rows):** ALL scales → **Rendah**, Otomatis. `pma_status = TERBUKA`.

**Verdetto: COMPATIBILE.** The "100% PMA-open" claim matches canonical exactly; the prose is simply silent
on the risk tier itself.

**Bozza:**
> **What it means**: Graphic design and visual-communication services — brand identity, logos, packaging,
> infographics, UI/UX visual assets, signage, and typography. Excludes computer-based animation.
>
> **Licensing**: All scales — Rendah (low) risk, NIB issued automatically.
>
> **PMA**: Fully open — 100% foreign ownership allowed.
>
> **Bali context**: A clean, low-risk entry point for Bali's freelance/creative expat community — no
> physical studio required, a virtual office is sufficient. Historically confused with the more restricted
> Advertising code (73100); keep client contracts framed as "design deliverables", not "ad placements".

## Adversarial review

**Seat**: `codex` (`codex exec -m gpt-5.6-sol`, reasoning effort `high`, `--sandbox read-only`), run against
the first draft of all three parts of this pack together, independently re-querying the live table and the
canonical dataset rather than trusting this file's quotes, and instructed to check specifically for (a) any
rewrite that contradicts a canonical row, and (b) any rewrite that drops a hand-written warning/
disambiguation the original prose carried. Full transcript and per-code verdicts are recorded in Part 3 of
this pack (`2026-08-09-kbli-25refused-rewrite-pack-3-arts-personal-misc.md`), which the reviewer was run
against as the anchor file for the whole three-part pack — cross-reference there for the complete review
table covering all 25 codes, including the 8 in this file.
