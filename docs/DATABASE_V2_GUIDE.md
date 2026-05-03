# 🗄️ Nuzantara Database Guide (V2 Standards)

Questa guida definisce gli standard per la gestione, modifica e sviluppo del database PostgreSQL di Nuzantara.
Seguire rigorosamente queste procedure per evitare disallineamenti dello schema e perdita di dati.

---

## 🏗️ Filosofia V2: "Baseline & Incremental"

Il sistema di migrazioni di Nuzantara è stato rifattorizzato (V2) per eliminare la frammentazione storica.

1.  **Baseline Pulita (`001_baseline_v2.sql`):** Esiste un UNICO file che definisce lo stato iniziale "pulito" del database. Questo file contiene tutto lo schema consolidato.
2.  **Migrazioni Lineari:** Tutte le modifiche successive devono essere migrazioni sequenziali numerate (`002_...`, `003_...`).
3.  **Separazione Dati:** I dati statici (lookup tables come `visa_types`) NON sono nelle migrazioni ma in script di **Seeding** dedicati.

---

## 🚀 Workflow Operativi

### 1. Backup Prima di Tutto

Mai eseguire operazioni distruttive o migrazioni complesse senza un backup.

```bash
# Backup Completo (Locale)
./scripts/db_backup.sh full

# Backup Solo Schema (Locale)
./scripts/db_backup.sh schema
```

### 2. Aggiungere una Nuova Tabella

Per creare una nuova tabella, NON modificare file esistenti. Crea una nuova migrazione.

1.  Crea un file in `apps/backend-rag/backend/db/migrations_v2/`
2.  Nome file: `XXX_descrizione_breve.sql` (es. `002_create_user_preferences.sql`)
3.  Contenuto Standard:

```sql
-- Migration: 002_create_user_preferences
-- Author: [Tuo Nome]
-- Date: [YYYY-MM-DD]

CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(50) DEFAULT 'system',
    notifications_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indici (Obbligatori per Foreign Keys)
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

-- Trigger aggiornamento automatico updated_at (Opzionale ma consigliato)
DROP TRIGGER IF EXISTS set_timestamp ON user_preferences;
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON user_preferences
FOR EACH ROW
EXECUTE PROCEDURE trigger_set_timestamp();
```

### 3. Modificare una Tabella Esistente

Per aggiungere colonne o modificare tipi, usa `ALTER TABLE`.

1.  Crea nuova migrazione: `003_add_phone_to_users.sql`
2.  Contenuto:

```sql
ALTER TABLE users
ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_users_phone_number ON users(phone_number);
```

### 4. Data Seeding (Dati Iniziali)

Se devi inserire dati fissi (es. lista province, tipi di abbonamento):
**NON USARE INSERT NELLE MIGRAZIONI.**

Usa i seeder in `apps/backend-rag/backend/db/seeds/`.

---

## 📏 Naming Conventions

- **Tabelle:** `snake_case`, plurale (es. `users`, `order_items`).
- **Colonne:** `snake_case` (es. `first_name`, `is_active`).
- **Primary Key:** Sempre `id` di tipo `UUID`.
- **Foreign Keys:** `tabella_id` (es. `user_id`, `order_id`).
- **Indici:** `idx_nometabella_nomecolonna`.

---

## ⚠️ Regole di Sicurezza

1.  **Idempotenza:** Ogni script SQL deve poter essere eseguito più volte senza errori (usa `IF NOT EXISTS`, `DROP ... IF EXISTS`).
2.  **No Drop:** Mai usare `DROP TABLE` in produzione senza una review esplicita.
3.  **Transazioni:** Le migrazioni vengono eseguite implicitamente in transazione (se una fallisce, tutto rollbacka), ma scrivere script atomici è buona norma.

---

## 🛠️ Comandi Utili

| Azione                 | Comando                                                   |
| :--------------------- | :-------------------------------------------------------- |
| **Check Stato**        | (Verrà implementato nel nuovo manager)                    |
| **Applica Migrazioni** | `python apps/backend-rag/backend/db/migrate.py up`        |
| **Reset DB Locale**    | `docker compose down -v postgres && docker compose up -d` |

---

_Documento aggiornato al: 2026-01-25_
