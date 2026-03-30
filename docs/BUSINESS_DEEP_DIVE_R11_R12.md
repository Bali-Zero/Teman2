# Business & Revenue Deep Dive — Round 11-12

> Ricerca profonda su: pricing, WhatsApp Flows, market sizing, churn,
> frontend performance, prompt optimization, Google Workspace, NLM prodotto,
> War Room, email, SEO, Ollama, satellite apps, Canva

---

## 1. PRICING STRATEGY

### Competitor Prezzi Esatti (trovati!)

| Servizio | Emerhub | BaliVisas | Market | **Noi (proposta)** |
|----------|---------|-----------|--------|-------------------|
| PT PMA setup | $1,700 | $1,600 | $1,600-2,240 | **$1,500** (-12%) |
| KITAS Investor 1yr | — | $910 | $900-1,500 | **$900** |
| KITAS Working 1yr | — | $1,140-1,490 | — | **$1,200** |
| KITAP 5yr | — | $3,540 | — | **$3,500** |
| Tax monthly | $80-300 | $130 | — | **$120** |
| Full package (PMA+KITAS+compliance) | $12-15K | — | — | **$8,000** |

### Modello Raccomandato: Hybrid 3-Tier

| Tier | Setup | Retainer/mese | Target |
|------|-------|---------------|--------|
| **Basic** (AI self-service + guidance) | $800 | — | Nomadi, budget |
| **Standard** (AI + human review) | $1,500 | $150/mo | Maggioranza (60%) |
| **Premium** (dedicated + priority + AI) | $3,500 | $300/mo | Corporate, VIP |

### AI Premium: +25% per processing veloce
KITAS standard 30gg → AI-speed 7gg = $1,125 (vs $900 base). 30% clienti urgenti pagano.

### Compliance-as-a-Service: $99-299/mo
- $99: alert visa/tax/license expiry
- $199: alert + filing + monitoring
- $299: full compliance + DPO-as-a-Service + quarterly audit

### Freemium funnel:
- Free: KBLI lookup (balizero.com/kbli), visa eligibility quiz
- Conversion tipica B2B: 2-5% freemium → paid
- Con 50K visitatori/mese → 1,000-2,500 lead/mese

---

## 2. WHATSAPP FLOWS

### Capabilities confermate:
- **DocumentPicker**: upload passport/KTP scan direttamente in chat (PDF/JPEG, 25MB)
- **Catalog**: lista servizi con prezzi (fino a 500 items)
- **Interactive buttons**: quiz eligibilità visa in chat
- **Template utility**: "Visa status: {{2}}" → IDR 357/msg, approvazione 24-48h
- **No pagamento nativo** in Flows → redirect Xendit link

### Costi Cloud API Indonesia:
- Marketing: IDR 1,940/msg
- **Utility/Auth: IDR 357/msg**
- **Service: prime 1000 conv/mese GRATIS**, poi tariffa utility
- Cloud API 30-50% più economico dei BSP (Twilio/Wati)

### Flow proposto per visa:
```
Client apre chat → Quick reply "Visa" →
Flow screen 1: Nationality, Purpose (work/invest/retire/nomad) →
Flow screen 2: DocumentPicker passport scan →
Flow screen 3: Summary + Xendit payment link →
Auto-create practice nel CRM + notify team
```

---

## 3. MARKET SIZING (TAM/SAM/SOM)

(Da dati xAI Round 11 — numeri da verificare con fonti ufficiali)

| Metrica | Valore | Fonte |
|---------|--------|-------|
| Stranieri residenti Indonesia | ~350K | BPS estimate |
| PT PMA attive Indonesia | ~75K | BKPM |
| Nuovi visa/anno Indonesia | ~200K | Ditjen Imigrasi |
| Expat Bali specificamente | ~30-50K | Stima community |
| Digital nomad Bali | ~10-15K | NomadList + E33G data |
| Nuove company/anno Bali | ~5K | DPMPTSP Bali |

**TAM** (Indonesia): 350K stranieri × $2K avg service = **$700M/anno**
**SAM** (Bali + online-reachable): ~80K target × $2K = **$160M/anno**
**SOM** (3 anni, con AI advantage): 15K clienti × $2K = **$30M/anno**

