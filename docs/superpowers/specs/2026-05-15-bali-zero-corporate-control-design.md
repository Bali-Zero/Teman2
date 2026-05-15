# Bali Zero Corporate Control System — Design Spec
**Date:** 2026-05-15 (rev. 2026-05-16)
**Author:** Zero (Bali Zero) + Claude Sonnet 4.6
**Brainstorm panel:** DeepSeek V4 Pro + Gemini 3.1 Pro + Codex GPT-5.5
**Ground-truth:** NB-6 (Ops & Compliance / UU PDP) + NB-10 (Team Guides / Indonesian labor law)
**Status:** Draft — approvato verbalmente, pending firma lunedì 2026-05-19

---

## 1. Goal & Constraints

### Business goal
Sistema "trust + verify" per 10 dipendenti indonesiani, Q3 2026. Previene esfiltrazione dati e uso non autorizzato degli asset aziendali (numero WA Business, CRM clienti, email aziendale) senza keylogger né screen recording.

### Hard constraints
| # | Constraint | Fonte |
|---|---|---|
| C1 | Zero costo ricorrente aggiuntivo (no Workspace Enterprise) | Bali Zero |
| C2 | No screen recording, no keylogger | "non voglio essere un tiranno" |
| C3 | Trust + verify — alert anomalia, non sorveglianza continua | Bali Zero |
| C4 | UU 27/2022 PDP compliant (DPIA + Privacy Notice + consenso) | NB-6 |
| C5 | Contratti solo Bahasa Indonesia (UU 24/2009 art. 31) | Bali Zero |
| C6 | Waarmerking notarization only (~Rp 200–500k/contratto) | Bali Zero |
| C7 | 15 SIM corporate Telkomsel Halo Business già acquistate | Bali Zero |
| C8 | Standardizzazione Android (tutti i telefoni aziendali) | Derivato da MDM |
| C9 | WA Business: app nativa mantenuta (no Cloud API pivot) | Bali Zero |

### Out of scope
- Infrastruttura fisica ufficio (armadietti, acquisto laptop)
- Workspace Enterprise upgrade — esplicitamente rifiutato

---

## 2. Target Population

**10 dipendenti** soggetti al rollout Q3 2026:

| Nome | Ruolo | Non-compete |
|---|---|---|
| Asya | Platform / Backend | Sì |
| Vino | Marketing | Sì |
| Krisna | LKPM / Reporting | Sì |
| Adit | Operations / Welcome | Sì |
| Ari Firda | Visa / Immigration | Sì |
| Dea | — | Sì |
| Surya | Tax operations | Sì |
| Damar | Marketing / War Room | Sì |
| Sahira | Sales / WhatsApp | Sì |
| Rina | Reception | Sì |

Ragione sociale nei contratti: da determinare in stesura per ciascun dipendente tra:
- PT Bayu Bali Nol
- PT Bali Nol Impresariat
- PT Bali Nol Konsultan

Cross-reference con 9 KTP forniti + dati CRM (`apps/backend-rag/backend/data/team_members.py`) in Phase 1.

---

## 3. Architecture — 4 Layers

### Layer 1 — Employment Contracts (PKWTT + 5 Allegati)

#### PKWTT principale
Contratto a tempo indeterminato in Bahasa Indonesia. Firma lunedì 2026-05-19, consegna notaio per waarmerking successivamente.

---

#### Lampiran I — Kerahasiaan dan Non-Divulgasi (NDA)
- Obbligo di riservatezza **perpetuo**, nessun limite geografico o temporale
- Copre: dati cliente, prezzi, processi operativi, know-how aziendale
- Pilastro primario — massima enforceability sotto KUHPerdata
- Sopravvive alla cessazione del rapporto di lavoro

---

#### Lampiran II — Penyerahan Hak Kekayaan Intelektual (IP Assignment)
- Tutto il lavoro creato durante il rapporto → ceduto a PT [X] (ragione sociale da determinare)
- Copre: codice, contenuti, liste clienti, processi, materiali marketing
- Allineato a UU 28/2014 Hak Cipta (work-for-hire)

---

#### Lampiran III — Non-Solicit + Non-Compete
**Non-solicit** (primario, forte):
- Divieto di sollecitare clienti e dipendenti Bali Zero per 24 mesi post-termine
- Ancorato a violazione NDA — massima enforceability

