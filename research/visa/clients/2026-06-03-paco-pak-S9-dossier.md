---
date: 2026-06-03
domain: property
session: ONDA-3 S9 client-case-dossier
client_case: paco-pak-seseh-shophouse-lease
status: DRAFT — NEEDS-ANTONELLO (legal-service quote = "Contact for quote" in listino; HIGH cures unresolved)
pricing_source: bali_zero_official_prices_2026.json (version 2026.1) via PricingTool source-of-truth
devils_advocate: PASS (Codex read-only adversarial pass + DeepSeek v4-pro math verification)
eligibility_source: research/property/paco-pak-due-diligence-2026-05-22.html (DD memo) + research/property/2026-06-02-foreign-property-rights-hak-pakai-hgb-leasehold.md (S6 NB-5 ground truth)
math_verification: DeepSeek v4-pro (model verified, NOT reasoner alias) — lease escalation 2-scenario
author: S9 orchestrator (Claude Opus 4.8)
---

# Dossier cliente — Paco Pak / Seseh Shophouse Lease

> **STATUS: BOZZA — NON SEND-READY.** Verdetto DD esistente = "Hold / cure first" (4 rischi HIGH aperti). Il costo del servizio legale Bali Zero per questo caso e' "Depend (Contact for quote)" nel listino 2026 → quote NON auto-generabile, marcata NEEDS-ANTONELLO. La due diligence sottostante e' completa.

## 1. Profilo cliente / oggetto

