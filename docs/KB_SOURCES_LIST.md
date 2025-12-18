# Knowledge Base Sources - NUZANTARA

Lista delle fonti fondamentali per la Knowledge Base su visti, immigrazione e business in Indonesia.

---

## 1. SITI GOVERNATIVI UFFICIALI

### Immigrazione
| Sito | URL | Contenuto |
|------|-----|-----------|
| **Imigrasi.go.id** | https://www.imigrasi.go.id | Portale principale Direktorat Jenderal Imigrasi |
| **eVisa Portal** | https://evisa.imigrasi.go.id | Applicazione visti elettronici, e-VOA, Golden Visa |
| **All Indonesia** | https://allindonesia.imigrasi.go.id | Nuovo portale unificato (obbligatorio dal 1 Oct 2025) |
| **Molina** | https://molina.imigrasi.go.id | Sistema e-Visa alternativo |

### Ministeri Chiave
| Sito | URL | Contenuto |
|------|-----|-----------|
| **Kemenkumham** | https://kemenkumham.go.id | Ministero Legge e Diritti Umani |
| **Kemlu** | https://kemlu.go.id | Ministero Affari Esteri, servizi consolari |
| **Kemnaker TKA Online** | https://tka-online.kemnaker.go.id | Permessi lavoro (RPTKA), Foreign Workers |
| **Pajak.go.id** | https://pajak.go.id | Tasse, NPWP per stranieri |

### Business & Investimenti
| Sito | URL | Contenuto |
|------|-----|-----------|
| **OSS (Online Single Submission)** | https://oss.go.id | Licenze business, NIB, Risk-Based Approach |
| **BKPM/Kementerian Investasi** | https://bkpm.go.id | Investimenti, PT PMA, Golden Visa corporate |

---

## 2. DATABASE LEGALI

### Priorità Alta
| Sito | URL | Contenuto | Note |
|------|-----|-----------|------|
| **Paralegal.id** | https://paralegal.id | ~25.000 normative indonesiane, sentenze, dizionario giuridico | Gratuito, completo |
| **Hukumonline** | https://www.hukumonline.com | 150.000+ regolamenti e sentenze, analisi bilingue | Premium ma contenuti free disponibili |

### Secondari
| Sito | URL | Contenuto |
|------|-----|-----------|
| **JDIH Kemenkumham** | https://jdih.kemenkumham.go.id | Database giuridico ufficiale |
| **Peraturan.go.id** | https://peraturan.go.id | Raccolta normative nazionali |

---

## 3. TIPI DI VISTO - REFERENCE

### Visti Principali da Documentare
| Codice | Nome | Target | Validità |
|--------|------|--------|----------|
| **B211A** | Social/Cultural Visa | Turisti, affari brevi | 60 giorni + ext |
| **e-VOA** | Electronic Visa on Arrival | Turisti 92 paesi | 30 giorni + 30 ext |
| **E28A** | Investor KITAS | Investitori (10B IDR) | 2 anni |
| **E30/E30A/E30B** | Student Visa | Studenti | 1-4 anni |
| **E33G** | Remote Worker / Digital Nomad | Nomadi digitali ($60k/anno) | 1 anno + 5 ext |
| **Second Home Visa** | Second Residency | High-net-worth (2B IDR deposit) | 5-10 anni |
| **Golden Visa** | Investment Visa | Investitori ($2.5M-$50M) | 5-10 anni |
| **Silver Hair** | Retirement Visa | Pensionati 60+ ($50k deposit) | 5 anni |
| **KITAS** | Limited Stay Permit | Lavoro, famiglia, investimento | 1-2 anni |
| **KITAP** | Permanent Stay Permit | Residenza permanente | 5 anni renewable |

---

## 4. REQUISITI CAPITALE 2025 (BKPM Reg 5/2025)

| Tipo | Capitale Minimo |
|------|-----------------|
| PT PMA (issued/paid-up) | IDR 2.5 miliardi (ridotto da 10B) |
| PT PMA (investimento totale) | IDR 10 miliardi per KBLI/location |
| Investor KITAS | IDR 10 miliardi in shares |
| Golden Visa (individuo 5y) | USD 2.5 milioni (company) o $350k (portfolio) |
| Golden Visa (individuo 10y) | USD 5 milioni (company) o $700k (portfolio) |
| Second Home Visa | IDR 2 miliardi (time deposit) o $1M (real estate) |

---

## 5. FONTI AGGIUNTIVE CONSIGLIATE

### Ambasciate/Consolati
- https://kbri-canberra.go.id (esempio struttura servizi consolari)
- Tutte le ambasciate su kemlu.go.id

### Agenzie Consulenza (per FAQ/guide)
- letsmoveindonesia.com
- cekindo.com
- ilaglobalconsulting.com

### News Legali
- Indonesian Legal Brief (ILB) - hukumonline.com/ilb

---

## 6. PRIORITÀ SCRAPING

### Fase 1 - Core (Immediato)
1. **paralegal.id** - Normative complete
2. **evisa.imigrasi.go.id** - Requisiti visti attuali
3. **imigrasi.go.id** - News e aggiornamenti
4. **oss.go.id** - Licenze business

### Fase 2 - Espansione
5. **hukumonline.com** (contenuti free)
6. **pajak.go.id** - NPWP e tasse
7. **tka-online.kemnaker.go.id** - Work permits
8. **kemlu.go.id** - Servizi consolari

### Fase 3 - Completamento
9. **bkpm.go.id** - Investimenti
10. **allindonesia.imigrasi.go.id** - Nuovo sistema
11. Regolamenti specifici da paralegal.id

---

## 7. NOTE TECNICHE PER INTEL SCRAPING

### Paralegal.id
- Endpoint ricerca: `/peraturan` con filtri per tipo/anno
- ~25.000 documenti indicizzabili
- Struttura: titolo, tipo norma, anno, testo completo

### Siti .go.id
- Spesso richiedono headers specifici
- Alcuni hanno API non documentate
- Rate limiting variabile

### Hukumonline
- Contenuti premium dietro paywall
- Articoli free indicizzabili
- Klinik Hukum (Q&A) molto utile

---

*Ultimo aggiornamento: Dicembre 2025*
