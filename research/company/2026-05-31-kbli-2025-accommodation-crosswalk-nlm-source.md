# KBLI 2025 Accommodation Crosswalk for NLM Validation

Date: 2026-05-31

Purpose: correct stale NotebookLM sources that still treat KBLI 2020 accommodation codes as current KBLI 2025 codes.

Primary authority: Peraturan Badan Pusat Statistik Nomor 7 Tahun 2025 tentang Klasifikasi Baku Lapangan Usaha Indonesia (KBLI 2025). The internal KBLI 2025 catalog used by Nuzantara/Zantara was extracted from this source and is available at `apps/backend-rag/scripts/generated_guides/company/kbli_2025_catalogo_completo.txt`.

## Operational rule for May-June 2026

When discussing WhatsApp client questions, Zantara should distinguish:

- KBLI 2020 / older OSS references that a client may still see in legacy documents or stale web pages.
- KBLI 2025 current classification codes from BPS Regulation 7/2025.
- OSS transition caveat: actual filing/registration must be checked in the live OSS/BKPM flow because the 2020-to-2025 migration is in transition until the June 2026 conversion window completes.

Do not call the KBLI 2025 code invented merely because an older NotebookLM source lacks it. If the KBLI 2025 catalog contains the code, treat the NotebookLM source as stale.

## Correct KBLI 2025 accommodation codes

### Villas / Airbnb-style direct villa operations

Current KBLI 2025 direction:

- `55203` - `AKTIVITAS VILA`
- Description: short-term accommodation for the public consisting of private houses specifically rented to tourists with facilities and managed by the owner.

Legacy/stale references may mention `55193` for villa operations. In May 2026 validation, `55193` should be treated as an older reference/mapping, not the primary KBLI 2025 answer.

### Apartment hotel / aparthotel

Current KBLI 2025 direction:

- `55204` - `AKTIVITAS APARTEMEN HOTEL`
- Description: short-term accommodation that manages and operates apartments as hotels for temporary stays.

Legacy/stale references may mention `55194` for apartment hotels or villas. In KBLI 2025 validation, use `55204` for apartment hotel / aparthotel questions.

### Homestay

Current KBLI 2025 direction:

- `55201` - `AKTIVITAS RUMAH TINGGAL SEWA (HOMESTAY)`
- Description: short-term accommodation in a residential house used by the owner and rented daily or weekly.

Legacy/stale references may mention `55130` for pondok wisata/homestay. In KBLI 2025 validation, do not force Zantara back to `55130` when the current KBLI 2025 catalog returns `55201`.

### Accommodation management for third-party properties

Current KBLI 2025 direction:

- `55901` - `AKTIVITAS JASA MANAJEMEN AKOMODASI`
- Description: third-party management services for accommodation businesses, including responsibility for business performance and daily operations.

Legacy/stale references may mention `55900`. For current KBLI 2025 validation, `55901` is the more precise management code to consider.

### Accommodation intermediation / booking platform

Current KBLI 2025 direction:

- `55400` - `AKTIVITAS JASA INTERMEDIASI AKOMODASI`
- Description: intermediation of accommodation services by matching clients and service providers for a fee or commission.

This is the KBLI 2025 direction for a platform/intermediary model, not for a company directly operating a villa.

## Validation expectation for Zantara replies

For WhatsApp replies, a safe answer should:

- explain both old and current codes when the user asks `55193 vs 55203` or similar;
- say that `55203` is the current KBLI 2025 villa direction for direct villa accommodation;
- say that `55901` may apply to third-party accommodation management;
- say that `55400` may apply to accommodation intermediation/platform activity;
- ask about the actual operating model before giving a final code;
- add a live OSS/BKPM filing caveat during the transition window.

The answer should not present the code as final legal advice. Final classification still depends on the actual contract structure, location/zoning, licensing route, and OSS/BKPM availability at filing time.
