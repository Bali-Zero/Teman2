# CRM Global Fix — Design Spec

_Date: 2026-03-26_

## Summary

Intervento globale su `kita.balizero.com/clients` per risolvere 67 issue identificati tramite screening completo con agenti paralleli. Diviso in due round sequenziali.

## Round 1 — Security (backend)

### Problemi

1. `/extract-passport-enhanced`: nessun RBAC — qualsiasi admin può modificare dati di qualsiasi cliente
2. `/extract-npwp`: `client_id` accettato ma ignorato — no access control, dati non salvati
3. `/extract-nib`: stesso problema di `/extract-npwp`
4. Tutti e 3 gli endpoint OCR: nessuna validazione del base64 prima del decode

### Fix

- Aggiungere `verify_client_access(client_id, current_user)` su tutti e 3
- `/extract-npwp`: salvare NPWP estratto su `clients.npwp`
- `/extract-nib`: salvare NIB estratto su `clients.nib`
- Validare che `image_base64` sia base64 valido prima del decode
- Verifica con pytest (292 test) + red team Gemini su tutto il file

## Round 2 — UX/Bug (frontend + backend, sequenziale)

### Ordine di intervento (impatto decrescente)

1. `new/page.tsx` — avatar upload disabled (feature broken silente)
2. `AddCompanyModal.tsx` — extractNpwp/extractNib non awaited + upload silente
3. `VisaCard.tsx` — OCR catch vuoto
4. `PassportCard.tsx` — OCR silenzioso, no retry
5. `EditClientModal.tsx` — date_of_birth null crash
6. `CompanyTab.tsx` — catch vuoti, any casts
7. `FamilyTab.tsx` — catch vuoti, onRefresh non guardato
8. `TaxTab.tsx` — catch vuoti, loading state upload
9. `ImmigrationTab.tsx` — rollback ottimistico su delete failure
10. `crm_clients.py stats` — N+1 → GROUP BY
11. `crm_clients.py required-docs` — N+1 → JOIN
12. `page.tsx` — getUserProfile non awaited, null check assigneesData
13. `useCrmClients.ts` — refetch non awaited, errori non propagati
14. `crm.api.ts` — timeout su read ops, validazione response

## Verifica per ogni step

- Backend: `PYTHONPATH=. pytest backend/tests/ -k "crm or client" -v`
- Frontend: `cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "(clients|crm)"`
- Deploy finale: `fly deploy --strategy rolling` + `git push origin main`