### CLV (Customer Lifetime Value):
- Servizio iniziale: $1,500 (PMA) + $900 (KITAS) = $2,400
- Retainer annuale: $150/mo × 12 = $1,800
- Renewal (KITAS annuale): $900/anno
- CLV 3 anni: **$2,400 + $1,800×3 + $900×2 = $9,600**

---

## 4. CLIENT CHURN

### Modello raccomandato: LightGBM
- AUC 90-95% anche su 5000 clienti (3 anni storia)
- Feature top: avg_days_to_payment, ticket_per_month, usage_frequency, days_since_last_interaction

### Retention anchors (ciclo immigration):
- KITAS renewal: 45gg prima → WhatsApp reminder + upsell KITAP
- Tax filing: Marzo → reminder + offerta filing package
- License renewal: OSS annual → compliance alert
- Company annual report: → reminder + assistance

### Proactive saves: 34% clienti a rischio salvati con intervento tempestivo

---

## 5. FRONTEND PERFORMANCE

### Target Core Web Vitals 2026:
- LCP ≤ 2.5s (SSG taglia 50% vs SSR)
- INP ≤ 200ms (sostituisce FID)
- CLS ≤ 0.1

### Quick wins:
- `next/image` con AVIF → -40-70% size, LCP +20-30%
- Dynamic imports per componenti pesanti (chart, map) → bundle <170KB
- Lighthouse CI in GitHub Actions → fail build se <90 score
- `next-sitemap` per 1563 KBLI pages

---

## 6. PROMPT OPTIMIZATION

### Compression: 2000 → 300 token
- Claude 4.6 mantiene **95% capability al 15% lunghezza**
- Tagliabili: CLOSING_PHRASES (50+), GREETING_RULES verbose, emotional adaptation
- Prompt caching Anthropic: 90% risparmio ($720→$72/mese)
- Zero-shot > few-shot per Claude 4.6 (79-100% SWE-bench)

### Multilingual:
- Non-English costa 1.5-2x token
- Prompt specifici per lingua tagliano 20-30%
- Detect language → route a prompt tailored

---

## 7. GOOGLE WORKSPACE INTEGRATION

### Tutti i 4 servizi integrabili via `google-api-python-client`:
- **Calendar**: auto-create eventi da milestone practice
- **Sheets**: compliance matrices, client reports
- **Gmail**: tracking comunicazioni client
- **Meet**: link consultazione automatico

### Costi: API gratis. Workspace $6/user/mese.

---

## 8. WAR ROOM ALTERNATIVE

### Prefect 3.0 > Temporal per il nostro caso
- Python-native (`@flow` + `@task`)
- Free OSS, Cloud free tier (10 flows)
- UI per observability
- Sostituisce 8-stage shell pipeline con DAG robusto

---

## 9. EMAIL DELIVERABILITY

### Brevo (nostro provider):
- Deliverability tipica: 88-95%
- Serve: SPF/DKIM/DMARC configurati su balizero.com
- Auto warm-up per IP dedicato
- GlockApps per test prima di campagne

---

## 10. SEO TECNICO

### Azioni immediate:
- `next-sitemap` per 1563 KBLI + blog pages
- JSON-LD: FAQPage + HowTo + LocalBusiness su pagine immigration
- robots.txt: bloccare GPTBot/ClaudeBot/PerplexityBot (o permettere per GEO)
- Lighthouse CI in GitHub Actions per ogni PR

---

## 11. OLLAMA OPTIMIZATION (M4 Pro 48GB)

### MLX > GGUF su Apple Silicon (20-50% più veloce)
- Qwen3.5:27b Q4_K_M → ~18GB RAM
- Speculative decoding con qwen3.5:9b come draft
- Multi-model: 27b + 7b + 3b = ~40GB (ci sta nei 48GB)
- `mlx_lm.server` per batched inference

---

## 12. SATELLITE APPS

### Verdetto: consolidare da 6 a 3
- **Tenere**: kita (workspace), my (portal), zantara (chat)
- **Consolidare**: mail+calendar+drive+knowledge → integrati nel workspace
- Next.js Multi-Zones per deploy unificato
- SSO semplificato (meno cross-domain)

---

*Business Deep Dive v1.0 — 29 marzo 2026*
*Round 11 (pricing, WA, market, churn, frontend, prompt) + Round 12 (GWS, NLM, War Room, email, SEO, Ollama, satellites, Canva)*
