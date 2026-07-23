---
adversarial_review: fable5
---

## SEAT VERDICT

**FIX-FIRST** — the analysis is usable as the plan basis: the P0 (broken feed) is real and correctly prioritized, and 3 of 4 regulatory anchors verify cleanly. But it carries one material mechanism error in M1 (the request *does* reach the backend — a catch-all proxy the architect missed), one wrong regulatory date (Kepmen effective 2025-06-01, not 2026-06-02), and one refuted detail (no "Permenkumham 10/2026 Second Home" exists). Corrections below are cheap; none changes the critical path ordering.

## LIVE-SITE EVIDENCE

All probes run 2026-07-23 ~15:40–15:50 UTC from Air-M5.

| Probe | Result | Notes |
|---|---|---|
| `GET www.balizero.com/api/visa/match` | **401** | Body `{"detail":"Authentication required"}`; headers include `fly-request-id`, `via: 1.1 fly.io`, `server: Vercel`, `www-authenticate: Bearer` → **proxied to Fly, rejected by backend auth floor** |
| `POST www.balizero.com/api/visa/match` (`-d '{}'`) | **401** | Same FastAPI body, same Fly headers |
| `POST …/api/visa/match` with fake `Authorization: Bearer` | **401** | Real credential check, not a missing route |
| `OPTIONS …/api/visa/match` | **404** | No CORS preflight handler on that backend path |
| `GET www.balizero.com/api/health` | **200** | `{"status":"ok","timestamp":…}` — served by Vercel (Next route handler, no Fly headers) |
| `GET www.balizero.com/api/nonexistent-test` | **401** | Also carries `fly-request-id` → **all** unmatched `/api/*` proxy to Fly |
| `GET kita.balizero.com/api/visa/match` | **401** | `{"detail":"Authentication required"}` — matches analysis verbatim |
| `POST kita.balizero.com/api/visa/match` | **401** | Same |
| `GET /visa`, `/visa/match`, `/visa-oracle` | 301 → 200 | Redirect is only www→apex; final pages all 200 |
| `/visa-oracle` HTML | `noindex` **confirmed** | `<meta name="robots" content="noindex, nofollow"/>`; title "Visa Oracle — Prototype \| Bali Zero" |
| `/visa-v2` | **308** → `/visa-oracle` | Matches analysis |
| `/visa/match` wizard | **Renders** | 51 KB SSR HTML: "4 short questions. A visa recommendation with the cost."; repo source confirms steps nationality→purpose→duration→budget (`page.tsx:79-249`) and the bare same-origin POST with swallowed failure → WhatsApp fallback (`page.tsx:252-280`) |

Repo archaeology (read-only): `apps/mouth/src/app/api/[...path]/route.ts` — a 434-line catch-all proxy forwarding every unmatched `/api/*` to `NUZANTARA_API_URL` (default `https://nuzantara-rag.fly.dev`) — **exists since commit `7c1d23a686`, 2025-12-19**, long before the April 2026 breakage window.

## CLAIM-BY-CLAIM

**M1 — broken SHADOW feed: CONFIRMED in effect, PARTIAL/REFUTED in mechanism.**
- ✅ GET/POST 401 on www and kita, `/api/health` 200, `/api/nonexistent-test` 401 — every status code reproduces exactly.
- ❌ "There is NO Next.js route handler for it … and NO rewrite … the v1 wizard's POST **never reaches the backend**" — REFUTED. There is no visa-*specific* handler and no config rewrite, but the catch-all `[...path]` proxy has forwarded `/api/visa/match` to Fly since 2025-12-19. Proven by `fly-request-id`/`via: fly.io` on the live 401 and the byte-identical FastAPI error body vs. the direct `kita` call. The POST **does** reach the backend and dies on the auth floor. The analysis's own open question ("missing Next route vs backend auth floor?") is now answered by evidence: **single failure layer = backend auth gate**.
- ✅ Consequence fully confirmed: wizard submits bare same-origin POST → 401 → silent degradation to error+WhatsApp fallback. The live funnel *looks* alive (page 200, wizard renders, copy intact) but is functionally dead at submit — consistent with the claimed `visa_checks` gap.
- ⚠️ "`visa_checks`: 28 rows, min 2026-04-18, max 2026-04-21" — **UNVERIFIABLE from this seat** (DB-side claim, no read path from M5). Treat as corroborated-by-behavior, not independently confirmed. The "~7/day at launch" traffic estimate in M5 inherits this caveat.

