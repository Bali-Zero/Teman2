---
date: 2026-05-22
domain: operations
client_case: "Antonello personal SIM +62 821 6459 9868 activation (Italian national, KITAS holder, PT PMA owner Bali Zero, Bali)"
sources: 11
status: draft
---

# Telkomsel Prepaid SIM Registration Procedure for +62 821 6459 9868 (Italian national, Bali)

## Question

How does Antonello (Italian, KITAS, PT PMA owner) activate Telkomsel +62 821 6459 9868 in Bali in May 2026 under the new biometric regulation?

## TL;DR

- **Prefix 0821 = Telkomsel simPATI prepaid** (not Halo postpaid; postpaid uses 0811). Confirmed via Telkomsel prefix maps.
- **Regulation just changed**: Permen Komdigi 7/2026 effective **19 Jan 2026** mandates **biometric face recognition** for new registrations; transition until ~Jul 2026 still allows NIK+KK self-registration for WNI. **For WNA (foreigners) registration was already GraPARI-only — no SMS 4444 self-service path** because WNA has no NIK+KK pair.
- **Action for Antonello**: bring KITAS + passport to **GraPARI Renon** (closest to Sanur/Bali Zero office); the agent registers passport/KITAS number + biometric. Do NOT attempt SMS 4444 — it will fail (no NIK+KK).

## Key citations (verbatim)

- **Permen Komdigi 7/2026** (effective 19 Jan 2026, supersedes Art. 153–175 of Permenkominfo 5/2021 which itself absorbed Permenkominfo 14/2017): "_penyelenggara dilarang melakukan registrasi lebih dari tiga nomor prabayar untuk setiap identitas pelanggan pada satu operator yang sama_" — max 3 prepaid per identity per operator. WNA register with "_nomor pelanggan disertai dengan paspor, Kartu Izin Tinggal Tetap (KITAP), atau Kartu Izin Tinggal Terbatas (KITAS)_". WNI add facial-recognition biometric (≥95% match, ISO/IEC 30107-3). Old NIK+KK self-registration allowed until system upgrade deadline (~19 Jul 2026). Source: justisio + komdigi + Kompas Tekno.
- **Telkomsel FAQ WNA** (verbatim): "_Foreign Citizens may do prepaid registration by coming to telco operator outlets or its partners_. The outlet records _name, passport/Temporary Stay Permit Card (KITAS)/Permanent Stay Permit Card (KITAP) number, citizenship, as well as Date & Place of Birth_." No self-service for WNA.
- **Telkomsel prefix map**: 0821 / 0822 / 0823 = simPATI/Kartu AS prepaid; 0811 = Halo postpaid.

## Findings

### 1. Legal framework (May 2026 reality)

The often-cited "Permenkominfo 14/2017" was already absorbed into Permenkominfo 5/2021 (omnibus). On **19 Jan 2026** Komdigi issued **Permen Komdigi 7/2026** ("Registrasi Pelanggan Jasa Telekomunikasi Melalui Jaringan Bergerak Seluler"), effective 23 Jan 2026, replacing Articles 153–175 of Permenkominfo 5/2021. Key changes:

- Mandatory **face-recognition biometric** for WNI new registrations (95% match, ISO/IEC 30107-3 liveness).
- Starter SIM cards must be shipped **inactive**; activation only after biometric verification.
- Cap: **max 3 prepaid numbers per identity per operator** (unchanged from 2017 rule).
- WNA path **unchanged in substance**: passport, KITAS, or KITAP, validated at operator outlet.
- Transition: until ~19 Jul 2026 WNI may still use the legacy NIK+KK channel (SMS 4444, web, app).

### 2. Activation channels — feasibility ranking for Antonello

| Channel                                                                | Antonello (KITAS holder)                                                                                                      | Works?                                                |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **GraPARI walk-in with KITAS + passport**                              | Agent enters passport + KITAS number, captures bio data + face                                                                | **YES — recommended**                                 |
| SMS to 4444 (format `REG NIK#KK#`)                                     | Requires Indonesian NIK (KTP) and KK number; KITAS does have a NIK but Telkomsel self-service does not accept it (no KK pair) | **NO**                                                |
| MyTelkomsel app self-registration                                      | Same constraint as SMS 4444 + biometric face capture wired to Dukcapil database, foreigner not enrolled                       | **NO**                                                |
| Telkomsel web `my.telkomsel.com/v3/prepaid-registration/landing-page`  | Same constraint                                                                                                               | **NO**                                                |
| USSD `*444#`                                                           | Menu-driven equivalent of SMS 4444                                                                                            | **NO**                                                |
| Call Center 188                                                        | Triage only — will redirect to GraPARI for WNA                                                                                | NO (informational)                                    |
| **Pre-Order Tourist SIM online** (`telkomsel.com/shops/preorder-wna/`) | For inbound tourists, pickup at airport/GraPARI                                                                               | YES but he is already in Bali with SIM in hand → moot |

