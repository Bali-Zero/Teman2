# Step 1: Query Design — NB-2 Deep Research Pipeline

> Synthesis: Gemini + Codex GPT-5.4 + DeepSeek R1 (2026-03-28)
> Status: Brainstorm complete, ready for testing

---

## 1. Language Strategy

### Consensus: Dual-track asymmetric (3/3 agree)

| Language             | Weight | Target Sources                                                | Use For                                                                    |
| -------------------- | ------ | ------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Bahasa Indonesia** | 60-70% | .go.id, hukumonline, Kompas, Katadata                         | Regulations, circulars, official announcements                             |
| **English**          | 20-30% | Jakarta Globe, law firms (SSEK, Fragomen), BKPM EN, embassies | Analysis, comparison, international coverage                               |
| **Mixed bridge**     | 10-15% | Cross-taxonomy                                                | When term is ID but market searches EN: `RPTKA work permit Indonesia 2025` |

### Rules

- **Never** use long mixed-language queries in one string — degrades Google results
- **L1 monitoring**: always run ID+EN pair per topic
- **L2-L4 analytical**: prefer EN or mixed, they seek comparison/trends
- Formula: `ID first (find regulation) → EN confirm (find analysis)`

### Key Divergence

- Gemini: "Do NOT use mixed-language" — separate queries only
- Codex: 10-15% mixed bridge queries ARE useful for taxonomy bridging
- DeepSeek: L1 = 80% Bahasa, L2-L4 = 50/50
- **Resolution**: Use separate clean queries per language, with occasional bridge queries for taxonomy gaps

---

## 2. Query Anatomy — The Perfect Deep Research Query

### Structure (all 3 agree on 5 components)

```
[TOPIC ANCHOR] + [REGULATORY MARKER] + [TEMPORAL ANCHOR] + [SOURCE HINT] + [NOISE CONTROL]
```

| Component             | Good Examples                                                                 | Bad Examples                                    |
| --------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------- |
| **Topic anchor**      | `KITAS investor`, `RPTKA`, `B211A`, `KITAP`, `Permenkumham 22/2023`           | `Indonesia visa`, `work permit`, `stay in Bali` |
| **Regulatory marker** | `peraturan`, `persyaratan`, `surat edaran`, `resmi`, `official`, `regulation` | `how to`, `guide`, `tips`                       |
| **Temporal anchor**   | `2025-2026`, `setelah UU 1/2026`, `Permenkumham Nomor X perubahan terbaru`    | `last 7 days` (unreliable), `recent`            |
| **Source hint**       | `Dirjen Imigrasi`, `Kemnaker`, `hukumonline`, `JDIH Kemenkumham`              | (none)                                          |
| **Noise control**     | `bukan blog wisata`, `excluding tourist guides`, `berdasarkan sumber resmi`   | (none)                                          |

### Optimal Query Length

| AI       | L1          | L2-L4       | Note                            |
| -------- | ----------- | ----------- | ------------------------------- |
| Gemini   | 25-50 words | 25-50 words | Natural language research brief |
| Codex    | 5-9 tokens  | 7-12 tokens | Keyword-style, shorter          |
| DeepSeek | 5-8 terms   | 8-12 terms  | With operators                  |

**Key insight**: Gemini treats NLM Deep Research as a "research brief" (longer, natural language). Codex and DeepSeek treat it more like Google Search (shorter, keyword-dense). **We need to test both styles** to see which NLM handles better.

**Test plan**: Run the same topic as both styles, compare source quality.

---

## 3. Visa Type Coverage — 5 Clusters

### Cluster Definitions

| Cluster             | Visa Types                                                 | Volatility | Priority          |
| ------------------- | ---------------------------------------------------------- | ---------- | ----------------- |
| **A: Work Permits** | KITAS Investor, KITAS Kerja, RPTKA, TKA, DKPTKA            | High       | Core revenue      |
| **B: Stay Permits** | KITAP, ITAS sponsor, family reunification                  | Medium     | Long-term clients |
| **C: Visit Visas**  | B211A, VOA, e-VOA, visa-free                               | High       | Volume driver     |
| **D: Special**      | Second Home (D2J), Retirement (D31H), Digital Nomad (E33G) | Medium     | Growth segment    |
| **E: Compliance**   | Overstay, reporting, sponsor obligations, enforcement      | Always-on  | Risk management   |

### Rotation Schedule

**Gemini approach** (5-day cycle, 1 cluster/day):

```
Mon: A (Work)  |  Tue: B (Stay)  |  Wed: C (Visit)  |  Thu: D (Special)  |  Fri: E (Compliance)
```

