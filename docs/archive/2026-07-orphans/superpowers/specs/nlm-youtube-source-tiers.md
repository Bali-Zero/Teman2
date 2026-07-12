# YouTube Source Tier Classification — NLM Notebooks

> **Date:** 2026-03-29
> **Scope:** All 10 NB notebooks
> **Purpose:** Classify YouTube sources by authority tier, same as document sources

---

## YouTube Tier Definitions

| Tier        | Name                            | Description                                                                                                                                                                                                     | Examples                                                                                                                                               | Trust Level                                                        |
| ----------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| **YT-T0**   | **Government Official**         | Channels owned/operated by Indonesian government ministries, agencies, directorates. Official press conferences, regulatory presentations, official tutorials.                                                  | Kementerian Investasi (BKPM), Ditjen Imigrasi, DJP (Direktorat Jenderal Pajak), ATR/BPN, Sekretariat Presiden, Kemenkumham, KLHK                       | **HIGHEST** — equivalent to gazette for procedural content         |
| **YT-T1**   | **Major Press & Institutional** | National broadcast media, top-tier news outlets, official institutional channels (universities, professional associations). Press conferences hosted by media, investigative reports, expert panel discussions. | CNBC Indonesia, Kompas TV, Metro TV, CNN Indonesia, IDX Channel, Katadata, Hukumonline TV, PERADI (lawyers association), IAI (accountants)             | **HIGH** — journalistic standard, verifiable                       |
| **YT-T2**   | **Recognized Professionals**    | Named experts with verifiable credentials: senior lawyers at top-10 law firms, licensed notaries (PPAT), certified public accountants, university professors. Must be identifiable + credentialed.              | SSEK Law webinars, Hadiputranto (HHP) seminars, notary association channels, Big 4 accounting (PwC/EY/Deloitte/KPMG Indonesia), university law faculty | **MEDIUM-HIGH** — expert opinion, check against T0                 |
| **YT-T3**   | **Specialist Consultants**      | Business consultancy channels with track record: licensed agents (PPJT, immigration agents), established consulting firms, industry association channels. Must have business registration verifiable.           | Bizindo, Emerhub, InCorp, Seven Stones, Cekindo, ILA Global, licensed PPJT firms, APINDO (employers assoc), KADIN                                      | **MEDIUM** — operational knowledge, cross-verify claims            |
| **YT-T4**   | **Educational/Training**        | Training companies, course providers, independent educators with expertise. Good for practical how-to but verify regulatory claims.                                                                             | Mudjisantosa (MS Training), enviplan (environmental), tax training channels, OSS tutorial creators, UMKM educators                                     | **MEDIUM-LOW** — practical value, verify against T0-T2             |
| **YT-T5**   | **Community/Influencer**        | Expat YouTubers, lifestyle channels, personal experience videos. Useful for understanding client perspective and common questions, NOT for regulatory claims.                                                   | Expat channels, "moving to Bali" vloggers, digital nomad content, personal experience stories                                                          | **LOW** — sentiment/question discovery only, never cite for claims |
| **YT-DENY** | **Denylist**                    | Clickbait, SEO spam, outdated content (pre-2023), channels with known misinformation, foreign-jurisdiction content misapplied to Indonesia.                                                                     | "Make money in Bali" clickbait, Singapore/Malaysia content about Indonesia, pre-Cipta Kerja outdated tutorials                                         | **REJECT** — do not ingest                                         |

---

## Scoring Rules

1. **Government channels (YT-T0)** get same SVS boost as T0 documents
2. **Video age matters more than documents**: regulation videos from pre-GR 28/2025 (before June 2025) are potentially outdated for licensing topics
3. **Language bonus**: Bahasa Indonesia videos from government = highest authority. English translations by government = same tier. English by consultants = T3 max.
4. **Duration signal**: Webinars >30min from T0-T2 sources = high value (deep content). <3min from any tier = likely overview only.
5. **Cross-reference rule**: Any regulatory claim from YT-T3+ MUST be verified against T0-T2 before VERIFIED classification. YT-T0/T1 claims can be VERIFIED with 1 corroborating source.

---

## Per-Notebook YouTube Strategy

### NB-2: Immigration & Visa

- **YT-T0 targets**: Ditjen Imigrasi, Kemenkumham, Kemnaker
- **YT-T1 targets**: CNBC Indonesia immigration segments, Kompas TV
- **Topics**: visa policy changes, KITAS/KITAP procedures, TKA regulations, enforcement news

### NB-3: Company Setup

- **YT-T0 targets**: Kementerian Investasi (BKPM), Kemenkumham (AHU), Ditjen Perindustrian
- **YT-T1 targets**: CNBC Indonesia business, IDX Channel
- **Topics**: PP 28/2025 explainers, OSS tutorials, PT PMA procedures, LKPM

### NB-4: Tax & Fiscal

- **YT-T0 targets**: DJP (Direktorat Jenderal Pajak), Kemenkeu
- **YT-T1 targets**: CNBC Indonesia tax segments, Katadata fiscal
- **Topics**: Coretax tutorials, SPT filing, HPP implementation, PPh/PPN changes

### NB-5: Property & Real Estate

- **YT-T0 targets**: Kementerian ATR/BPN, Dinas PUPR
- **YT-T1 targets**: CNBC Indonesia property, Kompas TV property segments
- **Topics**: land registration, HGB/Hak Pakai, zoning, PBG procedures, foreigner property rules