### 3. Edge cases

- **SIM already pre-registered to a previous owner (shop "starter pack" with someone else's NIK)**: requires "ganti kepemilikan" at GraPARI. Original registrant must come in person OR a notarised power of attorney (surat kuasa, Rp 10,000 materai) + originals of both parties' ID + KK. Telkomsel deliberately makes this friction-heavy to prevent number theft (TKBN-style security). Verify before paying: ask the shop to issue a fresh starter pack and let Antonello register on the spot at GraPARI.
- **Max SIMs**: 3 per identity per operator (Permen Komdigi 7/2026 Art.). Cross-operator total not capped by regulation but each operator enforces its own 3-cap.
- **Grace period on failed registration**: legacy 2017–2024 rule was tiered (1st period outgoing blocked, then incoming, then number reclaimed at day ~60). Telkomsel current FAQ does not publish a hard timeline; in practice a starter SIM ships inactive and only "wakes up" after successful registration. If pre-registered to someone else and not transferred, the SIM behaves as "registered but not yours" — no service.
- **Prefix lookup**: +62 821 X XXXX XXXX = **Telkomsel simPATI prepaid** (also 0822, 0823). Halo postpaid = 0811 only. So +62 821 6459 9868 is in scope of this prepaid procedure, NOT Halo Korporat.

### 4. PT PMA owner — corporate option

Halo Korporat (postpaid corporate) is a separate enrollment under the PT PMA NPWP + Akta + Direktur KTP/KITAS; numbers issued are 0811-prefix. For a personal phone Antonello already has 0821, so corporate route is not applicable to _this_ SIM. If later he wants a corporate line for Bali Zero billing, that is a different process (NPWP PT PMA + Akta + SIUP) handled by Telkomsel Account Manager, not GraPARI walk-in.

### 5. GraPARI locations Denpasar (closest to Bali Zero / Sanur)

| Outlet                                          | Address                                                         | Hours                                            |
| ----------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------ |
| **GraPARI Renon** (recommended — closest Sanur) | Jl. Raya Puputan Renon No. 33, Denpasar Selatan 80234           | Mon–Fri 08:00–17:00, Sat 08:00–12:00, Sun closed |
| GraPARI Teuku Umar                              | Gedung Plasa Telkom, Jl. Teuku Umar No. 6, Denpasar Barat 80114 | same hours                                       |
| GraPARI Gatot Subroto Timur                     | Jl. Gatot Subroto Timur No. 36C, Denpasar Timur 80237           | same hours                                       |

Call centre common to all: **0807 1 811 811** or **188** from a Telkomsel line.

## Numerical analysis

- Penalty / blocking timeline under legacy 14/2017 (still indicative): D+1 to D+15 = outgoing blocked; D+16 to D+30 = incoming blocked; D+31+ = number reclaimed. New Permen Komdigi 7/2026 does not republish the exact day count but the inactive-by-default starter card approach functionally replaces the grace-period model.
- Cost of GraPARI registration: **Rp 0** (free). Any fee charged by a non-GraPARI counter is unofficial.

## Disagreements / open questions

- Telkomsel English FAQ for WNA does not mention biometric capture for WNA, but Permen Komdigi 7/2026 Art. requires the operator to retain biometric data for WNI registrations specifically. For WNA the regulation is silent on biometric — practical expectation: GraPARI agent may take a face photo for the activation record, but it is not validated against Dukcapil (which has no WNA face data). Antonello should not be surprised if a photo is taken.
- Open: does Antonello's KITAS already have him in any Telkomsel registration (e.g. from a prior SIM)? If yes, the 3-cap may be tight. Verify via SMS `INFO` to 4444 from another Telkomsel line he owns, or ask at GraPARI.

## Decision tree

```
+62 821 6459 9868 (confirmed simPATI prepaid Telkomsel)
│
├─ KITAS active and physically in hand? ──── YES ──> Go to GraPARI Renon, bring:
│                                                    • Passport (original + photocopy of bio page + visa stamp page)
│                                                    • KITAS card (original + photocopy)
│                                                    • The SIM card itself (still in starter pack ideally)
│                                                    • Optional: NPWP if registering under business name later
│                                                    Agent registers passport+KITAS number, may capture face photo.
│                                                    Activation typically within minutes; max 24h.
│
├─ KITAS not yet issued (B211/B1/VoA only)?  ──> Same GraPARI Renon route, bring passport only.
│                                                Telkomsel WNA FAQ explicitly accepts passport-only registration.
│                                                Validity tied to visa stamp/passport — re-registration on KITAS issuance recommended.
│
└─ SIM already registered to someone else (shop sold pre-activated starter)?
                                              ──> Option A (cleanest): return SIM to shop, demand fresh inactive starter pack, register on the spot.
                                              ──> Option B: bring previous registrant in person to GraPARI Renon with their KTP+KK + Antonello's KITAS + passport, request "ganti kepemilikan" (transfer of ownership).
                                              ──> Option C (worst): notarised surat kuasa (Rp 10,000 materai) from previous registrant + originals of both parties' KTP+KK + Antonello's KITAS + passport.
                                              Do NOT pay the shop extra "activation fee" — GraPARI is free.
```

## Checklist for action (Antonello, Friday 23 May 2026)

- [ ] Verify the starter pack: is it sealed/inactive, or did the shop pre-register? Dial `*888#` from the SIM — if it returns balance info, it's already active under someone's identity.
- [ ] If active under someone else → return to shop, refuse, demand fresh sealed pack.
- [ ] Pack documents: passport (original + 1 photocopy), KITAS (original + 1 photocopy), the SIM tray/card.
- [ ] Drive to **GraPARI Renon, Jl. Raya Puputan Renon No. 33** before 12:00 Saturday (or any weekday 08–17). No appointment needed; expect 10–30 min queue.
- [ ] Confirm at counter: this is registered to "Antonello Siano" passport + KITAS, max 3-line cap; ask for activation confirmation receipt (struk).
- [ ] Test: outbound call to +62 lokal, inbound call, SMS, data session, before leaving the GraPARI.
- [ ] (Optional) Top-up Rp 100,000 at the GraPARI counter for a clean start.

## Sources

1. Telkomsel FAQ EN — "How to do prepaid registration for Foreign Citizens (WNA)" — https://www.telkomsel.com/en/support/faq/how-do-prepaid-registration-foreign-citizens-wna
2. Telkomsel FAQ ID — "Bagaimana cara melakukan registrasi kartu prabayar bagi WNA?" — https://www.telkomsel.com/support/faq/bagaimana-cara-melakukan-registrasi-kartu-prabayar-bagi-wna
3. Telkomsel support — "Registrasi SIM Card Warga Negara Asing (WNA)" — https://www.telkomsel.com/support/foreigner-simcard-activation
4. Telkomsel SIMPATI registration — https://www.telkomsel.com/en/SIMPATI/registrasi
5. Telkomsel support — "Nomor Telah Terdaftar Namun Tidak Bisa Digunakan" — https://www.telkomsel.com/support/number-registered-but-unable-to-be-used
6. Permen Komdigi 7/2026 analysis — Justisio — https://justisio.com/blog/permenkomdigi-7-2026
7. Permen Komdigi 7/2026 official text — BPK Peraturan — https://peraturan.bpk.go.id/Details/345091/permenkomdigi-no-7-tahun-2026
8. Kompas Tekno — "Komdigi Resmikan Aturan Baru Registrasi SIM Card, Wajib Biometrik" 2026-01-24 — https://tekno.kompas.com/read/2026/01/24/16041617/komdigi-resmikan-aturan-baru-registrasi-sim-card-wajib-biometrik-dan-jumlah
9. Prefix lookup — Kumparan / Detik — https://kumparan.com/how-to-tekno/0821-kartu-apa-simak-provider-aslinya-di-sini-1x2PctiXX3U and https://inet.detik.com/cyberlife/d-6819551/0821-kartu-apa-simak-penjelasan-dan-daftar-kode-prefix-lainnya
10. GraPARI Bali locations — Bali Easy eSIM guide — https://esim.balieasy.com/blog/grapari-telkomsel-bali/ and Alamatpenting — https://alamatpenting.com/grapari-telkomsel-renon-bali/
11. Simology — Indonesia SIM Registration for Foreigners 2025 — https://simology.io/blog/indonesia-sim-registration-foreigners-2025-passport-tax-id-where-register
