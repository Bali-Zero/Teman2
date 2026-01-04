# Email Configuration - balizero.com

## Overview

Configurazione email per il dominio `balizero.com` tramite Zoho Mail con DNS su Cloudflare.

**Data configurazione:** 2026-01-04

## Status Protocolli Email

| Protocollo | Status | Descrizione |
|------------|--------|-------------|
| **MX** | ✅ Configurato | Record MX per Zoho Mail |
| **SPF** | ✅ Configurato | Sender Policy Framework |
| **DKIM** | ✅ Configurato | DomainKeys Identified Mail |
| **DMARC** | ✅ Configurato | Domain-based Message Authentication |
| **BIMI** | ⏸️ Non configurato | Brand Indicators (opzionale) |

## Dettagli Configurazione

### SPF Record
```
v=spf1 include:_spf.google.com include:zohomail.com ~all
```
- Autorizza Google e Zoho a inviare email per conto del dominio
- `~all` = soft fail per altri server

### DKIM Record
- **Selector:** `default`
- **TXT Name:** `default._domainkey.balizero.com`
- **Status:** Verified
- Configurato automaticamente tramite integrazione Zoho-Cloudflare

### DMARC Record
- **TXT Name:** `_dmarc.balizero.com`
- **Value:**
```
v=DMARC1; p=none; rua=mailto:zero@balizero.com; ruf=mailto:zero@balizero.com; sp=none; adkim=r; aspf=r
```

| Parametro | Valore | Descrizione |
|-----------|--------|-------------|
| `p` | none | Policy: monitor only (no action) |
| `rua` | zero@balizero.com | Aggregate reports recipient |
| `ruf` | zero@balizero.com | Forensic reports recipient |
| `sp` | none | Subdomain policy |
| `adkim` | r | DKIM alignment: relaxed |
| `aspf` | r | SPF alignment: relaxed |

### BIMI (Non Configurato)
Requisiti per configurazione futura:
1. Logo SVG in formato Tiny P/S
2. Certificato VMC (Verified Mark Certificate) ~$1000-1500/anno
3. DMARC policy `p=quarantine` o `p=reject`

## Provider

- **Email Provider:** Zoho Mail
- **DNS Provider:** Cloudflare
- **Admin Console:** https://mailadmin.zoho.com

## Raccomandazioni Future

1. **Monitorare report DMARC** inviati a `zero@balizero.com`
2. **Upgrade DMARC policy** dopo periodo di monitoraggio:
   - `p=none` → `p=quarantine` → `p=reject`
3. **Considerare BIMI** per branding (quando budget disponibile)

## Riferimenti

- [Zoho DKIM Configuration](https://www.zoho.com/mail/help/adminconsole/dkim-configuration.html)
- [Zoho DMARC Policy](https://www.zoho.com/mail/help/adminconsole/dmarc-policy.html)
- [Cloudflare DNS](https://dash.cloudflare.com)
