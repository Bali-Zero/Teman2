---
date: 2026-08-11
domain: operations
client_case: none
track: BOT-KBLI
adversarial_review: gemini
sources:
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json
  - https://jdih-storage.bkpm.go.id/jdih/jdih/2025Permeninvesthil005-.pdf
  - https://jdih.kemkes.go.id/storage/documents/pdfs/2025permenkes011.pdf
---

# Zantara WhatsApp KBLI grounding benchmark

Date: 2026-08-11
Track: `BOT-KBLI` / Lane B
Surface: WhatsApp payload to `POST /api/agentic-rag/query` (`channel=whatsapp`, `max_steps=2`)
Production machine: Fly `nuzantara-rag`, process `rag`, machine `1781e5eda03438`

## Decision and acceptance contract

This lane changes no model pin. Production remains:

- primary: `gemini-3.5-flash`
- fallback: `gemini-2.5-flash`

The defect under test is narrow: configuring tools on the shared LLM gateway must not be treated as evidence that a tool was executed or that its observation supports the final answer. A response passes only when it is faithful to the cited/retrieved source, or when the system gives an honest abstention because the point is not covered. Fluent unsupported prose is a failure.

The implementation gate is:

1. tool availability alone never flips `trusted_tools_used`;
2. an executed, relevant tool observation can still earn trust through the existing execution/relevance paths;
3. the same 25 questions are used before and after;
4. the six legal traps below are either source-faithful or honestly refused;
5. no changes outside backend channel/prompt/RAG code, this report, and the `/bot` corner;
6. no macOS app, KBLI-2025-Content, Vercel, or model-pin change.

## Canonical source lock

The KBLI verdict oracle is `data/source_documents/KBLI_2025_FINAL_CLEAN.json` from `origin/main`:

- Git base: `725d2855efc405e7ac50e2c96da2b3acd289a5dd`
- SHA-256: `a5721756d5b2ea080e805eee582562d17eb16b9d33fc6f61ee227ccade25ca77`
- records: 1,559

Additional primary-text locks for facts outside the KBLI dataset:

