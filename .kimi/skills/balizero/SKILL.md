# Bali Zero Custom Skill

## Overview

Estensione delle capacità di Kimi per operare direttamente sul sistema Bali Zero.

## Tools

### Database Query
Query dirette al PostgreSQL di Nuzantara.

### Google Drive Operations
Gestione file su Google Drive tramite token SYSTEM.

### CRM Operations
Operazioni su clienti, pratiche, documenti.

## Usage

Vedi script in `apps/backend-rag/`:
- `check_drive_token.py` - Verifica token Drive
- `refresh_drive_token.py` - Refresh token Drive

## Safety

- Tutte le operazioni sono tracciate
- Rate limiting attivo
- Rollback su errori
