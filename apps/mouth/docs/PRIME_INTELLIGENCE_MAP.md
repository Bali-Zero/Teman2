# Prime Intelligence — Bali Zoning Map

**URL:** `https://prime.balizero.com`
**Component:** `apps/mouth/src/components/maps/PrimeMap3D.tsx`
**Last updated:** 2026-03-12

---

## Overview

Prime Intelligence è una mappa 3D interattiva che mostra le zone urbanistiche di Bali (Kabupaten Badung) con dati ufficiali GISTARU/BATARA del DPUPR. Consente agli utenti di esplorare cosa è costruibile in ogni punto del territorio.

**Stack:**

- Google Maps JS API v=beta (`maps3d` + `places` libraries)
- FastAPI backend → `/api/prime/zoning?lat=&lng=`
- PostGIS `bali_zoning_layers` (ST_Contains)

---

## Funzionalità principali

### 1. Selezione punto sulla mappa

Click su qualsiasi punto della mappa 3D → avvia l'analisi della zona.

### 2. Ricerca per indirizzo (Google Places Autocomplete)

Digitare un nome di luogo o via nella search bar → dropdown suggerimenti → selezione naviga e analizza.

**Restrizioni:** `componentRestrictions: { country: "id" }` — solo Indonesia.

### 3. Ricerca per coordinate (feature 2026-03-12)

Digitare coordinate decimali direttamente nella search bar e premere **Enter**.

**Formati supportati:**

```
-8.644590, 115.148143    # con virgola
-8.644590 115.148143     # con spazio
```

**Regex usato:**

```typescript
/^(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$/;
```

**Validazione:**

- `lat` deve essere in `[-90, 90]`
- `lng` deve essere in `[-180, 180]`
- Valori fuori range → nessuna azione (fail silenzioso)

**Comportamento:** La mappa naviga alle coordinate, centra a quota 300m, tilt 65°, range 1200m, e avvia l'analisi della zona.

### 4. Reverse geocoding

Ogni punto selezionato (via click o coordinate) viene sottoposto a reverse geocoding via Google Geocoding API per mostrare il nome della via nel pannello laterale.

### 5. Pannello laterale — dati zona

Accordion collassabile con sezioni:

- **Location** — via, subdistrict, district, coordinate
- **Zone** — codice zona, nome, descrizione, risk level
- **What you can open** — attività KBLI consentite (o avviso zona protetta)
- **Development Limits** — KDB%, altezza max, KDH%
- **Overlays & Risks** — KKOP aviation, LP2B farmland, tsunami, heritage
- **Land Price** — prezzo medio stimato per are
- **Latest Intel** — articoli di intelligence rilevanti

### 6. Chat Zantara

Tab "Ask Zantara" — chat contestuale con il risultato della zona corrente passato come contesto.

### 7. Layer controls

Filtri per attivare/disattivare: Zone colors, Aviation zones (KKOP), Protected farmland (LP2B).

---

## Copertura dati

| Area                                                                 | Copertura          |
| -------------------------------------------------------------------- | ------------------ |
| Kabupaten Badung (Kuta, Seminyak, Canggu, Jimbaran, Uluwatu, Mengwi) | ✅ Completa        |
| Denpasar, Ubud, Gianyar, Tabanan                                     | ❌ Fuori copertura |

Le coordinate fuori copertura restituiscono `status: "outside_coverage"` con messaggio esplicativo.

---

## API Backend

```
GET /api/prime/zoning?lat={lat}&lng={lng}
```

**Response `status: "found"`:**

```json
{
  "status": "found",
  "district": "Kuta",
  "subdistrict": "Legian",
  "zone_code": "W-2",
  "zone_name": "Tourism W-2",
  "zone_label_en": "Tourism Zone (Type 2)",
  "zone_color_hex": "#f59e0b",
  "zone_type": "tourism",
  "zone_description_en": "Secondary tourism area — boutique stays, restaurants",
  "is_restricted": false,
  "businesses": [...],
  "building_codes": { "kdb_pct": 60, "height_limit": "15 Meter", ... },
  "overlays": { "kkop": null, "lp2b": null, "tsunami": null },
  "risk_score": 0.2,
  "avg_price_per_are": 450000000,
  "intel_articles": [...],
  "source": "BATARA/Badung DPUPR (official)"
}
```

---

## Codici zona comuni

| Codice | Nome                       | Tipo                       |
| ------ | -------------------------- | -------------------------- |
| `W-1`  | Tourism Zone (Type 1)      | Tourism principale         |
| `W-2`  | Tourism Zone (Type 2)      | Tourism secondario         |
| `P-1`  | Crop Farming Zone          | Agricolo protetto          |
| `R-1`  | Low Density Residential    | Residenziale bassa densità |
| `R-2`  | Medium Density Residential | Residenziale media densità |
| `K-1`  | Primary Commercial Zone    | Commerciale primario       |
| `SPU`  | Public Service Zone        | Servizi pubblici           |

---

## Maps API Key

```
`GEMINI_API_KEY` (placeholder)
```

Nota: la `l` in `Mlq9El8` è minuscola (comune fonte di errori di copia).

---

## Aggiornamenti recenti

| Data       | Modifica                                                                            |
| ---------- | ----------------------------------------------------------------------------------- |
| 2026-03-12 | Aggiunto supporto input coordinate decimali nella search bar (Enter per confermare) |
| 2026-03-01 | Prima release pubblica su `prime.balizero.com`                                      |
