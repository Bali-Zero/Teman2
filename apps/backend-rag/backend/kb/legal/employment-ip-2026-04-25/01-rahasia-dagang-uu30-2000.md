---
title: Rahasia Dagang (Trade Secret) Protection — UU 30/2000 in Employment Contracts
domain: company
subdomain: employment_law_ip_protection
topic: trade_secret
collection: legal_unified_hybrid_hybrid
notebook: NB-3
language: ID + EN
priority: P0
applicable_law: UU No. 30 Tahun 2000 tentang Rahasia Dagang
sources:
  - https://peraturan.bpk.go.id/Home/Download/33395/UU%20Nomor%2030%20Tahun%202000.pdf
  - https://www.dgip.go.id/menu-utama/rahasia-dagang/pengenalan
  - https://affa.co.id/global/2024/09/09/understanding-trade-secret-laws-in-indonesia-scope-and-consequences
---

# Rahasia Dagang Protection in PKWT — UU 30/2000

## Statutory definition (verbatim)

**UU No. 30 Tahun 2000 Pasal 1 angka 1:**

> "Dalam Undang-Undang ini yang dimaksud dengan Rahasia Dagang adalah informasi yang tidak diketahui oleh umum di bidang teknologi dan/atau bisnis, mempunyai nilai ekonomi karena berguna dalam kegiatan usaha, dan dijaga kerahasiaannya oleh pemilik Rahasia Dagang."

## The three constitutive elements (UU 30/2000 Pasal 3)

For information to qualify as **legally protected** rahasia dagang, ALL THREE must be present:

### 1. Kerahasiaan (Secrecy)

The information must NOT be publicly known or accessible. Practical implication: limited access, controlled distribution.

### 2. Nilai Ekonomi (Economic Value)

The information must have **commercial value derived from its secrecy**. Practical implication: the information gives the owner competitive advantage; if disclosed, value would be lost.

### 3. Upaya Menjaga Kerahasiaannya (Reasonable Efforts to Maintain Secrecy)

The owner must **actively take reasonable steps** to keep it secret. Without active protection efforts, the courts will not extend protection. Practical examples:

- Role-based access control (RBAC)
- Multi-factor authentication (MFA)
- Encryption (at rest + in transit)
- Audit logs
- Device policy
- Employee NDAs
- Restricted private repository access
- Periodic security reviews

## What qualifies as Rahasia Dagang for a software/AI company

Practitioner inventory for a Bali-based PT operating an AI/RAG platform:

| Category                   | Examples                                                                                                                                                        |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Source code**            | Repository code (Python, FastAPI, TypeScript), modules, libraries, scripts, infrastructure config (Fly.io, Vercel, Docker), CI/CD pipelines, alembic migrations |
| **AI Prompts**             | System prompts, prompt library, orchestration prompts, RAG prompts, agent prompts                                                                               |
| **RAG / KB**               | Retrieval architecture, hybrid search config (BM25+Dense+RRF), Knowledge Graph, Qdrant collections, internal knowledge base                                     |
| **Customer Data**          | Active client list, contact data, practice history, KTP/KITAS/passport copies, NPWP, NIB, akta                                                                  |
| **Pricing & Strategy**     | PricingTool, internal price lists, marketing strategy, vendor list, commercial contracts                                                                        |
| **Internal Documentation** | Notion docs, Drive folders, CLAUDE.md / SYMBIOSIS.md / VADEMECUM.md / INDEX.md, architecture & operations docs                                                  |

## Contract drafting — best practice

### Rule: explicitly recite the three elements

Don't rely on implicit protection. The contract must:

1. **List specifically** what is "DIANGGAP RAHASIA DAGANG" (in an Annex/Lampiran)
2. **Recite the three elements** (kerahasiaan + nilai ekonomi + upaya menjaga) as parties' express acknowledgment
3. **Describe the operational protection measures** (RBAC/MFA/encryption/audit) the company implements