**Anchor 1 — Kepmen M.IP-08/2025, 133→110 indexes: CONFIRMED; effective date REFUTED.**
- 133→110 consolidation confirmed by the [official decree PDF on kemenimipas.go.id](https://kemenimipas.go.id/attachments/2025/peraturan/20250813_09_Kepmen_No_M.IP-08.GR.01.01_Th_2025_Tentang_Klasifikasi_Visa.pdf) (full number **M.IP-08.GR.01.01/2025**), [Freshfields](https://www.freshfields.com/globalassets/our-thinking/campaigns/asia-employment-bulletin/apac-employment-law-bulletin-2026-freshfields.pdf), and [EY](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-gl/technical/tax-alerts/documents/indonesia-implements-new-immigration-classifications.pdf).
- Effective date: the decree is **signed 2025-05-02**; dictum KELIMA reads "mulai berlaku setelah 30 hari terhitung sejak tanggal ditetapkan" → **effective 2025-06-01**. EY independently states "Effective 1 June 2025". The corpus's `2026-06-02` is the wrong year; `2025-06-02` is off by one day. I read dictum KELIMA in the primary source — this is the arbitration answer.
- Bonus confirmation: dictum KEEMPAT revokes Kepmenkumham M.HH-02.GR.01.04/2023 (the old classification containing the B211* codes) → the "dead B211* codes" claim is **CONFIRMED** with a precise legal basis.

**Anchor 2 — Permen Imipas 10/2026, BVK nationality-only, 19 states incl. Macau: CONFIRMED (with dates and a refuted sub-claim).**
- Signed **2026-07-07**, effective **2026-07-09**; removes the residence-permit eligibility basis ("or Holders of Certain Residence Permits of a Country" struck from the 10/2025 title) → eligibility by nationality/SAR/entity only. Adds Kazakhstan, **Macau SAR**, Belarus; revokes Permen Imipas 10/2025 (which had added Türkiye, Brazil, Peru). Source: [Veritask analysis](https://veritask.ai/en/artikel/minister-of-immigration-and-corrections-regulation-number-10-of-2026-expands-the-list-of-indonesian-visa-free-visit-beneficiaries), corroborated by [ANTARA](https://kalteng.antaranews.com/berita/834891/regulasi-baru-kemenimipas-perluas-akses-bebas-visa-kunjungan-bagi-enam-negara).
- "19 states incl. Macau": **CONFIRMED** against the [official imigrasi.go.id BVK list](https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-bebas-visa-kunjungan) — 19 numbered countries/SARs (Makau = #18) **plus** entry 20, Singapore permanent-residents via designated checkpoints. Precise formulation: "19 states/SARs + 1 entity class".
- ❌ "Number-collision with Permenkumham 10/2026 (Second Home)": **REFUTED as stated.** The real [Peraturan Menteri Hukum Nomor 10 Tahun 2026](https://paralegal.id/peraturan/peraturan-menteri-hukum-nomor-10-tahun-2026/) (2026-01-28) regulates **notary beneficial-owner (PMPJ) obligations**, not Second Home. Second Home rests on SE Ditjen Imigrasi IMI-0740.GR.01.01/2022 and the E28B/E33F indexes ([imigrasi.go.id E33F](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33F)). A *generic* collision does exist — both ministries have a "10/2026" — so the caution is worth keeping in corrected form.

**Anchor 3 — Permen Imipas 5/2025 revoking Permenkumham 36/2021: CONFIRMED.**
[Official PDF on JDIH BPK](https://peraturan.bpk.go.id/Download/378168/Permen%20Imipas%20Nomor%205%20Tahun%202025.pdf): "Pencabutan Permenkumham Nomor 36 Tahun 2021 tentang Penjamin Keimigrasian"; ditetapkan 2025-02-07, berlaku 2025-03-07 ([BPK metadata](https://peraturan.bpk.go.id/Details/316860/permen-imipas-no-5-tahun-2025), [JDIH Kemenimipas](https://jdih.kemenimipas.go.id/jdih/regulations/view/permenimipas-no-5-tahun-2025-pencabutan-peraturan-menteri-hukum-dan-hak-asasi-manusia-nomor-36-tahun-2021-tentang-penjamin-keimigrasian)).

**Anchor 4 — Golden Visa 1,274 / Rp52.1T as of ~May 2026: CONFIRMED.**
1,274 visas and Rp52.1 trillion as of **2026-05-18**, per [ANTARA English](https://en.antaranews.com/news/416531/indonesias-golden-visa-helps-global-talents-to-support-economy-govt), [VnExpress](https://e.vnexpress.net/news/travel/visa/southeast-asia-s-largest-economy-draws-3b-of-investment-through-10-year-golden-visa-program-5077261.html), [IMI](https://www.imidaily.com/asia-pacific/indonesia-golden-visa-nears-us3-billion-in-investment-ahead-of-two-year-mark/), [Indonesia Expat](https://indonesiaexpat.id/news/two-years-after-launch-indonesias-golden-visa-investment-value-reaches-rp52-1-trillion/). The E28D = Rp50.88T breakdown also checks out (corporate-investor class, dominant share). Matches the analysis to the digit.

## MISSED

- **P0 — The catch-all proxy itself.** Missing `app/api/[...path]/route.ts` inverted the M1 mechanism. Practically: **no new Next route is needed for connectivity** — the request already lands on Fly. The cheapest fix is a public, scoped, rate-limited `POST /api/visa/match` on the backend (its wizard payload is non-PII multiple-choice facts); the service-token-via-Next-route design also works but solves a problem that doesn't exist (transport) instead of the one that does (auth floor).
- **P1 — Three months of silent failure means zero detection signal.** `page.tsx` calls `tracker.formSubmitted()` on *attempt*, not outcome, and `setSubmitError` emits no telemetry. Nobody compared wizard starts vs. `visa_checks` rows for 3 months. Whatever the fix, add a submit-failure event + an alert on `visa_checks` ingestion rate, or the next breakage repeats invisibly. (G-a's own evidence collector would have caught this — another reason the feed fix precedes everything.)
- **P1 — `OPTIONS /api/visa/match` → 404.** No CORS preflight on that backend path. Irrelevant for the same-origin wizard, but any future cross-origin consumer (partner embed, kita-direct) will hit it.
- **P2 — Redirect hygiene in the transcript.** All three page URLs are 301 (www→apex) before 200; the analysis recorded bare "200". Harmless but worth a footnote for reproducibility.
- **P2 — Recency risk the analysis should flag harder:** Permen Imipas 10/2026 is **14 days old**. Track B FASE 2 content and any BVK rules in the RulePack must be authored against the 10/2026 list (19+1), not 10/2025 — the regulatory-cadence claim (~3-4 months) is directionally supported (5/2025 Mar → M.IP-08 Jun 2025 → 10/2025 → 10/2026 Jul).

## CORRECTIONS

1. **M1 mechanism rewrite.** Replace "There is NO Next.js route handler for it … and NO rewrite … The v1 wizard's POST never reaches the backend" with: *a catch-all proxy (`apps/mouth/src/app/api/[...path]/route.ts`, in repo since 2025-12-19) forwards `/api/visa/match` to the Fly backend, where the auth floor returns 401 (verified live: `fly-request-id`/`via: fly.io` headers; error body byte-identical to the direct `kita` call). Single failure layer = backend auth gate.*
2. **Resolve the open question.** "Missing Next route vs backend auth floor" is settled by evidence: backend auth floor. Reframe P0 fix 0 accordingly — minimal fix is a public scoped+rate-limited backend endpoint (or token injection); connectivity plumbing already exists.
3. **Kepmen date.** Strike `2026-06-02`; the corpus's `2025-06-02` is also wrong by one day. Correct: **signed 2025-05-02, effective 2025-06-01** (dictum KELIMA, 30 days post-signature; EY concurs). Cite the full number M.IP-08.GR.01.01/2025 and dictum KEEMPAT (revokes M.HH-02.GR.01.04/2023) as the legal death of the B211* codes.
4. **Permen Imipas 10/2026 precision.** Add: signed 2026-07-07, effective 2026-07-09; consolidates (adds Kazakhstan/Macau SAR/Belarus, revokes 10/2025's Türkiye/Brazil/Peru grant into one list); BVK list = **19 states/SARs + 1 entity** (Singapore PRs via designated checkpoints).
5. **Fix the collision note.** Delete "Permenkumham 10/2026 (Second Home)" — the actual Permenkum 10/2026 covers notary PMPJ obligations; Second Home = SE IMI-0740.GR.01.01/2022 (+E28B/E33F). Keep only the generic warning that "10/2026" exists in two ministries' numbering.
6. **Live-site footnote.** `/visa`, `/visa/match`, `/visa-oracle` = 301 (www→apex) → 200; `/visa-oracle` verified `noindex, nofollow`; `/visa-v2` → 308 confirmed.
7. **Flag the DB-only claims.** `visa_checks` 28-row window and the M5 traffic extrapolation were not independently verifiable from this seat; mark them "architect-reported, behavior-corroborated" rather than "verified" in the final plan, and have the DB seat re-run the query before the owner sees M5's re-calibration ask.