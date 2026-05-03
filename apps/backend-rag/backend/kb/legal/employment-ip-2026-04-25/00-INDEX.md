---
title: Employment & IP Defense — Indonesian PKWT Contracts (Master Index)
domain: company
subdomain: employment_law_ip_protection
notebook: NB-3 (Company & Licensing) — UUID 933509f9-1561-403d-bd44-4a7a67a36df2
collection: legal_unified_hybrid_hybrid
generated_at: 2026-04-25
generator: Exa Research Pro (exa-research-pro model, $1.56)
research_id: r_01kq2dfa6qm6z7j8atmqpcsate
language: ID + EN
freshness_policy: on_demand
priority: P0
sources_count: 49
jurisdiction: Indonesia
applicable_laws:
  - UU No. 30 Tahun 2000 (Rahasia Dagang)
  - UU No. 28 Tahun 2014 (Hak Cipta)
  - UU No. 11 Tahun 2008 jo. UU No. 1 Tahun 2024 (ITE)
  - UU No. 27 Tahun 2022 (Pelindungan Data Pribadi)
  - UU No. 13 Tahun 2003 jo. UU No. 6 Tahun 2023 (Ketenagakerjaan/Cipta Kerja)
  - KUH Perdata Pasal 1249, 1304
  - Putusan MA 3549 K/Pdt/2023 (non-competition)
---

# Employment & IP Defense — Master Index

Asset di knowledge base che raggruppa **research deep-dive sulla difesa della proprietà intellettuale di un PT indonesiano nei confronti di dipendenti WNI**, con clausole pronte all'uso (Pasal Bahasa Indonesia) e analisi giurisprudenziale.

Use case primario: drafting di **PKWT (Perjanjian Kerja Waktu Tertentu)** che proteggano codebase, AI prompts, RAG system, knowledge base, e customer data, con clausole defensible nei tribunali indonesiani (PHI Denpasar, Pengadilan Niaga Surabaya).

## Files in this set

1. **`01-rahasia-dagang-uu30-2000.md`** — Trade secret protection: i tre elementi UU 30/2000, durata, sanksi pidana art. 17, lista trade secrets per software company.

2. **`02-hak-cipta-uu28-2014-employment.md`** — Copyright assignment under UU 28/2014: art. 35 work-for-hire default, art. 36 pengalihan eksplisit, art. 57 hak moral non rinunciabile, fail-safe clauses.

3. **`03-non-compete-MA-3549-2023.md`** — Non-compete & non-solicit enforceability: Putusan MA 3549 K/Pdt/2023, durate 6-12 mesi, requisiti di proporzionalità, freelance allowance.

4. **`04-electronic-evidence-ite-monitoring.md`** — UU ITE Pasal 5 (admissibility git history, cloud logs), UU PDP 27/2022 monitoring compliance, forensic preservation.

5. **`05-pasal-templates-ready-bahasa-indonesia.md`** — Clausole Bahasa Indonesia pronte: definisi rahasia dagang, pengalihan hak cipta, kerahasiaan, non-compete, denda proporzionale, source code controls, return-and-destroy.

## Common drafting mistakes (dal research)

- ❌ Non-compete >12 mesi → batal di pengadilan
- ❌ Denda arbitrario (es. Rp 500jt) → ridotto da hakim per art. 1249 KUHPerdata
- ❌ Affidarsi solo a default Pasal 35 UU 28/2014 → ambiguità su out-of-hours code
- ❌ Generic "menjaga kerahasiaan" → non qualifica come rahasia dagang ex UU 30/2000
- ❌ No survival clause → kewajiban kerahasiaan post-termination contestabile
- ❌ Mixed forum / no carve-out IP → Pengadilan Niaga vs PHI confusione

## Enforcement playbook (post-breach)

1. Forensic IT preservation (image device, log, hash) — UU ITE Pasal 5
2. Ex-parte sita jaminan (RBg) — beni mobili contenenti rahasia dagang
3. Gugatan perdata (Pengadilan Niaga Surabaya) — wanprestasi + ganti rugi + injunctive relief
4. Lapor pidana Polda Bali:
   - UU ITE Pasal 30 (akses tanpa hak): max 8 anni + Rp 800jt
   - UU Rahasia Dagang Pasal 17 (misappropriation): max 2 anni + Rp 300jt
   - UU Hak Cipta Pasal 113-116 (commercial infringement): max 4 anni + Rp 1M

## Cross-references

- **PKWT Subhi v2** (case study di applicazione): `/research/hr/2026-04-25-contratto-subhi-probation-pkwt.md`
- **Source contratto Damar** (sample PT Bayu Bali Nol B2B): Drive `13WZhFEhTykDTzrssZdBxOiohnDb0DdWn`
- **NB-3 Company & Licensing** (sibling sources): `legal_labor_dispute`, `legal_ip_basics`, `riforma_lavoro_2025`