- **Cliente**: Paco Pak (tenant nel draft: Michele Cangiano)
- **Oggetto**: lease 10 anni (1 apr 2026 – 31 mar 2036) di 2 unita shophouse + ~60 m2 terreno retrostante
- **Localita**: Jalan Raya Seseh, Munggu, Mengwi, Badung
- **Titolo**: Hak Milik No. 22030509.1.03453, NIB 22030509.02627, area 935 m2, owner **Pura Puseh Desa Adat Munggu**
- **Firmatario First Party**: I Made Suwinda, S.Pd. (NON l'owner BPN)
- **Rent base**: IDR 260.000.000/anno (240M shophouse + 20M terreno), +7% escalation, totale tabella contratto IDR 2.943.156.000

## 2. Eligibility / struttura legale (ground-truth S6 NB-5 + DD memo)

Questo e' un **leasehold (Hak Sewa, PP 44/1994)** — la struttura piu accessibile per WNA (solo passaporto, no KITAS, no BPN, no soglia investimento) ma anche **la piu rischiosa** (protezione = solo il contratto notarile PPAT, nessuna registrazione BPN).

| Aspetto | Stato | Ground-truth |
|---|---|---|
| WNA puo prendere leasehold commerciale | Si | S6: Hak Sewa, qualsiasi WNA, uso commerciale se da contratto |
| Durata 10 anni | OK | Sotto i 30 anni → nessun rifiuto PPAT atteso |
| Uso commerciale (shophouse) | **A RISCHIO** | BPN dice "sawah"; RDTR appare zona agricola/food-crop |
| Autorita a concedere il lease | **A RISCHIO** | Owner BPN = Pura/Desa Adat; firmatario = individuo |

**Vincolo zoning critico (S6 NB-5)**: costruire/operare strutture commerciali in **Zona Pertanian (P1 sawah / P2)** = divieto assoluto, demolizione forzata + pidana (Perda Bali 4/2026 criminalizza conversione sawah→commerciale, protegge subak UNESCO). Precedente: 21 lug 2025 demolizioni Bingin Beach. Il caso Paco Pak tocca esattamente questo rischio (BPN "sebidang tanah sawah").

## 3. Risk register (dalla DD memo — 4 HIGH bloccanti)

| Rischio | Finding | Cura richiesta |
|---|---|---|
| **HIGH — Owner/signatory mismatch** | BPN owner = Pura Puseh Desa Adat Munggu; firma = I Made Suwinda | Catena autorita formale: delibera Pura/Desa Adat, lettera nomina, procura, KTP/NPWP, conferma PPAT che il firmatario puo concedere lease commerciale 10 anni |
| **HIGH — Zoning/use uncertainty** | BPN "sawah"; RDTR appare agricolo/food-crop | KRK/PKKPR/RDTR ufficiale per NIB/NOP esatto + conferma scritta uso commerciale ammesso (DPMPTSP/PUPR Badung) |
| **HIGH — Building legality missing** | Nessun PBG/IMB, SLF, dettaglio tassa edilizia | Richiedere PBG/IMB, SLF, as-built, approvazione uso/funzione, permessi ristrutturazione |
| **HIGH — Lease object not tied to title** | Lease cita 2 unita + 60 m2 ma non allega plot plan rilevato dentro i 935 m2 | Allegare site plan firmato con confini, misure, accesso, parcheggio, utilities, allocazione terreno retrostante |
| MEDIUM — Payment schedule ambiguity | "7% increase" ambiguo (annuale vs block) | Riscrivere Art. 3 con tabella datata, periodo esatto, late fee, trattamento fiscale |
| MEDIUM — Template blanks / dispute forum | Dati parti + Tribunale incompleti nel template | Completare identita parti, indirizzi, lingua, foro |
| MEDIUM — Assignment/sublease restriction | Art. 5 vieta cessione/sublease senza consenso scritto | Aggiungere clausola cessione controllata |
| MEDIUM — No operational rights detail | Solo "lawful business use" | Aggiungere permitted-use schedule + obblighi cooperazione licenze |

## 4. Math — verifica escalation (DeepSeek v4-pro, modello verificato)

Discrepanza Art. 3 quantificata. Base IDR 260M/anno, 10 anni, "7% increase":

- **Scenario A (7% compound annuale)**: IDR 260M × (1.07^10 − 1)/0.07 = **IDR 3.592.276.470**
- **Scenario B (7% per payment-block, come da tabella contratto)**: 260M + 3×278.2M + 3×297.674M + 3×318.511M = **IDR 2.943.155.000** (contratto dichiara 2.943.156.000 — delta 1.000 IDR arrotondamento)
- **Differenza A − B**: **IDR 649.121.470**

Sanity check manuale orchestratore: 1.07^10 ≈ 1.9672, fattore geom ≈ 13.817, ×260M ≈ 3.592 mld → concorda con DeepSeek. La tabella contratto segue lo Scenario B (block-based). **Il contratto e' aritmeticamente coerente sotto interpretazione block**, ma la clausola va resa esplicita per evitare contestazione downstream (potenziale esposizione +649M se un tribunale leggesse "annuale").

## 5. Cost — PricingTool (Bali Zero Official Prices 2026)

> Da `bali_zero_official_prices_2026.json`. NESSUN prezzo inventato.

| Voce listino | Prezzo (IDR) | Nota |
|---|---|---|
| **Legal Real Estate / lease DD** | listino company_services: "Akta Perubahan" e simili **"Depend (Contact for quote)"** | Il servizio legale/DD su misura NON ha prezzo fisso a listino → quote richiede input Bali Zero |
| Voci ancillari potenzialmente rilevanti (se il cliente procede) | — | NPWPD Registration 2.500.000; NPWP Personal + Coretax 1.000.000 (se Paco apre struttura fiscale locale) |

**Cost status: NEEDS-ANTONELLO.** Il listino 2026 NON contiene un prezzo fisso per la due-diligence/contract-review immobiliare su misura ("Contact for quote"). Coerente con la prassi: la DD legale e' a preventivo. NON invento una cifra (sarebbe esattamente lo STRUCT-1 / lo "[OPINIONE - SPECULATIVE pricing]" che il caso C5A mostra come anti-pattern).

## 6. Timeline

- **Pre-firma (cure)**: 4 HIGH da risolvere con documenti originali + conferma PPAT/legale. Tempi dipendono da reattivita Pura/Desa Adat + DPMPTSP/PUPR Badung (zoning KRK/PKKPR puo richiedere settimane).
- **Istruzione immediata (dalla DD memo)**: NESSUN pagamento del deposito IDR 5.000.000, NESSUNA firma, NESSUNA ristrutturazione, NESSUN lancio pubblico finche i HIGH non sono curati con documenti originali.

## 7. Deliverable

- Questo dossier (`research/visa/clients/2026-06-03-paco-pak-S9-dossier.md`).
- DD memo brand A4 gia esistente: `research/property/paco-pak-due-diligence-2026-05-22.html`.
- Cure-list (4 HIGH + 4 MEDIUM) sopra = checklist operativa per l'account exec.

## Devils-Advocate (gate pre-output)

Verdetto: **PASS**. Codex read-only adversarial + DeepSeek math + auto-critica. Controlli: (1) zoning sawah→commerciale correttamente flaggato come potenziale pidana (Perda Bali 4/2026); (2) struttura leasehold/Hak Sewa correttamente identificata (NON Hak Milik nominee — owner e' Desa Adat, non un nominee straniero); (3) math escalation verificato 2-scenario, delta 649M coerente con DD memo; (4) cost NON inventato — marcato "Contact for quote" come da listino reale; (5) nessun KBLI allucinato. Residuo legittimo: caso intrinsecamente "Hold/cure" — il dossier riflette lo stato reale, non un difetto del dossier.
