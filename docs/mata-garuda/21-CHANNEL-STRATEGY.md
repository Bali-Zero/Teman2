# Mata Garuda — Channel Strategy

> Data: 2026-04-08 | Sessione: brainstorming iniziale

## Overview

Mata Garuda non produce solo intelligence — la **distribuisce nel formato giusto, al pubblico giusto, nel momento giusto**.

Ogni canale ha un Channel Agent dedicato che riceve intelligence products dal bus e li adatta.

## Canali

### 1. Telegram Privato Zero
- **Audience**: Solo Zero
- **Contenuto**: TUTTO (briefing, alert, OSINT, decisioni L2, source health)
- **Lingua**: Italiano
- **Frequenza**: Real-time (alert) + daily (briefing) + weekly (digest, autonomy log)
- **Bot**: @Balizerobot (chat_id: 1125336968)
- **Formato**: Markdown strutturato con emoji per priority
- **Autonomia Agent**: L1 (invia senza chiedere)

### 2. Telegram Channel Bali Zero
- **Audience**: Clienti + pubblico
- **Contenuto**: News curate, no OSINT, no internal
- **Lingua**: Inglese (primary) + Indonesiano (quando rilevante)
- **Frequenza**: 1-3 post/giorno (solo score > 0.6)
- **Formato**: Titolo + 2-3 righe + link articolo balizero.com
- **Autonomia Agent**: L2 (draft → review queue, auto-publish se score > 0.8)
- **[OPEN]**: Channel esiste? Da creare?

### 3. Instagram (@balizero)
- **Audience**: Expat community Bali, potenziali clienti
- **Contenuto**: Carousel informativi (via War Room)
- **Lingua**: Inglese (primary)
- **Frequenza**: 2-3/settimana
- **Formato**: 6-11 slide Canva, cover Fireworks/Flux
- **Pipeline**: Mata Garuda briefing → WR Topic Agent → War Room pipeline
- **Autonomia Agent**: L2 (topic auto-selected, content reviewed)

### 4. X/Twitter (@Balizero0)
- **Audience**: Internazionale, digital nomad, investor
- **Contenuto**: Thread breaking news + commento esperto
- **Lingua**: Inglese
- **Frequenza**: Real-time su regulation changes + 2-3 thread/settimana
- **Formato**: Thread 3-7 tweet con citazioni e link
- **Autonomia Agent**: L2 (draft thread → review per breaking, auto per repost)
- **[OPEN]**: CRC broken (da CLAUDE.md). Va riparato prima.
- **Note**: Premium+ scade ~maggio 2026

### 5. Newsletter Email
- **Audience**: Clienti BZ registrati
- **Contenuto**: Weekly digest top 5 notizie + 1 deep analysis
- **Lingua**: Inglese
- **Frequenza**: Venerdi (pre-weekend read)
- **Formato**: HTML email responsive
- **Tool**: [OPEN] Resend / SendGrid / Brevo?
- **Autonomia Agent**: L1 (auto-generate) → L2 (Zero review prima del primo mese, poi auto)

### 6. Blog balizero.com
- **Audience**: Pubblico, SEO, lead generation
- **Contenuto**: Long-form articles da enriched pipeline
- **Lingua**: Inglese + Indonesiano (per SEO)
- **Frequenza**: 2-3/settimana
- **Formato**: 1400-2000 parole, SEO ottimizzato (gia nel pipeline step 5_seo)
- **Pipeline**: Scraper enrichment → SEO → publish (gia esiste, estendere con auto-scheduling)
- **Autonomia Agent**: L1 per articoli T1 source con score > 0.7

### 7. WhatsApp Broadcast
- **Audience**: Clienti con practice attive
- **Contenuto**: SOLO breaking news urgenti che li toccano
- **Lingua**: Inglese (primary)
- **Frequenza**: Solo quando impact > 0.8 E tocca servizio del cliente
- **Formato**: 1 messaggio conciso + link
- **Filtro**: client.service_type MATCH article.topic
- **Autonomia Agent**: L3 (SEMPRE approvazione Zero per broadcast)
- **[OPEN]**: Limiti Meta API, template pre-approvati necessari

### 8. LinkedIn (Bali Zero company page)
- **Audience**: Professional, B2B, investor
- **Contenuto**: Thought leadership repackaged da weekly digest
- **Lingua**: Inglese
- **Frequenza**: 1/settimana (lunedi)
- **Formato**: Post lungo (1000-1500 parole) o article
- **Autonomia Agent**: L2 (draft → review)
- **[OPEN]**: LinkedIn page esiste? API posting?

## Matrice Canale × Intelligence Product

| Product | TG Zero | TG Channel | IG | X | Newsletter | Blog | WA | LinkedIn |
|---------|---------|------------|-----|---|------------|------|----|----------|
| Daily Briefing | ✅ | - | - | - | - | - | - | - |
| Reg Alert | ✅ | ✅ (se public) | - | ✅ thread | - | ✅ article | ✅ (se impact>0.8) | - |
| Contradiction | ✅ | - | - | - | - | - | - | - |
| Weekly Digest | ✅ | summary | - | - | ✅ full | - | - | ✅ repack |
| WR Topics | ✅ | - | ✅ carousel | - | - | - | - | - |
| OSINT Feed | ✅ | ❌ MAI | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Comp Digest | ✅ | - | - | - | menzione | - | - | - |

## Lingua Decision Tree

```
IF audience == Zero:
    lingua = Italiano
ELIF canale == Instagram OR canale == X OR canale == LinkedIn:
    lingua = Inglese
ELIF canale == TG_Channel:
    lingua = Inglese (default) + Indonesiano (se fonte indonesiana rilevante)
ELIF canale == Newsletter:
    lingua = Inglese
ELIF canale == WhatsApp:
    lingua = Inglese (default), client.preferred_language se noto
ELIF canale == Blog:
    lingua = Inglese (primary) + duplicate Indonesiano (per SEO)
```

## [OPEN] Da approfondire

- TG Channel BZ: esiste? Da creare? Quanti subscriber?
- X CRC: come riparare? Serve per la strategia
- LinkedIn page: esiste? API access?
- Newsletter tool: Resend (semplice, $0 per <3000 email/mo) vs SendGrid
- WhatsApp template messages: serve pre-approvazione Meta
- SEO dual-language: come gestire /en/ e /id/ per lo stesso articolo?
- Content calendar: chi decide i giorni di pubblicazione per canale?
- Analytics: come misurare performance per canale? UTM? GA4?
