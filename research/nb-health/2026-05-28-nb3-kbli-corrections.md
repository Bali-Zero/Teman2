---
date: 2026-05-28
domain: nb-health
notebook: NB-3 Company Setup Indonesia
notebook_uuid: 933509f9-1561-403d-bd44-4a7a67a36df2
type: correction-report
severity: P2
discovered_by: deep-researcher (primary-source verification, Peraturan BPS 7/2025 PDF 623pp letto direttamente)
trigger: Antonello challenge "hanno cercato nel KBLI 2025? e la legge BPS di dicembre 2025?"
sources:
  - research/company/2026-05-28-kbli-2025-bps-december-verify.md
  - research/visa/2026-05-28-e33g-kbli-content-creator-pivot.md
  - "PRIMARY: Peraturan BPS No. 7 Tahun 2025 (KBLI 2025, 623pp, letto direttamente)"
---

# NB-3 — Segnalazione imprecisioni KBLI 2025 (2 errori + 1 nota)

Discovered durante verifica fonte primaria del KBLI 2025 per il pivot carosello content creator. NB-3 (Company Setup Indonesia) ground-truth ha 2 imprecisioni materiali + 1 nota di contesto. Nessuna è "bugia": NB-3 cita documenti reali, ma datati/versionati male.

**Decisione su correzione → operatore (Antonello). Questa è una segnalazione, non un auto-edit di NB.** Symbiosis Law 2 (OSINT/NB curati) + Law 5 (Zero decide su strutturale).

---

## ERRORE 1 (P2) — Codice 74149 "Desain Konten Kreatif Lainnya" attribuito a KBLI 2025

**NB-3 source_id `4f7bfcb6`** presenta `74149 — Aktivitas Desain Konten Kreatif Lainnya` citando un Lampiran "PRESIDEN REPUBLIK INDONESIA" (74141/74142/74149) come se fosse KBLI 2025.

**Realtà (verificata sul PDF Peraturan BPS 7/2025, grep esaustivo)**:

- `74149` → **0 match** nel testo KBLI 2025. È un codice **KBLI 2020**.
- Subgruppo 7419 del KBLI 2025 = `74191` (interior) / `74192` (grafis) / `74193` (desain khusus film-video-TV) / `74194` (desain konten gim, NUOVO) / `74199` (desain khusus lainnya YTDL).
- Il 74149 del 2020 è stato assorbito (verso 74199 YTDL).

**Causa radice**: NB-3 ha conflato la **matrice rischio OSS-RBA / Lampiran Perpres** (numerazione KBLI 2020) con il testo BPS KBLI 2025. Il documento citato è reale ma è un Lampiran Perpres su base KBLI 2020, non il Peraturan BPS 7/2025.

**Correzione proposta**: rimuovere 74149 come "codice nuovo/granulare KBLI 2025". Aggiungere nota: "74149 = KBLI 2020; in KBLI 2025 i codici design content sono 74194 (Desain Konten Gim) + 74199 (YTDL). I veri codici creator 2025 sono 59112/60103/60203/60390/90113/90200."

---

## ERRORE 2 (P2) — Tempistica OSS / KBLI 2025 "già mandatorio"

**NB-3 source_id `bbf21201`** afferma che OSS è già obbligato a usare KBLI 2025 a maggio 2026 ("31 mag 2026 full migration OSS RBA 1.2 + KBLI 2025").

**Realtà (WebSearch tier-2 convergente + Pasal 5 primaria + Permen BKPM 5/2025 Pasal 393)**:

- Al 28 maggio 2026 **OSS opera ANCORA su KBLI 2020**.
- KBLI 2020 e 2025 girano in **PARALLELO** durante la transizione.
- Cutoff legale conversione automatica: **18 giugno 2026** (Pasal 5 BPS 7/2025 = 6 mesi da promulgazione 18 dic 2025).
- Conversione AUTOMATICA lato-sistema (Permen BKPM 5/2025 Pasal 393), non a carico del cliente.

**Impatto pratico**: una PT PMA aperta a maggio/giugno 2026 si registra con codici KBLI **2020**, convertiti automaticamente dopo. Affermare "KBLI 2025 già mandatorio" rischia di far selezionare codici non ancora accettati da OSS.

**Correzione proposta**: aggiornare la entry a "coesistenza parallela KBLI 2020/2025 fino al 18 giu 2026; OSS registra ancora con KBLI 2020 a maggio 2026; conversione automatica lato-sistema". Mantenere il flag di verifica empirica OSS al momento del deposito akta.

---

## CONFERMATO (NB-3 corretto) — 73100 Periklanan PMA 49%

**NB-3 source_id `4539bbfb`**: _"73100 — AKTIVITAS PERIKLANAN PMA: TERBATAS (max 49% WNA) — cond: Kemitraan dengan badan usaha dalam negeri"_ + nota errore comune (confusione con rilascio iniziale Perpres 10/2021).

**Verificato CORRETTO**: il cap 49% deriva dalla Daftar Positif Investasi (Perpres 10/2021 jo 49/2021 jo 14/2024), àncora alla descrizione/numero KBLI (73100 invariato 2020→2025). NB-3 aveva ragione contro Gemini (che citava Perpres 10/2021 superata). **Nessuna correzione — anzi NB-3 ha già la nota anti-errore giusta.**

---

## Riepilogo per la curation

| #   | NB-3 source_id | Tipo                                 | Azione                                    |
| --- | -------------- | ------------------------------------ | ----------------------------------------- |
| 1   | `4f7bfcb6`     | ERRORE (74149 = KBLI 2020, non 2025) | Correggere/rimuovere                      |
| 2   | `bbf21201`     | ERRORE (OSS già su 2025)             | Aggiornare a coesistenza fino 18 giu 2026 |
| 3   | `4539bbfb`     | CORRETTO (73100 = 49%)               | Nessuna azione — conferma                 |

**Fonte data per aggiungere a NB-3 se l'operatore approva**: Peraturan BPS No. 7 Tahun 2025 (KBLI 2025, ISIC Rev. 5, 17 dic 2025, transizione 18 giu 2026). Codici creator 2025: 59112 (vlog/podcast verbatim), 60103/60203 (streaming), 60390 (social), 90113 (jurnalis independen), 90200 (influencer-as-talent), 74194 (gim).

**Pattern meta**: NB-3 cita documenti reali ma con versione/data sbagliata (Lampiran Perpres 2020 spacciato per KBLI 2025; tempistica OSS ottimistica). Il rischio NB non è hallucination ma **version-drift su normativa che cambia** — il KBLI è passato da 2020 a 2025 a dicembre e NB-3 non ha catturato la transizione. Suggerimento per nb-curator: flag delle entry KBLI come "version-sensitive — verify against latest BPS Peraturan".
