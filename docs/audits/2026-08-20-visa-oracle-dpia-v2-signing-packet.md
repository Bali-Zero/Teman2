# DPIA V2 — pacchetto di firma (§8)

Un solo schermo. Documento completo: `docs/audits/2026-08-20-visa-oracle-dpia-v2.md` §8.

## Cosa impegna la firma del §8

Firmare **non** accende Visa Oracle in produzione (`ENFORCE` resta un'autorizzazione
separata, gated sui volumi G-a/G-b/G-c/G-d). Firmare **approva la valutazione
privacy** e in particolare la ruling §A (retention analytics/telemetria = **12 mesi**,
365 giorni, invece dei 90 provvisori) — e **accetta i rischi residui** ancora aperti
in tabella §D:

- **Alto — invariato**: i log/analytics grezzi possono ancora far trapelare fatti,
  perché la destinazione dietro `NEXT_PUBLIC_ANALYTICS_ENDPOINT` non è ancora
  identificata (nessuna attestazione di cancellazione è quindi possibile).
- **Alto — invariato**: il registro processor/subprocessor cross-border (Annex 1) ha
  righe ancora `OPEN`/`UNKNOWN` (contratti, basi di trasferimento, entità).
- **Medio**: la scheda minori-senza-tutore (`review.minor-without-guardian`) ha un
  difetto di sourcing noto ma fail-safe (forza review, non lascia passare); la
  prova umana a due persone per DSR (ID sbagliato / hold attivo / record assente)
  manca ancora; il rischio "raccomandazione non supportata" resta strutturale,
  limitato dal motore deterministico, non da carta firmata.

## I tre campi

| Campo              | Valore                              |
| ------------------ | ----------------------------------- |
| Entità controllore | **PT Bali Nol Impresariat**         |
| DPO                | **Zainal Abidin**                   |
| Data               | **\____** (da compilare alla firma) |

## Cosa si sblocca alla firma

- La PR di questo pacchetto (PR #4593) — che porta il TTL delle attestazioni
  analytics da 90 a 365 giorni in runbook + preflight, con test guilt+innocence —
  può essere mergiata. **Fino alla firma resta armata ma non mergiata.**
- Ciò chiude SOLO il gate privacy-impact del §8. Non tocca l'`ENFORCE` gate.

## Cosa resta bloccato comunque

- **La destinazione analytics** dietro `NEXT_PUBLIC_ANALYTICS_ENDPOINT` è ancora da
  identificare — voce separata, non risolta da questa firma.
- **`VISA_ENGINE_EVALUATE_MODE=ENFORCE`** resta un'autorizzazione esplicita
  successiva, distinta da questa firma.
- **Incident contacts** nell'header del DPIA restano `OPEN` — servono comunque da
  Zero prima che l'approvazione sia completa in tutti i suoi campi.

## Dove firmare

`docs/audits/2026-08-20-visa-oracle-dpia-v2.md` → sezione **`## 8. Decision and
signatures`** (fondo del documento, dopo la tabella §D e la lista §E).
