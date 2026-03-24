# Zoho Invoice Integration - Deployment Guide

## Overview

Integrazione completata con Zoho Invoice API per la generazione automatica delle fatture quando lo status di una practice cambia a `quotation_sent`.

## Changes Made

### 1. New Service: `zoho_invoice_service.py`

- **Location**: `backend/services/integrations/zoho_invoice_service.py`
- **Purpose**: Interfaccia con Zoho Invoice API
- **Features**:
  - OAuth token management
  - Contact/Customer creation/retrieval
  - Invoice creation
  - Invoice PDF download
  - Invoice email sending via Zoho

### 2. Updated Service: `invoice_service.py`

- **Location**: `backend/services/invoicing/invoice_service.py`
- **Changes**:
  - Replaced SMTP email with Zoho Invoice API
  - Creates invoice in Zoho first
  - Downloads PDF from Zoho for Drive backup
  - Updates practice with Zoho invoice details

### 3. Updated Exports: `integrations/__init__.py`

- Added `ZohoInvoiceService` to exports

## Pre-Deployment Checklist

### 1. Verify Zoho Credentials

Assicurarsi che i segreti siano configurati su Fly.io:

```bash
fly secrets list --app nuzantara-rag
```

Required secrets:

- `ZOHO_CLIENT_ID`
- `ZOHO_CLIENT_SECRET`
- `ZOHO_REDIRECT_URI`

### 2. Configure Zoho Invoice Organization ID

L'Organization ID deve essere aggiunto ai token OAuth esistenti. Eseguire questo script dopo il deploy:

```python
# Script: update_zoho_org_id.py (run on Fly.io console)
import asyncpg
import os
import json

async def update_tokens():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # Get organization ID from Zoho (manual step first)
    # Login to Zoho Invoice → Settings → Organization Profile → Organization ID
    org_id = "YOUR_ORGANIZATION_ID"

    await conn.execute(
        """
        UPDATE zoho_oauth_tokens
        SET organization_id = $1,
            updated_at = NOW()
        WHERE provider = 'zoho'
        """,
        org_id
    )
    print(f"Updated {conn} tokens with organization_id")
    await conn.close()
```

### 3. Verify OAuth Scopes

Il token Zoho deve avere questi scopes:

- `ZohoInvoice.fullaccess.all`
- `ZohoMail.accounts.READ`
- `ZohoMail.messages.ALL`

Se necessario, rifare l'OAuth flow con gli scopes aggiornati.

### 4. Test Script (Pre-Deploy)

```bash
# SSH into Fly.io machine
fly ssh console --app nuzantara-rag

# Test imports
PYTHONPATH=. python3 -c "
from backend.services.invoicing.invoice_service import InvoiceAutomationService
from backend.services.integrations.zoho_invoice_service import ZohoInvoiceService
print('✓ All imports successful')
"
```

## Deployment Steps

### Step 1: Deploy to Fly.io

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag

# Deploy with rolling strategy
fly deploy --strategy rolling --app nuzantara-rag
```

### Step 2: Verify Deployment

```bash
# Check logs
fly logs --app nuzantara-rag

# Verify health endpoint
curl https://nuzantara-rag.fly.dev/health
```

### Step 3: Test Invoice Creation

1. Create a test practice or use existing one
2. Change status to `quotation_sent`
3. Verify in logs:
   - `Invoice automation triggered for practice X`
   - `Creating Zoho Invoice for practice X`
   - `Zoho Invoice created: INV-XXXX`
   - `Invoice automation completed successfully`

4. Check Zoho Invoice dashboard for the created invoice

## Troubleshooting

### Error: "No valid Zoho OAuth token"

- Verificare che il token esista in `zoho_oauth_tokens` table
- Verificare che il token non sia scaduto
- Rifare l'OAuth flow se necessario

### Error: "Zoho organization ID not configured"

- Aggiungere `organization_id` al token nel database
- Vedere sezione "Configure Zoho Invoice Organization ID"

### Error: "403 Forbidden" from Zoho API

- Verificare che lo scope `ZohoInvoice.fullaccess.all` sia presente
- Verificare che l'app Zoho abbia permessi per Invoice API

### Error: "Contact email required"

- Il client deve avere un'email valida
- L'email è obbligatoria per creare il contatto in Zoho

## Rollback Plan

Se necessario, fare rollback alla versione precedente:

```bash
# List previous releases
fly releases list --app nuzantara-rag

# Rollback to specific version
fly deploy --image nuzantara-rag:<previous_image> --app nuzantara-rag
```

## Post-Deployment Monitoring

Monitorare questi log pattern:

- `Invoice automation triggered` - workflow started
- `Zoho Invoice created` - invoice created successfully
- `Failed to create Zoho Invoice` - errors
- `Invoice automation completed` - workflow completed

## Next Steps (Future Enhancements)

1. **Payment Tracking**: Implementare webhook da Zoho per aggiornare `payment_status`
2. **Invoice Templates**: Personalizzare template fatture in Zoho
3. **Multi-Currency**: Supportare fatture in USD/EUR/IDR
4. **Recurring Invoices**: Per servizi subscription-based
