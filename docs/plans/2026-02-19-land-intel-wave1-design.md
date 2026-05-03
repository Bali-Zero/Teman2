# Land Intel Wave 1 — Design

**Date:** 2026-02-19
**Scope:** 5 feature a basso effort / alto impatto per potenziare il modulo Land Intel

---

## Feature 1 & 2: Walk Score + Noise Map (OSM Overpass)

**Obiettivo:** Dare un segnale immediato su qualità del contesto urbano e impatto rental.

**Implementazione:**

- Unica chiamata Overpass batch che fetcha POI entro 1km
- Walk Score (0–100): somma pesata di spiagge (×20), supermercati (×15), ospedali (×15), ATM (×10), ristoranti (×5), farmacia (×10) — cap a 100
- Noise Map: conta bar/club/pub entro 300m + strade `highway=primary/secondary` entro 150m → livello "🟢 Silenzioso / 🟡 Moderato / 🔴 Rumoroso" con stima impatto yield (±%)
- UI: sezione `🏃 Contesto Urbano` con due colonne — walk score gauge + noise signal

**API:** `https://overpass-api.de/api/interpreter` — già integrata, zero costi

---

## Feature 3: Elevazione

**Obiettivo:** Rilevare rischio alluvione e potenziale vista mare.

**Implementazione:**

- GET `https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}`
- Output: metri slm
- Logica derivata:
  - `< 3m` → ⚠️ Rischio alluvione alto
  - `3–8m` → 🟡 Zona bassa, verificare
  - `> 8m` → ✅ Sicuro
  - `> 15m` + distanza costa `< 3km` → 🌊 Possibile vista mare
- Distanza costa: calcolata via Haversine contro coordinate fisse litorale Badung
- UI: metric card in fondo ai parametri urbanistici

**API:** Open-Elevation — gratuita, no auth

---

## Feature 4 & 5: Calcolatore Valuta + Storico IDR/USD

**Obiettivo:** Contestualizzare prezzi in valuta dell'investitore.

**Implementazione:**

- Sidebar: widget sempre visibile con IDR → USD/EUR live, aggiornato ogni 60min via `@st.cache_data(ttl=3600)`
- API: `https://api.frankfurter.app/latest?from=IDR&to=USD,EUR` — gratuita, no auth
- Storico 12 mesi: `https://api.frankfurter.app/{start}..{end}?from=IDR&to=USD` → line chart Altair nel modulo ROI Calculator
- Il prezzo IDR inserito in Land Intel mostra automaticamente la conversione in USD/EUR sotto il campo input

---

## Feature 6: CSV Export

**Obiettivo:** Output strutturato di ogni analisi completata per archiviazione/condivisione.

**Implementazione:**

- Bottone `📥 Esporta CSV` appare dopo analisi completata (dopo AI Assessment)
- Dati inclusi: timestamp, lat/lon, indirizzo geocodificato, zona BATARA, KDB/KLB/KDH/TB, ROI, break-even, BPN tipehak/luas/nomor, vincoli (stringa), walk score, noise level, elevazione, densità OSM 500m/1km/2km
- Formato: `pandas.DataFrame.to_csv()` → `st.download_button()` con MIME `text/csv`
- Filename: `land_intel_{lat}_{lon}_{date}.csv`

---

## Ordine di implementazione

1. Calcolatore valuta (sidebar, indipendente dal resto)
2. Elevazione (singola API call, inserita nei parametri urbanistici)
3. Walk Score + Noise Map (un blocco Overpass)
4. Storico IDR/USD (chart nel ROI Calculator)
5. CSV Export (dopo che tutti i dati sono disponibili)

## File modificati

- `app_dashboard.py` — unico file, tutte le modifiche qui
- Nessuna dipendenza nuova (Altair è già incluso con Streamlit)