4 researches/day (2 topics x 2 languages). 4-week rotation across L1→L2→L3→L4.

**Codex approach** (3-day rotation, more aggressive):

```
Day 1: A1 C1 D1 E1  |  Day 2: A2 B1 C2 E2  |  Day 3: A1 B2 D2 E1  |  Repeat
```

8 L1 queries/day across clusters.

**DeepSeek approach** (priority-weighted weekly):

```
Mon/Thu: A + E (regulatory focus)
Tue/Fri: B + C (volume updates)
Wed/Sat: D + cross-check
Sun: broad sweep
```

### Recommendation for testing

Start with **Gemini's conservative approach** (1 cluster/day, 4 researches). If NLM handles it well and quota allows, expand toward Codex's 3-day rotation.

---

## 4. Query Evolution — Feedback Mechanism

### All 3 agree: signal-driven narrowing with decay

```
DETECT → PROMOTE → NARROW → PRESERVE BASELINE → DECAY → REVERT
```

| Phase        | Trigger                                                          | Duration         | Action                                                       |
| ------------ | ---------------------------------------------------------------- | ---------------- | ------------------------------------------------------------ |
| **Detect**   | New regulation number OR same change in 2+ authoritative sources | Immediate        | Flag as hot topic                                            |
| **Promote**  | Confirmed hot topic                                              | 7-14 days        | Generate 2-4 targeted follow-up queries                      |
| **Narrow**   | Follow-up finds deeper detail                                    | During promotion | Replace scheduled L2 query (not add)                         |
| **Preserve** | Always                                                           | Always           | Never reduce baseline coverage >20-30%                       |
| **Decay**    | 7 days no new documents on topic                                 | After promotion  | Revert to standard rotation                                  |
| **Branch**   | Change impacts multiple subtypes                                 | During promotion | Split into sub-queries (e.g., KITAS investor vs KITAS kerja) |

### State tracking (Gemini proposal)

```json
{
  "cluster_a": {
    "active_followup": {
      "trigger": "Permenkumham 3/2026 ITAS Investor",
      "query_override": "Analisis lengkap Permenkumham Nomor 3 Tahun 2026...",
      "cycles_remaining": 2,
      "first_detected": "2026-03-28"
    },
    "last_l1_run": "2026-03-25",
    "last_l2_run": "2026-03-18"
  }
}
```

---

## 5. Anti-Noise Techniques

### Query-Level (all 3 agree)

| Technique                  | Example                                                                         | Effectiveness |
| -------------------------- | ------------------------------------------------------------------------------- | ------------- |
| **Official intent words**  | `resmi`, `peraturan`, `surat edaran`, `official`, `regulation`                  | High          |
| **Temporal anchoring**     | `2025-2026`, reference specific regulation number                               | High          |
| **Institutional names**    | `Direktorat Jenderal Imigrasi`, `Kementerian Ketenagakerjaan`                   | High          |
| **Anti-consumer framing**  | Use `persyaratan` not `cara membuat`; use `regulation` not `how to get`         | High          |
| **Explicit exclusion**     | `bukan blog wisata`, `excluding tourist guides and forums`                      | Medium        |
| **Document type triggers** | `pdf`, `surat edaran`, `siaran pers`, `press release`                           | Medium        |
| **Specificity as filter**  | DKPTKA exemption thresholds for PMA KBLI 62012 → travel blogs CAN'T answer this | Very high     |

### Pipeline-Level

| Technique                  | When        | Action                                                     |
| -------------------------- | ----------- | ---------------------------------------------------------- |
| **Domain denylist**        | Post-import | Maintain dynamic list of noisy domains found in prior runs |
| **Noise ratio monitoring** | Post-import | If >30% sources are low-quality, tighten query specificity |
| **Publication date check** | Post-import | Flag any source with date before 2024                      |

### Expected noise budget

- With all techniques: 15-20% noise in imported sources
- Acceptable: NLM synthesis engine weights authoritative sources higher
- Alert threshold: 30%+ noise → query adjustment needed

---

## 6. Production-Ready Query Templates (20 queries)

### L1 — Monitoring (8 queries, 2 per cluster A-D)

**A1 — Work Permits: RPTKA/TKA (Bahasa)**

> Peraturan terbaru tentang Rencana Penggunaan Tenaga Kerja Asing (RPTKA) dan izin kerja tenaga kerja asing (TKA) di Indonesia tahun 2025-2026. Termasuk perubahan Permenaker, kuota jabatan, Dana Kompensasi Penggunaan TKA (DKPTKA), dan persyaratan KITAS Kerja. Fokus pada peraturan resmi Kementerian Ketenagakerjaan dan Dirjen Imigrasi.

