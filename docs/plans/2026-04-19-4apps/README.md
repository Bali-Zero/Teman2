# Build Plans — 4 App homepage (2026-04-19)

**Context:** `docs/cro/2026-04-19-funnel-audit.md` + `docs/cro/2026-04-19-4-app-engagement-conversion.md`

Shippare 4 app che rimpiazzano le 4 decorative FunnelFeature sections della home v2. Ognuna è costruita sullo stesso pattern (input minimale → output personalizzato → URL condivisibile → CTA WhatsApp precompilato), ma ha flow/CTA diversi per il segmento che serve.

## Ordine di ship

1. **Shared infrastructure** (`00`) — prerequisito per tutte, da fare prima
2. **Zoning Check** (`04`) — più veloce, infra PostGIS già pronta
3. **Visa Check** (`01`) — 2 rami (Clock + Match), copre il 100% del traffico visa
4. **KBLI Check** (`02`) — 2 rami (Decoder + Builder), copre PMA esistenti + PMA nuove
5. **Tax Gap** (`03`) — il più delicato (privacy + OCR), ultimo

## Decisioni architetturali chiave

- **Ogni app a 2 rami quando il segmento è naturalmente binario** (Clock/Match, Decoder/Builder) invece di esclude metà del traffico
- **Nessun prezzo inventato** — tutti i prezzi letti da `PricingTool` (CLAUDE.md Golden Rule #12)
- **Tax Gap: free 30-min call come CTA** (il vero prodotto è tax outsourcing ongoing, non la review)
- **Zoning Check: 3 CTA contestuali** (OK / LP2B / fuori coverage) invece di CTA unico
- **Shared infra prima** — CRM handoff, WhatsApp deeplink, analytics, email Brevo: un solo SSOT per le 4 app

## File

| File | App | Rami | Status |
|------|-----|------|--------|
| `00-shared-infrastructure.md` | Infra condivisa | — | PLAN |
| `01-visa-check.md` | Visa Check | Clock + Match | PLAN |
| `02-kbli-check.md` | KBLI Check | Decoder + Builder | PLAN |
| `03-tax-gap.md` | Tax Gap | — (single flow con 2 upload path) | PLAN |
| `04-zoning-check.md` | Zoning Check | — (3 CTA contestuali) | PLAN |

Ogni file contiene: user flow, API contract, schema migration, CTA design, acceptance criteria, killer risk + mitigazione, post-ship telemetry.
