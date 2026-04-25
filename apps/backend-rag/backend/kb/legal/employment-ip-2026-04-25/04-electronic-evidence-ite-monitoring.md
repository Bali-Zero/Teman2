---
title: Electronic Evidence + Employee Monitoring — UU ITE & UU PDP Compliance
domain: company
subdomain: employment_law_ip_protection
topic: electronic_evidence_monitoring
collection: legal_unified_hybrid_hybrid
notebook: NB-3
language: ID + EN
priority: P0
applicable_law: |
  UU No. 11/2008 jo. UU No. 1/2024 (ITE),
  UU No. 27/2022 (Pelindungan Data Pribadi)
sources:
  - https://jdih.komdigi.go.id/produk_hukum/view/id/167/t/undangundang+nomor+11+tahun+2008
  - https://peraturan.bpk.go.id/details/274494/uu-no-1-tahun-2024
  - https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022
  - https://www.unodc.org/cld/uploads/pdf/El%20Evidence%20Hub/Electronic_Evidence_Fiche_as_8_February_2023_INDONESIA.pdf
---

# Electronic Evidence + Employee Monitoring under Indonesian Law

## UU ITE Pasal 5 — admissibility of electronic evidence

> "Informasi Elektronik dan/atau Dokumen Elektronik dan/atau hasil cetaknya merupakan alat bukti hukum yang sah."

**Practical translation:** Electronic information, electronic documents, and printouts thereof are **legally admissible evidence** in any Indonesian legal proceeding (civil + criminal).

UU No. 1 Tahun 2024 (revision of UU ITE) reinforced this principle — electronic evidence is no longer treated as second-class.

## What qualifies as electronic evidence

For an IP/employment dispute against a former employee:

| Type                         | Examples                                                    | Admissibility |
| ---------------------------- | ----------------------------------------------------------- | ------------- |
| **Git history**              | Commit logs, branch logs, push logs                         | ✅ Admissible |
| **System logs**              | Authentication logs, audit logs, API logs                   | ✅ Admissible |
| **Cloud platform logs**      | GitHub org audit, Google Workspace activity, Notion history | ✅ Admissible |
| **Network logs**             | VPN connection logs, IP records                             | ✅ Admissible |
| **Screenshots / recordings** | If timestamped + chain of custody                           | ✅ Admissible |
| **Emails**                   | Company email archive                                       | ✅ Admissible |
| **Chat logs**                | Slack/Telegram/WhatsApp on company accounts                 | ✅ Admissible |

## Chain of custody — critical for admissibility

While electronic evidence is admissible, **authenticity must be preserved**. Practical requirements:

1. **Hash the evidence** at preservation time (SHA-256 of relevant files)
2. **Timestamp** the preservation (NTP-synced)
3. **Image** rather than copy (dd / forensic tool)
4. **Document** the preservation procedure (who, when, what tool)
5. **Coordinate with platform** — request retention/audit data via cooperation letter (GitHub org admin can request audit log export)

## GitHub / cloud reality — practical implications

### Code in private GitHub organization owned by company

✅ **Strong evidence of company ownership** — committer email is company email, repo lives in company org, audit logs show employer admin control.

### Personal forks / personal GitHub accounts

⚠️ **Evidence of misappropriation** — fork or push to personal account is a documentable IP transfer event. Git logs (committer email, timestamps, branch creation) become the prosecution's roadmap.

### Cloud copies (Drive, Notion, Dropbox)

✅ **Tracked** in their respective audit trails. Drive shows download events, share grants, file copies. Notion shows page exports.

### What to preserve immediately when leak suspected

1. **GitHub org audit log** export (Settings > Audit log > Export)
2. **Git log** of all repos employee had access to (`git log --all --author=<email>`)
3. **Google Workspace activity report** (admin.google.com > Reports > Audit > Drive)
4. **Notion workspace audit log** (workspace settings)
5. **Hardware imaging** of work device(s) before return
6. **Account access logs** from any service the employee used (Fly.io, Vercel, AWS, etc.)

## Sample electronic evidence clause (Bahasa Indonesia)

```
Bukti Elektronik (berdasarkan UU ITE Pasal 5 jo. UU No. 1 Tahun 2024).

(1) PARA PIHAK secara tegas mengakui bahwa seluruh log sistem, log
    akses, riwayat Git (commit history, branch logs, push logs),
    riwayat akses repositori, log audit, log API, screenshot, video
    screen recording, riwayat akun cloud (Google Workspace, GitHub,
    Notion, dll.), email perusahaan, dan komunikasi lain dalam bentuk
    elektronik dapat dijadikan alat bukti yang sah dalam proses hukum
    manapun, baik perdata maupun pidana, sesuai dengan Pasal 5 UU ITE
    jo. UU No. 1 Tahun 2024.

(2) PIHAK PERTAMA berhak untuk melakukan forensic preservation
    (preservasi forensik) atas perangkat, akun, dan log sistem yang
    berkaitan dengan PIHAK KEDUA, termasuk hashing, imaging, dan
    timestamping, untuk keperluan pembuktian.

(3) PIHAK KEDUA tidak akan mengajukan keberatan terhadap autentisitas
    bukti elektronik yang dihasilkan dari sistem PIHAK PERTAMA dengan
    dalil teknis terhadap proses preservasi yang telah dilaksanakan
    secara wajar dan terdokumentasi.
```