**A2 — Work Permits: KITAS Investor (English)**

> Current requirements for foreign investor KITAS (izin tinggal terbatas investor) in Indonesia 2025-2026, including PMA minimum capital thresholds, KBLI restrictions, DKPTKA exemptions for directors and commissioners, and renewal procedures. Based on official Kemenkumham regulations and BKPM guidelines, not travel blogs.

**B1 — Stay Permits: KITAP (Bahasa)**

> Persyaratan dan prosedur konversi ITAS ke KITAP (izin tinggal tetap) tahun 2025-2026, termasuk jalur perkawinan campuran, jalur investor 5 tahun, dan perubahan berdasarkan UU Nomor 1 Tahun 2026 tentang Imigrasi. Sumber resmi Ditjen Imigrasi atau analisis hukum keimigrasian.

**B2 — Stay Permits: Sponsor (English)**

> New reporting obligations for ITAS sponsors (penjamin) in Indonesia under 2025-2026 immigration regulations, including mandatory notifications, annual reporting (laporan keberadaan orang asing), and penalties for non-compliance. Focus on Permenkumham requirements and Direktorat Jenderal Imigrasi circulars.

**C1 — Visit Visas: B211A (Bahasa)**

> Peraturan terkini visa kunjungan B211A Indonesia 2025-2026: kategori bisnis, sosial budaya, dan medis. Termasuk biaya resmi, perpanjangan, single entry vs multiple entry, dan perubahan sejak berlakunya UU Imigrasi baru. Berdasarkan sumber Ditjen Imigrasi, bukan blog wisata atau forum ekspatriat.

**C2 — Visit Visas: VOA/e-VOA (English)**

> Indonesia Visa on Arrival (VOA) and electronic VOA (e-VOA) updates 2025-2026: eligible nationalities, fee changes, extension rules, airport and seaport availability, and processing through molina.imigrasi.go.id. Official government sources and verified news only, excluding tourist guides.

**D1 — Special: Second Home/Retirement (Bahasa)**

> Perkembangan visa Second Home (D2J) dan KITAS Pensiun (D31H) Indonesia 2025-2026: perubahan persyaratan deposit minimum, bukti pensiun, usia minimum, serta prosedur pengajuan melalui sistem online imigrasi. Berdasarkan Permenkumham terbaru dan kebijakan Ditjen Imigrasi.

**D2 — Special: Digital Nomad (English)**

> Indonesia digital nomad visa (E33G / remote worker visa) operational status 2025-2026: eligibility criteria, KBLI requirements, tax obligations for remote workers, application process, and comparison with neighboring countries' digital nomad programs. Based on BKPM and immigration directorate sources.

---

### L2 — Comparative (4 queries)

**L2-1 — ASEAN Work Permit Comparison (English)**

> Comparative analysis of foreign work permit systems in Indonesia, Thailand, Malaysia, and Vietnam 2025-2026: processing time, cost, employer sponsorship requirements, and digital processing adoption. Focus on policy research and government statistics, not relocation agency marketing.

**L2-2 — UU 1/2026 vs Previous Law (Bahasa)**

> Perbandingan detail antara UU Nomor 1 Tahun 2026 tentang Imigrasi dan UU Nomor 6 Tahun 2011: perubahan kategori visa, sanksi overstay, kewajiban sponsor, dan kewenangan penegakan hukum. Analisis hukum dari hukumonline, JDIH, atau firma hukum keimigrasian.

**L2-3 — Golden Visa Competitiveness (English)**

> Indonesia Golden Visa program competitiveness compared to Thailand Elite, Malaysia MM2H (2025 revision), and Philippines SRRV 2025-2026: investment thresholds, benefits, processing time, and uptake statistics. Policy analysis and government data sources only.

**L2-4 — KITAS Cost Benchmark (Bahasa)**

> Perbandingan biaya resmi dan biaya layanan agen untuk pengurusan KITAS di Indonesia 2025-2026: KITAS Kerja, KITAS Investor, dan KITAS Pensiun. Termasuk PNBP resmi berdasarkan PP tentang PNBP Kemenkumham dan markup agen visa di Bali.

---

### L3 — Predictive (4 queries)

**L3-1 — Implementing Regulations Forecast (Bahasa)**

> Peraturan pelaksana (Permenkumham, Permenaker, PP) yang diharapkan terbit untuk mengimplementasikan UU Nomor 1 Tahun 2026 tentang Imigrasi: daftar peraturan turunan yang belum diterbitkan, timeline yang diumumkan pemerintah, dan dampak pada pemohon visa selama masa transisi. Sumber resmi dan analisis hukum.

