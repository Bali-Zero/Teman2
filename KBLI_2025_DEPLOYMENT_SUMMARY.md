# Deployment Summary - 2026-02-24 (KBLI 2025 Funnel & Backend Fixes)

## 1. Funnel Intelligence KBLI 2025

- **Frontend:** Integrata logica di lead capture in `KBLI-Explorer` (modal "Black Book", banner di transizione, alert contestuali sui codici revocati).
- **Asset Social:** Progettati 4 caroselli IG (Nomad Exit, 10B Coffee, Slow Paralysis, Villa Delisting) con estetica Nano Banana Pro (Black & Gold).
- **Dossier:** Strutturato il contenuto del "KBLI 2025 Black Book" per la conversione lead.

## 2. Backend Technical Fixes

- **Auth Middleware:** Sbloccati endpoint pubblici `/api/blog/`, `/api/vitals` e `/api/blog/newsletter/subscribe` per eliminare errori 401 in produzione.
- **Instagram Webhook:** Implementato e registrato il router per i webhook di Meta, risolvendo i 404 sui messaggi in entrata.
- **Notification Scheduler:** Riparato bug critico (`TypeError` e `NameError` su `asyncpg`). Lo scheduler ora riceve correttamente il database pool e invia le email automatiche.
- **Dependencies:** Aggiunti `apscheduler` e `aiosmtplib` a `requirements-prod.txt`.

## 3. System Cleanup

- **CRM Auto:** Rimosso completamente dal backend (`router_registration.py` e `hybrid_auth.py`).
- **Dashboard Team:** Aggiornata documentazione `DASHBOARD_COVERAGE_REPORT.md` per riflettere il passaggio da AutoCRM a CRM Analytics.

## 4. Status Operativo

- **Backend:** Live su Fly.io (`nuzantara-rag`).
- **Scheduler:** Attivo e monitorato.
- **Marketing:** Sistema pronto per il lancio dei caroselli.

**Nota per Adit/Sahira:** In caso di errori post-deploy sulla dashboard, eseguire Logout -> Login e Hard Refresh (CMD+Shift+R).