## Employee Monitoring — UU PDP 27/2022 compliance

UU PDP creates obligations for employers monitoring employees as it constitutes "pemrosesan data pribadi pekerja."

### Required: legal basis for monitoring

UU PDP Pasal 20 lists the lawful bases. For employee monitoring, the most defensible are:

1. **Persetujuan pekerja** (consent) — express, informed, freely given
2. **Pelaksanaan kontrak** (contract performance) — necessary to perform employment contract
3. **Kepentingan sah** (legitimate interest) — proportional, balancing employer's interest vs. employee's rights

**Best practice:** combine all three — express consent in PKWT + contract necessity + legitimate interest declared.

### UU PDP Pasal 35-39 — operational requirements

The employer (as Pengendali Data Pribadi) must:

1. **Inform** the employee what is being monitored, why, how long
2. **Limit** monitoring to what is necessary for the stated purpose
3. **Secure** the collected data (encryption, access control)
4. **Define retention** period
5. **Allow data subject rights** (access, rectification, deletion within limits)
6. **Not use** monitoring data for unrelated purposes

### Sample monitoring clause (Bahasa Indonesia)

```
Hak Audit dan Pemantauan Elektronik (sesuai UU No. 27 Tahun 2022 PDP).

(a) PIHAK PERTAMA berhak melakukan audit, pemeriksaan, monitoring,
    logging, dan analisis forensik terhadap perangkat kerja, akun
    perusahaan, repositori, log akses, dan aktivitas sistem PIHAK
    KEDUA yang berkaitan dengan pekerjaan;

(b) Pemantauan dilakukan dengan dasar hukum kepentingan sah
    (legitimate interest) Perusahaan untuk melindungi Rahasia Dagang,
    keamanan informasi, dan kepatuhan kontrak;

(c) Pemantauan tidak ditujukan untuk komunikasi pribadi PIHAK KEDUA
    pada perangkat pribadi di luar jam kerja;

(d) PIHAK KEDUA dengan ini secara tegas menyetujui pemantauan
    sebagaimana diatur dalam Pasal ini sebagai bentuk persetujuan
    yang sah berdasarkan UU PDP.
```

## UU ITE Pasal 30 — criminal route for unauthorized access

If employee accesses systems they're not authorized to access, or maintains access after termination:

> "Setiap Orang dengan sengaja dan tanpa hak atau melawan hukum mengakses Komputer dan/atau Sistem Elektronik milik Orang lain dengan cara apa pun."

### Penalties (Pasal 46)

- **Pasal 30 ayat (1)** general unauthorized access: max **6 bulan + Rp 600 juta**
- **Pasal 30 ayat (2)** access to obtain information: max **7 tahun + Rp 700 juta**
- **Pasal 30 ayat (3)** access by breaking security: max **8 tahun + Rp 800 juta**

### Practical use

If former employee retains GitHub access after termination and uses it to download code → criminal complaint under Pasal 30 ayat (3) is appropriate.

## Forensic IT preservation playbook

When breach suspected (immediate, within hours):

| Step | Action                                                    | Tool                           |
| ---- | --------------------------------------------------------- | ------------------------------ |
| 1    | Disable employee accounts (don't delete — preserve)       | IDP / SSO admin                |
| 2    | Snapshot work device state                                | dd, FTK Imager                 |
| 3    | Hash everything                                           | sha256sum                      |
| 4    | Export audit logs from all platforms                      | GitHub, Google, Notion, Fly.io |
| 5    | Cooperation letter to platforms requesting full retention | Legal counsel                  |
| 6    | Document procedure                                        | Forensic report                |
| 7    | Engage external forensic firm if stakes high              | Local Bali IT forensic service |

## Common mistakes (avoid)

| Mistake                                      | Fix                                              |
| -------------------------------------------- | ------------------------------------------------ |
| Deleting accounts immediately on termination | Preserve access first, image device, THEN revoke |
| No monitoring consent in PKWT                | UU PDP basis becomes contestable                 |
| Monitoring personal devices/communications   | Stay within "work-related" scope                 |
| No chain of custody documentation            | Authenticity defense fails                       |
| Long retention without limit                 | UU PDP requires defined retention period         |

## Cross-references

- Trade secret (what to monitor for): `01-rahasia-dagang-uu30-2000.md`
- Pasal templates: `05-pasal-templates-ready-bahasa-indonesia.md`
