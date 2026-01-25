# 🏛️ Nuzantara Database Architecture (V2 System)

> **Versione:** 2.0 (Established Jan 25, 2026)  
> **Status:** Production Ready  
> **Core Concept:** "Squash & Reset" with Baseline Snapshot

Questo documento descrive la nuova architettura del database di Nuzantara, implementata per risolvere la frammentazione storica delle migrazioni e garantire stabilità in produzione.

---

## 1. Il Problema Risolto (Context V1)

Il sistema precedente (V1) soffriva di:

- **Frammentazione:** 44 file di migrazione, molti con logica rotta o dipendenze da codice Python non più esistente.
- **Gap Numerici:** Migrazioni mancanti che rendevano impossibile ricostruire il DB da zero in un nuovo ambiente.
- **Rischio Drift:** Disallineamento tra lo schema di Produzione e quello di Sviluppo.

## 2. La Soluzione V2: "Squash & Reset"

Il 25 Gennaio 2026 abbiamo effettuato un reset controllato del sistema di gestione delle migrazioni, **senza alterare i dati esistenti**.

### Componenti Chiave

1.  **La Baseline Unica (`001_baseline_v2.sql`)**
    - Invece di rieseguire la storia (V1), abbiamo creato uno **Snapshot** dello schema di produzione reale.
    - Questo file è ora l'unica fonte di verità per lo stato iniziale del database.
    - Contiene tutte le tabelle (`users`, `conversations`, ecc.), indici, trigger ed estensioni.

2.  **Nuovo Migration Manager (`migration_manager.py`)**
    - Aggiornato per leggere dalla cartella `migrations_v2/`.
    - Gestisce una nuova tabella di tracciamento: `_schema_versions` (sostituisce la vecchia `schema_migrations`).

3.  **Logica "Fake Apply" (Smart Transition)**
    - Il sistema è intelligente: se rileva che il DB è già popolato (es. esiste la tabella `users`) ma la tabella `_schema_versions` è vuota, capisce che si trova su un DB Legacy.
    - In questo caso, **marca la migrazione 001 come "APPLIED" senza eseguire l'SQL**.
    - Questo previene errori fatali ("Table already exists") e allinea istantaneamente il vecchio DB al nuovo sistema V2.

---

## 3. Mappa del Filesystem

| Percorso                                                 | Descrizione                                                                        |
| :------------------------------------------------------- | :--------------------------------------------------------------------------------- |
| `apps/backend-rag/backend/db/migrations_v2/`             | **NUOVA HOME.** Contiene `001_baseline_v2.sql` e le future migrazioni (`002_...`). |
| `apps/backend-rag/backend/db/migrations_legacy_archive/` | **ARCHIVIO.** Le vecchie 44 migrazioni V1. Solo per consultazione storica.         |
| `apps/backend-rag/backend/db/migration_manager.py`       | Il cervello del sistema. Gestisce apply, rollback e fake-apply.                    |
| `docs/DATABASE_V2_GUIDE.md`                              | **Manuale Operativo.** Leggere qui per "Come aggiungere una tabella".              |

---

## 4. Relazione con la Codebase (ORM)

Il refactoring del sistema di migrazione è stato **trasparente** per il codice applicativo.

- **Modelli Python (SQLAlchemy/Pydantic):** I file in `app/models.py` non sono stati toccati. Continuano a mappare le tabelle esattamente come prima.
- **Indirizzi:** La `DATABASE_URL` rimane invariata.
- **Dati:** Nessun dato è stato cancellato o modificato durante la transizione.

Zantara (il sistema) scrive e legge dalle stesse tabelle di sempre. È cambiato solo il modo in cui gestiremo le _future_ modifiche strutturali.

---

## 5. Protocollo di Sicurezza

### Backup

Prima di ogni operazione di schema, usare sempre il tool di backup:

```bash
./scripts/db_backup.sh [full|schema]
```

### Regola d'Oro per lo Sviluppo

**MAI modificare `001_baseline_v2.sql`.**
Se devi cambiare lo schema, crea SEMPRE una nuova migrazione sequenziale (`002`, `003`...).

---

## 6. Verifica Integrità

Per verificare lo stato attuale del sistema V2:

```bash
# Deve mostrare "001_baseline_v2.sql ... ✅ APPLIED"
cd apps/backend-rag && export PYTHONPATH=$(pwd) && python3 backend/db/migrate.py list
```

---

_Documentazione a cura del Team DevOps & Architecture - Gennaio 2026_
