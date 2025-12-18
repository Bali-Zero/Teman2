# Playbook UX Conversazionale (fluida, elegante, “Ultra”)

Questa webapp è già ben impostata (streaming, step/status, fonti, micro‑animazioni). Qui sotto trovi i “trucchi” che, nei migliori prodotti AI al mondo, fanno la differenza tra “chat ok” e “esperienza travolgente”.

## 1) Streaming che *sembra* premium

- **Streaming robusto**: nessuna perdita token/eventi (parser SSE con buffering).
- **Progressive disclosure**: mostra “Thinking / Tool / Searching” senza mostrare reasoning interno.
- **Citations progressive**: prima la risposta, poi “evidence pack” che si popola (fonti e snippet).
- **Controlli utente**: `Stop`, `Retry`, `Retry with Deep Think`, `Copy`, `Share`.

## 2) Micro‑interazioni che aumentano fiducia

- **Typing indicator intelligente**: cambia testo in base allo stato (“Searching visa_oracle…”, “Checking pricing…”, “Composing answer…”).
- **Tool chips**: quando parte un tool, mostra pill “Running vector_search” (già presente), ma con outcome (“Found 5 sources”).
- **Error UX**: messaggi chiari per quota/timeouts con un’azione: “Riprova in Fast / Precision”.

## 3) Risposte leggibili (percepita > modello)

- **Formati fissi per dominio**:
  - Visa/Legal: checklist + requisiti + tempi + rischi + next steps
  - Tax: tabella aliquote + esempi + note + fonti
  - CRM: “summary + next best actions”
- **Sezione finale standard**: “Next steps” + “I need from you” + “Sources”.
- **Auto‑followup**: 3 suggerimenti mirati (non generici) basati su intent/routing.

## 4) “Precision Mode” senza confondere l’utente

- Toggle: **Fast ↔ Precision** (con microcopy: “più lento, più accurato, più citazioni”).
- Dopo una risposta: CTA “Non ti convince? Prova Deep Think”.
- Mostra badge del tier (Fast/Pro/Deep Think) + latenza stimata.

## 5) Memory & continuity (wow factor)

- “Conversation title” auto‑generato (e modificabile).
- “Recap” automatico dopo N turni (“What we decided so far”).
- “Pinned facts” (memoria fattuale con consenso): preferenze lingua, dati azienda, scadenze.

## 6) Eleganza UI (senza diventare gimmick)

- Motion: transizioni brevi e coerenti (150–250ms), no jitter.
- Layout: max width costante, spacing generoso, contrasto alto.
- Citazioni: pill compatte + espansione dettagli (già presente) + link/ID documento quando disponibile.

