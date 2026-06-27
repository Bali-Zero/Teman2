---
date: 2026-06-19
domain: compliance
client_case: none
status: DEMO — prova viva schema-v2 su 1 KBLI (villa 55203)
---

# KBLI 55203 (Villa) — prima e dopo lo schema-v2

## PRIMA (nostro vecchio KBLI_2025_FINAL_CLEAN)
- judul: "Aktivitas Vila" · pma_status: TERBUKA 100% · intel_2026 (LLM-inventato: prezzi/location Bali)
- **Nessun dato sui divieti Bali.** Un cliente avrebbe letto "aperto 100%" e basta.

## DOPO (schema-v2, 5 strati con provenance)
- **L0 (OSS truth, HIGH)**: Aktivitas Vila + ruang_lingkup ["Seluruh"]
- **L1 (normalized)**: title_en separato (NON impastato nel judul) · hierarchy 55→552→5520→55203
- **L2 (compliance NAZIONALE, HIGH)**: PMA TERBUKA 100% [Perpres 10/2021,49/2021,14/2024]
- **L4 (Bali, NUOVO)**: **BLOCCATO_CLASSE_RISCHIO** — low/medium-low risk → moratoria 13/5/26 blocca PMA Bali
- **L3 (editoriale, LOW)**: legacy intel_2026 (da re-gate)

## Il valore in una frase
**Prima: "villa = aperta 100%".  Dopo: "aperta 100% in Indonesia MA bloccata per PMA a Bali".**
La verità doppia (L2 nazionale vs L4 locale) è ciò che evita a un cliente di comprare un sogno irrealizzabile.

## 2 item di qualità residua (NON bug — onesti, per il prossimo giro)
1. **title_en spesso = judul_id** (l'OSS non traduce davvero). L1 ha il campo separato ma serve un
   enrichment-traduzione EN reale (job L1, ~1559 traduzioni, deterministico+gate).
2. **504 codici legacy intel_2026** non sono fact-gated (LLM-inventati pre-grounding, incl. 55203).
   Per coerenza totale: rigenerarli col fact-gate (504 chiamate DeepSeek non-PII, pre-autorizzato ma
   volume → conferma Zero). Finché non fatto, restano marcati LOW/da-re-gate (onesto, non pericoloso).