### Sample acknowledgment clause (Bahasa Indonesia)

```
PARA PIHAK secara tegas mengakui bahwa seluruh informasi yang tercantum
pada Lampiran A memenuhi ketiga unsur Rahasia Dagang sesuai Pasal 3 UU
No. 30 Tahun 2000:
(a) bersifat rahasia — hanya dapat diakses oleh pihak terbatas;
(b) memiliki nilai ekonomi — memberikan keunggulan kompetitif kepada
    Perusahaan;
(c) dijaga kerahasiaannya — Perusahaan menerapkan kontrol akses berbasis
    peran, MFA, enkripsi, audit log, kebijakan perangkat, NDA, dan
    pembatasan akses pada repositori privat.
```

## Duration of confidentiality obligation

### Question: is perpetual post-termination confidentiality enforceable?

**Answer:** YES, **as long as the information continues to satisfy the three elements**. The obligation survives termination indefinitely, but:

- If information becomes public through no fault of the employee → obligation extinguishes
- If the company ceases to maintain "upaya menjaga" → obligation extinguishes (loss of trade secret status)
- Information that was already public before contract → never covered

### Sample duration clause (Bahasa Indonesia)

```
PIHAK KEDUA wajib menjaga kerahasiaan Rahasia Dagang selama masa kerja
dan setelah berakhirnya hubungan kerja TANPA BATAS WAKTU, sepanjang
informasi tersebut tetap memenuhi unsur Rahasia Dagang menurut UU No.
30 Tahun 2000 dan PIHAK PERTAMA terus melakukan upaya menjaga
kerahasiaannya.
```

## Penalties — civil + criminal cumulative

### Civil

- Wanprestasi (breach of contract) under contract law
- Damages under Pasal 11 UU 30/2000 + KUHPerdata
- Injunctive relief

### Criminal — UU 30/2000 Pasal 17

> "Barangsiapa dengan sengaja dan tanpa hak menggunakan Rahasia Dagang pihak lain ... diancam dengan pidana penjara paling lama 2 (dua) tahun dan/atau denda paling banyak Rp 300.000.000,00 (tiga ratus juta rupiah)."

Criminal complaint filed at Polda regional. The civil and criminal routes are **independent and cumulative** — payment of civil damages does NOT extinguish the criminal action.

## Enforcement: what to do when leak suspected

1. **Forensic preservation immediate** — image of work device, log capture, hash, timestamp
2. **Civil:** ex-parte sita jaminan (RBg) over devices suspected of containing trade secrets
3. **Civil suit:** Pengadilan Niaga (Surabaya for Bali) — wanprestasi + ganti rugi + injunctive relief
4. **Criminal complaint:** Polda Bali — UU 30/2000 Pasal 17 + UU ITE Pasal 30 (akses tanpa hak)

## Common drafting mistakes (avoid)

| Mistake                                             | Why it fails                              | Fix                                         |
| --------------------------------------------------- | ----------------------------------------- | ------------------------------------------- |
| Generic "menjaga kerahasiaan" without listing what  | Doesn't satisfy element 1 (specificity)   | Lampiran A with specific items              |
| No description of company's protection measures     | Doesn't satisfy element 3 (upaya menjaga) | Recite RBAC/MFA/encryption/audit explicitly |
| No survival clause                                  | Post-termination obligation contestable   | Explicit "tanpa batas waktu sepanjang..."   |
| Penalty amount unrealistically high (e.g. Rp 500jt) | Hakim reduces under KUHPerdata Pasal 1249 | Use 3-6× monthly salary as proxy            |
| Mixed jurisdiction without IP carve-out             | Court confusion (PHI vs Niaga)            | Separate Pasal: PHI for labor, Niaga for IP |

## Cross-references

- Copyright assignment: `02-hak-cipta-uu28-2014-employment.md`
- Non-compete: `03-non-compete-MA-3549-2023.md`
- Pasal templates: `05-pasal-templates-ready-bahasa-indonesia.md`