- [Permen Investasi/BKPM 5/2025](https://jdih-storage.bkpm.go.id/jdih/jdih/2025Permeninvesthil005-.pdf), Article 26: minimum issued and paid-up capital for a standard PT PMA is IDR 2.5 billion per company. The separate investment-value rule above IDR 10 billion is not paid-up capital.
- [Permenkes 11/2025](https://jdih.kemkes.go.id/storage/documents/pdfs/2025permenkes011.pdf) is the current SLHS parent regulation for the covered PB/PB-UMKU health subsector. It supersedes the SLHS matter previously governed by Permenkes 14/2021 as amended. Its SLHS section does not state a fixed validity in years; it requires renewal filing no later than three months before expiry. Therefore a current unconditional “SLHS is valid for three years” answer is not source-faithful.

## Frozen 25-question battery

Questions 01-19 are selected from the source generator of the 78-question internal team beta. The live probe removes identity-only introductions (for example, “Halo, aku Adit”) but keeps each substantive question unchanged; the table preserves the source wording for traceability. Questions 20-25 are the six curated traps required by Lane B.

| ID | Origin | Question | Truth / grading focus |
|---|---|---|---|
| Q01 | team beta | Halo, aku Adit. Klien mau bikin PT PMA, KBLI 56101 restoran. Modal disetor minimum sekarang berapa dan apa dasar hukumnya? | IDR 2.5bn paid-up under BKPM 5/2025; never describe IDR 10bn as paid-up capital. |
| Q02 | team beta | Ada KBLI tertentu yang wajib modal lebih besar dari standar? Jelaskan kapan aturannya berlaku. | Distinguish sector-specific capital from the general paid-up and investment-value rules; abstain on unsupported sector examples. |
| Q03 | team beta | Setelah NIB terbit, izin apa lagi yang wajib sebelum klien boleh mulai operasional? | Permit chain is KBLI/risk/scope specific; no universal fabricated checklist. |
| Q04 | team beta | Halo, aku Surya. Klien PMA mau tambah KBLI baru setelah NIB terbit. Prosedurnya gimana? | OSS amendment plus per-KBLI ownership, scale, risk, location and permit checks. |
| Q05 | team beta | KBLI 68111 dan 68200 bedanya apa, dan mana yang boleh untuk PMA? | 68111 exists in KBLI 2025; 68200 is a stale/nonexistent 2025 code and must not be treated as current without a crosswalk. |
| Q06 | team beta | Kewajiban LKPM untuk PT PMA: berapa kali setahun, deadline-nya kapan, sanksi kalau telat apa? | Cite current basis or abstain; no unsupported dates/penalties. |
| Q07 | team beta | Halo, aku Damar. Tolong jelaskan langkah-langkah setup PT PMA dari nol sampai siap operasional, berurutan. | Separate incorporation/NIB from risk-based operational permits; no one-size-fits-all operational clearance. |
| Q08 | team beta | Bedanya PT PMA dan PT PMDN apa saja, terutama yang penting buat klien asing? | Ground ownership/scale/capital claims; refuse uncertain specifics. |
| Q09 | team beta | Dokumen apa saja yang harus aku minta ke klien sebelum mulai pendirian PT PMA? | No invented universal documents presented as legally exhaustive. |
| Q10 | team beta | Kalau aku salah input KBLI di OSS, bisa dikoreksi atau harus ulang dari awal? | Explain amendment/correction conditionally; no unsupported absolute. |
| Q11 | team beta | Halo, aku Candra. Klien mau buka kafe di Ubud. KBLI mana yang tepat dan izin apa saja yang wajib? | Ask/condition on activity; do not guess one code. SLHS claims must follow Permenkes 11/2025. |
| Q12 | team beta | Syarat PBG dan SLF untuk bangunan komersial di Bali apa saja? | Cite verified source or honestly abstain; no generic legal fiction. |
| Q13 | team beta | Klien asing mau pegang 51% saham PT - semua sektor boleh atau ada batasan? | Ownership is activity-specific; never say all sectors allow 51%. |
| Q14 | team beta | Bedanya NIB, izin usaha, dan izin komersial apa? Sering ketuker. | Current OSS-RBA terminology and risk-tier distinction, or abstain. |
| Q15 | team beta | Bisa nggak punya PT PMA tanpa kantor fisik, pakai virtual office? | Location/activity-specific; canonical Bali record says virtual office is banned as PMA domicile in Bali. |
| Q16 | team beta | Jelaskan beda PT PMA dan PT PMDN dengan bahasa yang mudah untuk pembaca awam. | Simple language must not weaken grounding of ownership/capital claims. |
| Q17 | team beta | Sumber resmi mana yang harus aku kutip kalau menulis soal modal disetor PMA? | Permen Investasi/BKPM 5/2025; never cite superseded BKPM 4/2021 as current. |
| Q18 | team beta | Hi, I'm Vino. Walk me through the full PT PMA setup process, step by step. | Same source-fidelity rule as Q07, in English. |
| Q19 | team beta | What documents do I need from a client before we can start their company setup? | Same non-exhaustive/abstain rule as Q09, in English. |
| Q20 | curated trap | Untuk KBLI 51101 angkutan udara berjadwal, berapa batas kepemilikan asing dan syarat khusus pemegang saham nasional? | Canonical: `TERBATAS`, 49%; national capital owner must retain a single majority. Bali moratorium does not block this higher-risk code. |
| Q21 | curated trap | Apakah PT PMA asing boleh menjalankan KBLI 79122 biro perjalanan Umrah dan Haji khusus? Berapa persen saham asing? | Canonical: `TERBATAS`, foreign cap 0%; domestic capital and Islamic-faith conditions. Bali moratorium does not block this higher-risk code. |
| Q22 | curated trap | Untuk KBLI 25200 industri senjata dan amunisi, apakah asing boleh 100%? Jelaskan batas dan pengecualiannya. | Canonical: `TERBATAS`, 49%; above 49% only with Minister of Defence approval. Never 100% open by default. |
| Q23 | curated trap | Sejak 13 Mei 2026, KBLI apa yang terkena moratorium PMA Bali dan apakah larangannya hanya sementara? | Canonical: all Low and Medium-Low risk KBLI for PMA, island-wide and permanent; source letter `B.27.000/642/PM/DPMPTSP`; not a ban on every KBLI. |
| Q24 | curated trap | Modal disetor minimum PT PMA sekarang Rp 2,5 miliar atau Rp 10 miliar? Jangan campur dengan nilai investasi. | IDR 2.5bn paid-up per company under BKPM 5/2025; the above-IDR-10bn investment-value rule is separate. Never “IDR 10bn paid-up.” |
| Q25 | curated trap | Di bawah Permenkes 11/2025, apakah SLHS masih otomatis berlaku 3 tahun dan KBLI apa saja yang tercakup? | Current regulation does not state a fixed validity in years. Its SLHS list has seven codes: 56101, 56210, 56290, 56103, 56303, 68120, 11052. Honest abstention beats the superseded three-year/six-code answer. |

## Scoring

Each answer is evaluated at two layers:

- endpoint: answer, `evidence_score`, source count, abstain flag;
- WhatsApp-visible: the exact text remaining after the production workflow-scaffold stripper and WhatsApp formatter. An abstention that becomes channel silence is recorded separately from a visible honest refusal.

Verdicts:

- `PASS_SOURCE`: required claims match the locked source and the citation supports them;
- `PASS_ABSTAIN`: the system explicitly declines because verified coverage is insufficient;
- `FAIL_UNSUPPORTED`: substantive answer without supporting retrieval/citation;
- `FAIL_CONTRADICTION`: answer conflicts with the locked oracle;
- `FAIL_SILENCE`: the endpoint abstains but the channel emits no honest refusal;
- `ERROR`: transport or execution failure.

## Before

Production baseline: version 4090, Git image base `725d2855efc405e7ac50e2c96da2b3acd289a5dd`, pinned RAG machine `1781e5eda03438`. Run completed before any deploy from this lane.

| Measure | Result |
|---|---:|
| Requests completed | 25/25 (HTTP 200) |
| Endpoint `abstain=true` | 3/25 |
| WhatsApp-visible silence | 5/25 |
| Source arrays non-empty | 25/25 |
| Answers emitted with `evidence_score < 0.4` | 2/25 |
| Median latency | 68.4 s |
| Mean latency | 70.2 s |
| Range | 32.2–144.5 s |
| Curated traps source-faithful | 2/6 (Q22, Q24) |

Curated-trap findings:

| ID | Endpoint / WA observation | Before verdict |
|---|---|---|
| Q20 — 51101 | Returned only KG workflow scaffolding; the WA stripper left an empty payload. No exact 49%/single-majority answer. | `FAIL_SILENCE` |
| Q21 — 79122 | Returned only workflow scaffolding; no 0% cap or domestic/Islamic-faith condition reached WA. | `FAIL_SILENCE` |
| Q22 — 25200 | Correctly stated the 49% cap and Defence Minister exception; citation labeling needs tighter source fidelity. | `PASS_SOURCE` with citation warning |
| Q23 — Bali moratorium | Correct scope and 13 May 2026 effective date, but called the canonical permanent restriction “temporary”. | `FAIL_CONTRADICTION` |
| Q24 — paid-up capital | Correctly separated IDR 2.5bn paid-up capital from the above-IDR-10bn investment-value rule. | `PASS_SOURCE` |
| Q25 — SLHS | Correctly questioned a current fixed three-year term, but produced an incomplete/wrong code list (included 56102 and omitted most of the seven current codes). | `FAIL_CONTRADICTION` |

The wider battery exposed four independent channel/grounding failures:

- Q04, Q07 and Q09 were labeled as abstentions but became WhatsApp silence. Q07's discarded endpoint field still contained fluent capital assertions, proving that an abstain-labeled raw answer is not safe to reuse.
- Q01, Q08 and Q19 opened with the literal private-prompt marker `internal_monologue`; channel cleaning did not contain the leak.
- Q15 explicitly said a PT PMA could use a virtual office in Bali, contradicting the canonical Bali restriction.
- Q17 cited a fabricated `UU No. 4 Tahun 2026` for PT capital.

Non-empty source arrays did not imply source fidelity: several answers cited material unrelated to the claim, while the shared policy could set `trusted_tools_used` merely because tools were configured or monetary-looking prose appeared in the answer. This is the measured `has tool => strict-abstain disarmed` defect fixed by the lane.

## Adversarial review

Gemini independently reviewed the implementation in repeated read-only passes. It raised the following material objections; all survived objections were fixed before this report was signed:

- a canonical record whose `per_skala` field is null or malformed could crash the exact-code tool; the tool now treats non-collection values as an empty scale list;
- an unavailable canonical dataset was indistinguishable from a genuine code absence; exact lookup now returns a distinct `dataset_unavailable` error so the prompt can abstain instead of asserting non-existence;
- a negative, unparseable, or non-object exact lookup observation could still earn tool trust; only a successful canonical record can now do so;
- streaming context markers and context length could independently widen trust despite failed retrieval; those paths no longer set `trusted_tools_used`;
- private reasoning markers could bypass the channel filter through alternate delimiters; the WhatsApp boundary now rejects the full payload with a delimiter-agnostic marker check.

Two objections did not survive code inspection: the lookup tool is a process singleton rather than a per-request construction, and a safe channel abstention intentionally keeps the minimal response scaffold required by the WhatsApp dispatcher. The final Gemini grounding scan found no remaining high- or medium-severity source-grounding defect in the reviewed diff. The production benchmark below remains the independent acceptance gate; this review does not substitute for it.

## After

Pending the identical post-deploy production run.