**Non-compete** (tutti i 10 dipendenti):
- Durata: 12 mesi post-termine
- Ambito geografico: Bali
- Settore: servizi immigration / tax / property / company setup Indonesia
- Compensazione obbligatoria: 50% ultimo stipendio mensile lordo per ogni mese di restrizione
- Riferimento giurisprudenziale: PN Jakarta Timur No. 54/Pdt.G/2017/PN.Jkt.Tim

**VIETATO citare:** MA RI 1331/K/Pdt/2010 — caso Hukum Adat Bali (successione), zero rilevanza lavorativa.

---

#### Lampiran IV — Acceptable Use Policy + Privacy Notice (UU PDP)

**Uso esclusivo aziendale degli strumenti:**
- Email Zoho (`@balizero.com`)
- Google Drive condiviso (`zero@balizero.com`, 5TB)
- CRM (`kita.balizero.com`)
- Numero WA Business Bali Zero

**Divieti espliciti:**
- Collegare il numero WA Business aziendale a dispositivi personali
- Usare profilo personale (browser, email, WA) su strumenti aziendali durante 09:00–18:00 WITA
- Rimozione SIM aziendale dal telefono aziendale durante orario di lavoro
- Installazione app non autorizzate su dispositivi aziendali

**Privacy Notice** (obbligatoria per UU PDP — non può essere sostituita solo dal PKWTT):
- Cosa si monitora: log accessi CRM, stato enrollment MDM, alert anomalia, screenshot Linked Devices settimanale
- Finalità: sicurezza asset aziendali e dati clienti
- Retention: 12 mesi
- Diritti del dipendente: accesso, rettifica, penghapusan (UU PDP Pasal 34)
- Base giuridica: legittimo interesse del datore di lavoro su sistemi aziendali (UU ITE + UU PDP)

**Firma di consenso esplicita** al monitoraggio dei sistemi di proprietà aziendale.

---

#### Lampiran V — Ganti Rugi dan Sanksi

**Livello 1 — Penale liquidata (eseguibile senza prova di danno):**

| Violazione | Importo |
|---|---|
| Device personale trovato collegato a WA Business aziendale | Rp 10.000.000 |
| Mancato invio screenshot Linked Devices entro lunedì 10:00 WITA | Rp 2.000.000 per settimana |
| Uso profilo personale su strumenti aziendali 09:00–18:00 WITA (documentato) | Rp 5.000.000 per incidente |
| Export massivo o condivisione dati fuori @balizero.com (documentato) | Rp 15.000.000 per incidente |

**Livello 2 — Penale per violazione grave:**

| Violazione | Importo |
|---|---|
| Divulgazione dati riservati (prezzi, processi, dati cliente) a terzi | Rp 50.000.000 |
| Sollecitazione cliente o dipendente Bali Zero entro 24 mesi post-termine | Rp 50.000.000 per soggetto sollecitato |
| Violazione non-compete (Lampiran III) | Rp 150.000.000 fisso |

**Livello 3 — Riserva di azione civile integrale:**

> *"Pembayaran ganti rugi likuidasi sebagaimana dimaksud dalam Lampiran ini tidak menghapuskan hak PT [X] untuk menuntut ganti rugi penuh atas kerugian nyata yang diderita, termasuk kehilangan pendapatan, nilai seumur hidup klien, dan biaya hukum, melalui gugatan perdata berdasarkan Pasal 1365 KUHPerdata (perbuatan melawan hukum)."*

(La penale contrattuale non estingue il diritto di PT [X] di richiedere il risarcimento integrale del danno effettivo — fatturato perso, valore lifetime cliente, spese legali — in sede civile ex art. 1365 KUHPerdata)

**Livello 4 — Clausola UU ITE (apre strada al penale):**

> *"Karyawan mengakui bahwa data klien, daftar harga, dan informasi rahasia perusahaan yang tersimpan dalam sistem perusahaan merupakan data elektronik yang dilindungi oleh UU No. 19 Tahun 2016 tentang ITE. Akses, pengambilan, atau penyebaran tanpa izin dapat dikenakan sanksi pidana sesuai Pasal 30 dan 32 UU ITE (ancaman pidana penjara hingga 8 tahun)."*

