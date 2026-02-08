# CloudFlare Implementation Plan - Nuzantara

**Created:** 2026-02-08  
**Status:** Planning Phase  
**Priority:** High

---

## 🎯 Obiettivi

1. **Protezione DDoS** per frontend e backend
2. **CDN Global** per asset statici
3. **SSL/TLS** ottimizzato
4. **Caching** intelligente
5. **WebSocket** support for real-time features

---

## 📋 Checklist Configurazione

### Fase 1: Setup Iniziale

- [ ] Verificare/Aggiungere dominio in CloudFlare Dashboard
- [ ] Aggiornare nameservers
- [ ] Verificare propagazione DNS
- [ ] Configurare SSL/TLS (Full Strict)

### Fase 2: DNS Configuration

#### Per Frontend (Vercel)
```
Type: CNAME
Name: @
Target: cname.vercel-dns.com
Proxy: Proxied (🟠)
TTL: Auto
```

#### Per Backend (Fly.io)
```
Type: CNAME  
Name: api
Target: nuzantara-rag.fly.dev
Proxy: Proxied (🟠)
TTL: Auto
```

### Fase 3: SSL/TLS Settings

```yaml
SSL/TLS Mode: Full (strict)
Always Use HTTPS: ON
Automatic HTTPS Rewrites: ON
Minimum TLS Version: 1.2
Opportunistic Encryption: ON
TLS 1.3: ON
```

### Fase 4: Speed Optimization

```yaml
Auto Minify: CSS, JS, HTML
Brotli: ON
HTTP/2: ON
HTTP/3 (QUIC): ON
0-RTT: ON
Rocket Loader: OFF (React compatibility)
```

### Fase 5: Page Rules (Priorità)

| Priority | URL Pattern | Settings |
|----------|-------------|----------|
| 1 | `*balizero.com/_next/static/*` | Cache Everything, 1 month TTL |
| 2 | `*balizero.com/api/*` | Bypass Cache |
| 3 | `*balizero.com/ws/*` | Bypass Cache |
| 4 | `*balizero.com/health` | Bypass Cache |

### Fase 6: Security

```yaml
WAF: ON (Managed Ruleset)
OWASP Core Ruleset: ON
Bot Fight Mode: ON
DDoS Protection: ON (High sensitivity)
Security Level: Medium
Challenge TTL: 30 minutes
```

### Fase 7: Network

```yaml
HTTP/2: ON
HTTP/3: ON
0-RTT: ON
WebSockets: ON
IP Geolocation: ON
Maximum Upload Size: 100MB
Response Buffering: OFF (for streaming)
```

---

## 🔧 Configurazione Specifica per Nuzantara

### 1. Frontend (Next.js su Vercel)

```javascript
// next.config.ts - Aggiungere headers per CloudFlare
const nextConfig = {
  async headers() {
    return [
      {
        source: '/_next/static/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },
};
```

### 2. Backend (FastAPI su Fly.io)

```python
# middleware per trusted proxy (CloudFlare)
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["balizero.com", "api.balizero.com", "*.fly.dev"]
)
```

### 3. WebSocket Configuration

CloudFlare supporta WebSocket su tutti i piani:
- Automatico su proxied records
- Nessuna configurazione aggiuntiva necessaria

---

## 🧪 Testing Checklist

```bash
# 1. Verifica DNS
 dig NS balizero.com +short

# 2. Verifica headers CloudFlare
curl -I https://balizero.com | grep CF-

# 3. Verifica cache
curl -I https://balizero.com/_next/static/test.js | grep CF-Cache-Status

# 4. Verifica WebSocket
wscat -c wss://balizero.com/ws

# 5. Verifica SSL
openssl s_client -connect balizero.com:443 -servername balizero.com
```

---

## 📊 Monitoraggio

### Metriche da tracciare:

| Metrica | Target | Alert |
|---------|--------|-------|
| Cache Hit Ratio | >90% | <80% |
| Avg Response Time | <200ms | >500ms |
| Bandwidth Saved | >50% | <30% |
| Security Events | <100/day | >500/day |
| Origin Error Rate | <1% | >5% |

### Alert da configurare:

- [ ] Origin unreachable
- [ ] DDoS attack detected
- [ ] SSL certificate expiring (< 30 days)
- [ ] High error rates (> 5%)
- [ ] Cache hit ratio drop

---

## 💰 Costi Stimati

| Piano | Costo | Caratteristiche |
|-------|-------|-----------------|
| **Free** | $0 | CDN base, DDoS, SSL |
| **Pro** | $20/mese | WAF, Page Rules (20), Analytics |
| **Business** | $200/mese | SLA 100%, Supporto prioritario |

**Raccomandazione:** Iniziare con piano Pro per produzione.

---

## ⚠️ Considerazioni Importanti

### 1. WebSocket e Real-time
- CloudFlare supporta WebSocket su tutti i piani
- Timeout: 100 secondi di inattività
- Per sessioni lunghe: implementare ping/pong

### 2. Streaming
- Response Buffering: OFF per streaming SSE
- Max upload: 100MB (Business: 500MB)

### 3. Cache Invalidation
```bash
# Purge via API
curl -X POST "https://api.cloudflare.com/client/v4/zones/ZONE_ID/purge_cache" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}'
```

### 4. Rate Limiting (Pro+)
Configurare per API endpoints:
```
100 richieste / 10 secondi / IP
```

---

## 🚀 Deployment Plan

### Step-by-Step:

1. **Pre-deployment**
   - [ ] Backup configurazione DNS corrente
   - [ ] Notificare team del cambio
   - [ ] Pianificare finestra di manutenzione

2. **Deployment**
   - [ ] Aggiungere dominio a CloudFlare
   - [ ] Copiare record DNS esistenti
   - [ ] Aggiornare nameservers
   - [ ] Attendere propagazione (1-24h)

3. **Post-deployment**
   - [ ] Verificare tutti i servizi
   - [ ] Testare WebSocket
   - [ ] Monitorare errori
   - [ ] Ottimizzare Page Rules

---

## 📞 Supporto

- **CloudFlare Status:** https://www.cloudflarestatus.com/
- **Community:** https://community.cloudflare.com/
- **Supporto Pro:** Dashboard > Support

---

*Questo piano verrà aggiornato dopo aver definito i domini specifici da configurare.*
