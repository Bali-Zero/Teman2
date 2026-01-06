# Deploy Note - Knowledge Base Download Fix

## Problema Risolto
- **Rimosso fallback a Google Drive** nella pagina blueprints
- **Aggiunto logging** per download
- **Aggiunto alert** quando PDF non disponibile (invece di redirect a Google Drive)

## File Modificati
1. `apps/mouth/src/app/(workspace)/knowledge/blueprints/page.tsx`
   - Rimosso `window.open(driveFolder, '_blank')` 
   - Aggiunto `logger` import e logging
   - Aggiunto alert user-friendly quando PDF non disponibile

2. `apps/mouth/e2e/knowledge/downloads.spec.ts` (nuovo)
   - 5 test E2E per verificare download senza Google Drive

## Deploy Comando

```bash
cd apps/mouth
flyctl deploy --remote-only --app nuzantara-mouth
```

## Problema Connettività
Al momento c'è un problema di connettività HTTPS con Fly.io API:
- Errore: `connection reset by peer`
- Ping funziona, ma HTTPS viene interrotto
- Potrebbe essere problema di rete/firewall temporaneo

## Soluzione
1. **Riprova più tardi** quando la connettività è ripristinata
2. **Prova da un'altra rete** (VPN, hotspot mobile)
3. **Verifica firewall/proxy** locale che potrebbe bloccare HTTPS a Fly.io

## Verifica Post-Deploy
```bash
# Verifica che l'app sia online
flyctl status --app nuzantara-mouth

# Verifica logs
flyctl logs --app nuzantara-mouth | grep -i "knowledge\|blueprint"

# Test manuale
# 1. Vai a https://nuzantara-mouth.fly.dev/knowledge/blueprints
# 2. Clicca su un bottone download
# 3. Verifica che NON ci sia redirect a Google Drive
```