(I dati nei sistemi aziendali sono protetti da UU ITE. Accesso/estrazione/divulgazione non autorizzati = reato penale fino a 8 anni)

**Notarizzazione:** waarmerking ~Rp 200–500k × 10 = ~Rp 2–5M una tantum. Firma 2026-05-19, notaio successivamente.

---

### Layer 2 — Browser & Desktop Policy

#### 2a. Chrome Enterprise Core (free)
Collegamento tecnico gestito da Bali Zero (admin.google.com, Workspace Business Plus già attivo su `zero@balizero.com`).

Policies attive:
- `BrowserSignin: 2` — login obbligatorio account aziendale, blocco switch a profilo personale
- `URLBlocklist`: `web.whatsapp.com` (WA Web personale), `mail.google.com`, `accounts.google.com` (Gmail personale)
- `URLAllowlist`: `mail.zoho.com`, `kita.balizero.com`, `my.balizero.com`, `drive.google.com`
- `SessionLength: 540` — re-login ogni 9h (elimina drift sessione personale)
- Alert automatico a management se rilevato switch a profilo non aziendale

#### 2b. NextDNS (free, log-only)
- Filtro DNS al router ufficio — blocca/logga a livello di rete, immune al cambio browser
- Modalità: **log-only** (trust + verify — non blocca, registra)
- Copre tutta la rete WiFi aziendale
- Non copre hotspot personale (hotspot = violazione Lampiran IV, non problema tecnico)

#### 2c. AppLocker (Windows — dove applicabile)
- Whitelist eseguibili: Chrome aziendale, Zoho Desktop, Canva, Figma
- Block: Firefox, Edge, Telegram Desktop
- **WA Desktop Mac: non bloccato** — comodo per uso aziendale, il controllo è sul profilo non sull'app

#### 2d. Zoho Admin
- 2FA obbligatoria su tutti gli account `@balizero.com`
- IP allowlist: IP statico ufficio + range Tailscale (gratuito, già nel tailnet `balizero`)
- Dispositivi ufficio in tailnet: Mac Pro, Mac Mini (sempre in ufficio), Mac Air (Ari)
- Audit log retention: 90 giorni

---

### Layer 3 — WhatsApp Business & Mobile

#### 3a. WA Business: app nativa mantenuta
Nessun pivot a Cloud API. Si mantiene WA Business app nativa sui telefoni aziendali.

**Controllo Linked Devices — audit remoto settimanale:**
- Ogni lunedì entro le 10:00 WITA: ciascun dipendente invia screenshot della schermata "Linked Devices" su canale Telegram aziendale dedicato (bot raccoglie, management verifica)
- Mancato invio entro scadenza: Rp 2.000.000 (Lampiran V Livello 1)
- Device personale trovato nello screenshot: Rp 10.000.000 (Lampiran V Livello 1)
- Audit trail fotografico conservato 12 mesi

#### 3b. SIM come token bancario
- Registro fisico: SIM ↔ dipendente (detenuto da Bali Zero)
- PIN SIM abilitato su tutte le 15 SIM aziendali
- Divieto rimozione SIM da telefono aziendale durante orario di lavoro (Lampiran IV)
- **Protocollo exit:** sospensione SIM immediata al portale Telkomsel Business prima che il dipendente lasci l'edificio il giorno di termine
- 2FA preferita via Authenticator app (non SMS) per ridurre rischio intercettazione OTP

#### 3c. Miradore Free MDM (Android, 50 device free)
- Enrollment: tutti i 15 telefoni aziendali Android via QR code
- Modalità: **Work Profile** (meno invasivo, conforme C2)
  - App aziendali nel work profile
  - Remote wipe del solo work profile (non tocca dati personali)
  - NON rileva uso hotspot personale — coperto da Lampiran IV
- Policy: encryption obbligatoria, PIN schermo, blocco installazione app non autorizzate nel work profile

---

### Layer 4 — Monitoraggio Anomalie

Nessuna sorveglianza continua. Solo alert su eventi di sicurezza. Alert → management only, mai visibili ai dipendenti.