**L3-2 — RPTKA Digitalization (English)**

> Indonesia's RPTKA and work permit digitalization roadmap 2025-2027: TKA Online system development, integration with OSS-RBA, planned automation of DKPTKA payments, and timeline for full online processing. Government technology announcements and Kemnaker publications.

**L3-3 — Enforcement Trends (Bahasa)**

> Tren penegakan hukum keimigrasian Indonesia 2024-2026: statistik operasi pengawasan orang asing (Pora), jumlah deportasi, overstay enforcement di Bali, dan proyeksi intensifikasi pengawasan berdasarkan UU Imigrasi baru. Data dari Ditjen Imigrasi, Kantor Imigrasi Ngurah Rai, dan laporan media terverifikasi.

**L3-4 — Digital Nomad Policy Direction (English)**

> Predicted evolution of Indonesia's approach to remote workers and digital nomads 2026-2027: signals from government statements on E33G visa expansion, tax framework development for remote workers, Bali provincial government position on digital nomad infrastructure, and comparison with Thailand LTR and Malaysia DE Rantau program trajectories.

---

### L4 — Cross-Domain (4 queries)

**L4-1 — Immigration x Tax (English)**

> Intersection of Indonesia immigration status and tax obligations 2025-2026: tax residency determination for KITAS holders, NPWP requirements by visa type, DGT enforcement on foreign workers, and impact of UU HPP on expatriate taxation. Cross-referencing immigration regulations with tax circulars.

**L4-2 — Immigration x Company Setup (Bahasa)**

> Dampak peraturan imigrasi terhadap pendirian perusahaan PMA di Indonesia 2025-2026: persyaratan RPTKA sebelum pendirian, hubungan KBLI dengan jabatan TKA yang diizinkan, kewajiban rasio tenaga kerja asing-lokal, dan integrasi proses di OSS-RBA.

**L4-3 — Immigration x Property (English)**

> Legal framework connecting immigration status to property rights in Indonesia 2025-2026: Hak Pakai eligibility by visa type, KITAP holder property rights vs KITAS holder limitations, recent court decisions on foreigner property ownership, and impact of new Agraria regulations.

**L4-4 — Immigration x ASEAN Integration (English)**

> ASEAN economic integration effects on Indonesia's immigration policy 2025-2026: MRA impact on professional work permits, ASEAN Business Travel Card utilization, intra-ASEAN investment visa facilitation, and Indonesia's position on ASEAN labor mobility frameworks.

---

## NOTA IMPORTANTE: Volume Query

> Le 20 query sono il CATALOGO COMPLETO per il testing. In produzione NON gireranno tutte ogni giorno.
> L'obiettivo del test e' capire QUANTE e QUALI query servono realmente, con quale frequenza,
> e quali producono valore vs rumore. Il volume di produzione sara' probabilmente 2-4 query/giorno
> per NB, da definire dopo i risultati del test.

## Open Questions for Testing

1. **Query style**: Does NLM Deep Research respond better to Gemini-style research briefs (25-50 words) or Codex-style keyword queries (5-12 tokens)?
2. **Source hints**: Does naming `.go.id` in the query text actually improve source quality, or does NLM ignore it?
3. **Noise exclusion**: Does adding "bukan blog wisata" actually reduce noise, or is specificity alone sufficient?
4. **Language pairs**: Does running EN+ID on same topic produce duplicate sources or genuinely complementary ones?
5. **Rate limits**: How many Deep Research queries can we run per day before NLM throttles?

These questions get answered in Step 7 (Testing Protocol).

---

## Source AI Contributions

### Gemini — Best on architecture

- Dual-language with role separation (not duplication)
- 5-day cluster rotation, 4-week level cycle
- Signal-triggered follow-up with JSON state tracking
- Most detailed query templates (natural language style)

### Codex GPT-5.4 — Best on precision

- `ID first, EN confirm, mixed bridge only where taxonomy differs`
- Shortest, most surgical queries (5-9 tokens)
- `baseline coverage + temporary topic amplification, never full pivot`
- Dynamic denylist of noisy domains

### DeepSeek R1 — Best on formulas

- Confidence scoring: Authority(0.4) + Recency(0.3) + Corroboration(0.3)
- Query performance metrics: CTR tracking, precision scoring
- `site:.go.id` operator suggestions (need to test if NLM supports this)
- Semi-annual query overhaul based on accumulated vocabulary
