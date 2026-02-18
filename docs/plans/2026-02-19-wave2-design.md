# Land Intel Wave 2 — Design

**Date:** 2026-02-19
**Scope:** Saved Parcels (PostgreSQL) + PDF Export (reportlab)

---

## Feature 1: Saved Parcels

**Obiettivo:** Persistenza condivisa dei terreni analizzati, con note e gestione da interfaccia.

**Database:** PostgreSQL Fly.io, accesso via `fly proxy 15432:5432`
**Connessione:** `psycopg2` sincrono (compatibile Streamlit)
**Connection string:** `postgres://backend_rag_v2:PASSWORD@localhost:15432/nuzantara_rag?sslmode=disable`

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS saved_parcels (
    id SERIAL PRIMARY KEY,
    saved_at TIMESTAMP DEFAULT NOW(),
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    indirizzo TEXT,
    zona_code TEXT,
    zona_name TEXT,
    desa TEXT,
    superficie_m2 INTEGER,
    prezzo_idr BIGINT,
    roi_pct DOUBLE PRECISION,
    walk_score INTEGER,
    noise_level TEXT,
    elevazione_m DOUBLE PRECISION,
    bpn_tipehak TEXT,
    densita_1km INTEGER,
    note TEXT
);
```

**UI Land Intel:** bottone "💾 Salva terreno" dopo analisi completata (accanto a CSV export).

- Apre un text_area per nota opzionale
- Conferma salvataggio con st.success

**Nuovo modulo sidebar:** `📌 Saved Parcels`

- Tabella con tutti i terreni salvati (ordinati per data desc)
- Filtro per zona_code
- Bottone 🗑️ per eliminare singola riga
- Bottone per aggiungere/modificare nota inline

**Gestione connessione:** funzione `get_pg_conn()` che legge `DATABASE_URL` da env, fallback con messaggio "Fly proxy non attivo — avvia: `fly proxy 15432:5432 -a nuzantara-rag`"

---

## Feature 2: PDF Export

**Obiettivo:** Report professionale scaricabile con tutti i dati dell'analisi.

**Libreria:** `reportlab` — generazione in-memory, no dipendenze C
**Install:** `pip install reportlab`

**Contenuto PDF:**

1. Header: "NUZANTARA PRIME — LAND INTELLIGENCE REPORT", data/ora, coordinate
2. Sezione Zona: zona_code, zona_name, desa, definizione
3. Parametri Urbanistici: KDB, KLB, KDH, altezza max, GSB
4. Analisi Finanziaria: ROI%, break-even, strategia ottimale, prezzo IDR + conversione USD
5. Catasto BPN: tipehak, luas, nomor, anno
6. Contesto: walk score, noise level, elevazione, distanza costa
7. Mercato Turistico: densità 500m/1km/2km
8. Vincoli overlay (se presenti)
9. Footer: "Dati: BATARA live, BPN BHUMI, OSM Overpass, Open-Elevation"

**UI:** bottone `📄 Esporta PDF` accanto al CSV export dopo analisi completata.
Generazione in-memory con `io.BytesIO`, servito via `st.download_button`.
Filename: `land_intel_{lat}_{lon}_{date}.pdf`

---

## Ordine di implementazione

1. Schema DB + funzione connessione
2. Bottone salva + insert PostgreSQL
3. Modulo Saved Parcels (lista, filtro, delete, note)
4. Install reportlab + funzione `generate_pdf(data_dict)`
5. Bottone PDF export in Land Intel