| Segnale | Soglia | Azione |
|---|---|---|
| Nuovo dispositivo login CRM (`kita.balizero.com`) | Qualsiasi | Alert Telegram → Bali Zero management |
| Export massivo (>50 record CSV/PDF) | Qualsiasi | Alert Telegram → Bali Zero management |
| Accesso CRM fuori orario (prima 08:00 / dopo 20:00 WITA) | Qualsiasi | Log + digest settimanale |
| Condivisione Drive fuori `@balizero.com` | Qualsiasi | Alert Telegram → Bali Zero management |
| Fallimento 2FA Zoho consecutivo | >3 | Alert + blocco account automatico |

**NON monitorato:** contenuto messaggi, keystroke, schermo, dispositivi personali, attività private fuori orario.

**Implementazione touchpoint:**
- CRM: `apps/backend-rag/backend/app/routers/` — audit event emitter su endpoint export
- Drive: `scripts/drive_poll_service.py` — estendere per rilevare external share
- Telegram: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_CHAT_ID` esistenti

---

## 4. Fasi di Implementazione

| Fase | Deliverable | Settimana |
|---|---|---|
| **1** | OCR 10 KTP → roster `research/hr/2026-05-16-team-roster-10-members.md`; draft 10 PKWTT + Lampiran I-V; firma 2026-05-19 | W1 |
| **2** | Chrome Enterprise Core policies; Zoho 2FA + IP allowlist; NextDNS log-only; DPIA doc interno | W2 |
| **3** | Miradore MDM enrollment 15 telefoni; registro SIM; canale Telegram Linked Devices | W3-4 |
| **4** | CRM anomaly detector; Drive external-share alert; alert Telegram management | W5 |
| **5** | Consegna contratti firmati al notaio per waarmerking | Post-W1 |

**DPIA obbligatoria** prima del deploy Layer 4 (UU PDP — rischio sanzione Rp 60M).

---

## 5. Costi

| Voce | Tipo | Costo |
|---|---|---|
| Chrome Enterprise Core | Ricorrente | Rp 0 (free) |
| NextDNS | Ricorrente | Rp 0 (free tier) |
| Miradore Free MDM | Ricorrente | Rp 0 (free ≤50 device) |
| Tailscale | Ricorrente | Rp 0 (free) |
| SIM corporate 15× | Ricorrente | Rp 825k/mese (già acquistate) |
| PKWTT waarmerking × 10 | Una tantum | ~Rp 2–5M |
| **Nuovo costo ricorrente** | | **Rp 0** |

---

## 6. Anchor Legali

| Documento | Rilevanza | Status |
|---|---|---|
| UU 13/2003 Ketenagakerjaan + UU Cipta Kerja 6/2023 | Framework PKWTT | Verificato NB-10 |
| KUHPerdata Pasal 1337-1338 | Non-compete + penali enforceability | Verificato |
| KUHPerdata Pasal 1365 | Azione civile danno effettivo | Verificato |
| UU 28/2014 Hak Cipta | IP Assignment | Verificato |
| UU 27/2022 PDP | Compliance monitoraggio | Verificato NB-6 |
| UU 19/2016 ITE Pasal 30+32 | Reato penale furto dati | Verificato |
| UU 24/2009 Pasal 31 | Obbligo Bahasa Indonesia | Verificato |
| PN Jakarta Timur 54/Pdt.G/2017/PN.Jkt.Tim | Precedente non-compete con LD = valido | Verificato NB-10 |

**VIETATO citare:** MA RI 1331/K/Pdt/2010 (caso matrimoniale Hukum Adat Bali).

---

## 7. Rischi

| Rischio | Prob | Impatto | Mitigazione |
|---|---|---|---|
| Non-compete voided in PHI | Media | Basso (non-solicit + NDA intatti) | Non-solicit è pilastro primario |
| Dipendente usa hotspot per bypassare NextDNS | Media | Basso | Lampiran IV + penale Rp 5jt |
| DPIA non completata prima di Layer 4 | Bassa | Alto (sanzione UU PDP Rp 60M) | Phase 4 bloccata su completamento DPIA |
| Screenshot Linked Devices falsificato | Bassa | Medio | Audit fisico occasionale a sorpresa |
| SIM intercettazione OTP fuori orario | Bassa | Medio | Authenticator app preferred, SIM PIN |
| Forwarding documento WA in 10s (DeepSeek finding) | Media | Alto | Documenti cliente su Drive, mai su WA |
