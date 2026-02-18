# Land Intel Wave 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Aggiungere 6 feature a Land Intel: calcolatore valuta sidebar, elevazione, walk score, noise map, storico IDR/USD, CSV export.

**Architecture:** Tutto in `app_dashboard.py`. Nessun nuovo file. Le feature usano API gratuite già note (Overpass, Frankfurter, Open-Elevation) e pandas/Altair già disponibili. Ogni feature è un blocco indipendente inserito nel flusso esistente.

**Tech Stack:** Streamlit, Folium, requests, pandas, altair, OSM Overpass API, Frankfurter API, Open-Elevation API

---

### Task 1: Calcolatore valuta nella sidebar

**Files:**

- Modify: `app_dashboard.py` — sezione sidebar (dopo riga `mode = st.sidebar.radio(...)`)

**Step 1: Leggi il file per trovare il punto esatto**

```bash
grep -n "mode = st.sidebar.radio" /Users/nuzantara/Desktop/nuzantara/app_dashboard.py
```

**Step 2: Aggiungi il widget valuta**

Inserire dopo `mode = st.sidebar.radio(...)`:

```python
st.sidebar.divider()
st.sidebar.caption("💱 Cambio live")

@st.cache_data(ttl=3600)
def get_fx():
    try:
        r = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "IDR", "to": "USD,EUR"},
            timeout=5,
        )
        rates = r.json().get("rates", {})
        return rates.get("USD", 0), rates.get("EUR", 0)
    except Exception:
        return None, None

fx_usd, fx_eur = get_fx()
if fx_usd:
    st.sidebar.metric("1.000.000 IDR", f"${fx_usd * 1_000_000:.2f}")
    st.sidebar.metric("", f"€{fx_eur * 1_000_000:.2f}")
else:
    st.sidebar.caption("FX non disponibile")
```

**Step 3: Verifica visiva**

Riavvia Streamlit e controlla che nella sidebar appaiano i due metric con i cambi.

**Step 4: Commit**

```bash
git add app_dashboard.py
git commit -m "feat: calcolatore valuta IDR/USD/EUR in sidebar"
```

---

### Task 2: Conversione valuta sotto il campo prezzo in Land Intel

**Files:**

- Modify: `app_dashboard.py` — dopo `li_price = st.number_input(...)`

**Step 1: Trova il punto**

```bash
grep -n "li_price = st.number_input" /Users/nuzantara/Desktop/nuzantara/app_dashboard.py
```

**Step 2: Aggiungi conversione inline**

Inserire subito dopo `li_price = st.number_input(...)`:

```python
if fx_usd:
    st.caption(f"≈ ${li_price * fx_usd:,.0f} USD  |  €{li_price * fx_eur:,.0f} EUR")
```

**Step 3: Verifica**

Cambia il prezzo e controlla che la conversione si aggiorni in tempo reale.

**Step 4: Commit**

```bash
git add app_dashboard.py
git commit -m "feat: conversione valuta inline sotto campo prezzo"
```

---

### Task 3: Elevazione e rischio alluvione

**Files:**

- Modify: `app_dashboard.py` — dentro il blocco `if btn_intel:`, dopo i parametri urbanistici (dopo `st.caption(f"GSB: {gsb}")`)

**Step 1: Trova il punto**

```bash
grep -n "st.caption.*GSB" /Users/nuzantara/Desktop/nuzantara/app_dashboard.py
```

**Step 2: Aggiungi il blocco elevazione**

Inserire dopo `st.caption(f"GSB: {gsb}")`:

```python
# Elevazione
try:
    elev_r = requests.get(
        "https://api.open-elevation.com/api/v1/lookup",
        params={"locations": f"{lat_in},{lon_in}"},
        timeout=8,
    )
    elev_m = elev_r.json()["results"][0]["elevation"]

    if elev_m < 3:
        elev_risk = "⚠️ Rischio alluvione alto"
        elev_color = "#dc3545"
    elif elev_m < 8:
        elev_risk = "🟡 Zona bassa — verificare"
        elev_color = "#fd7e14"
    else:
        elev_risk = "✅ Elevazione sicura"
        elev_color = "#198754"

    # Stima vista mare: > 15m slm e distanza costa < 3km
    # Distanza Haversine dal punto medio litorale Badung (-8.723, 115.168)
    import math
    dlat = math.radians(lat_in - (-8.723))
    dlon = math.radians(lon_in - 115.168)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat_in)) * math.cos(math.radians(-8.723)) * math.sin(dlon/2)**2
    dist_coast_km = 6371 * 2 * math.asin(math.sqrt(a))
    sea_view = elev_m > 15 and dist_coast_km < 3

    e1, e2 = st.columns(2)
    e1.metric("Elevazione slm", f"{elev_m:.1f} m", delta=elev_risk, delta_color="off")
    e2.metric("Distanza costa", f"{dist_coast_km:.1f} km",
              delta="🌊 Possibile vista mare" if sea_view else None, delta_color="off")
except Exception:
    st.caption("Elevazione non disponibile.")
```

**Step 3: Sposta import math**

Verificare che `import math` non sia già presente in testa al file. Se non c'è, aggiungerlo tra gli import.

```bash
grep -n "^import math" /Users/nuzantara/Desktop/nuzantara/app_dashboard.py
```

Se assente, aggiungere dopo `import os`:

```python
import math
```

**Step 4: Verifica**

Inserire coordinate di Canggu (-8.6478, 115.1320) e verificare che appaia l'elevazione.

**Step 5: Commit**

```bash
git add app_dashboard.py
git commit -m "feat: elevazione slm e rischio alluvione via Open-Elevation"
```

---

### Task 4: Walk Score + Noise Map (OSM Overpass)

**Files:**

- Modify: `app_dashboard.py` — dentro `if btn_intel:`, dopo il blocco elevazione, prima del blocco BPN

**Step 1: Trova il punto**

```bash
grep -n "# ── BPN CATASTO" /Users/nuzantara/Desktop/nuzantara/app_dashboard.py
```

**Step 2: Inserire il blocco**

Inserire prima di `# ── BPN CATASTO`:

```python
# ── WALK SCORE + NOISE MAP ───────────────────────────────
st.subheader("🏃 Contesto Urbano")
try:
    overpass_url = "https://overpass-api.de/api/interpreter"
    q_context = f"""
[out:json][timeout:25];
(
  node["natural"="beach"](around:3000,{lat_in},{lon_in});
  node["shop"~"supermarket|convenience"](around:1000,{lat_in},{lon_in});
  node["amenity"~"hospital|clinic"](around:2000,{lat_in},{lon_in});
  node["amenity"="atm"](around:1000,{lat_in},{lon_in});
  node["amenity"~"restaurant|cafe"](around:500,{lat_in},{lon_in});
  node["amenity"="pharmacy"](around:1000,{lat_in},{lon_in});
  node["amenity"~"bar|pub|nightclub"](around:300,{lat_in},{lon_in});
  way["highway"~"primary|secondary"](around:150,{lat_in},{lon_in});
);
out count;
"""
    rq_ctx = requests.post(overpass_url, data={"data": q_context}, timeout=30)
    ctx_tags = rq_ctx.json()["elements"][0]["tags"] if rq_ctx.status_code == 200 else {}
    total_ctx = int(ctx_tags.get("total", 0))

    # Walk Score: stima pesata (cap 100)
    q_walk = f"""
[out:json][timeout:25];
(
  node["natural"="beach"](around:3000,{lat_in},{lon_in});
  node["shop"~"supermarket|convenience"](around:1000,{lat_in},{lon_in});
  node["amenity"~"hospital|clinic"](around:2000,{lat_in},{lon_in});
  node["amenity"="atm"](around:1000,{lat_in},{lon_in});
  node["amenity"="pharmacy"](around:1000,{lat_in},{lon_in});
);
out body;
"""
    rq_walk = requests.post(overpass_url, data={"data": q_walk}, timeout=30)
    walk_els = rq_walk.json().get("elements", []) if rq_walk.status_code == 200 else []

    beach = sum(1 for e in walk_els if e.get("tags", {}).get("natural") == "beach")
    supermarket = sum(1 for e in walk_els if "supermarket" in e.get("tags", {}).get("shop", "") or "convenience" in e.get("tags", {}).get("shop", ""))
    hospital = sum(1 for e in walk_els if "hospital" in e.get("tags", {}).get("amenity", "") or "clinic" in e.get("tags", {}).get("amenity", ""))
    atm = sum(1 for e in walk_els if e.get("tags", {}).get("amenity") == "atm")
    pharmacy = sum(1 for e in walk_els if e.get("tags", {}).get("amenity") == "pharmacy")

    walk_score = min(100, (
        min(beach, 2) * 20 +
        min(supermarket, 2) * 15 +
        min(hospital, 1) * 15 +
        min(atm, 3) * 10 +
        min(pharmacy, 2) * 10
    ))

    # Noise: bar/club/strade principali entro 300/150m
    q_noise = f"""
[out:json][timeout:15];
(
  node["amenity"~"bar|pub|nightclub"](around:300,{lat_in},{lon_in});
  way["highway"~"primary|secondary"](around:150,{lat_in},{lon_in});
);
out count;
"""
    rq_noise = requests.post(overpass_url, data={"data": q_noise}, timeout=20)
    noise_count = int(rq_noise.json()["elements"][0]["tags"].get("total", 0)) if rq_noise.status_code == 200 else 0

    if noise_count == 0:
        noise_label = "🟢 Silenzioso"
        noise_yield = "+3% yield stimato"
    elif noise_count <= 3:
        noise_label = "🟡 Moderato"
        noise_yield = "neutro"
    else:
        noise_label = "🔴 Rumoroso"
        noise_yield = "-5% yield stimato (vacanze brevi)"

    if walk_score >= 70:
        ws_label = "🟢 Eccellente"
    elif walk_score >= 40:
        ws_label = "🟡 Buono"
    else:
        ws_label = "🔴 Isolato"

    w1, w2 = st.columns(2)
    w1.metric("Walk Score", f"{walk_score}/100", delta=ws_label, delta_color="off")
    w2.metric("Livello Rumore", noise_label, delta=noise_yield, delta_color="off")

except Exception as ctx_err:
    st.caption(f"Contesto urbano non disponibile: {ctx_err}")
```

**Step 3: Verifica**

Testare con coordinate Seminyak (-8.6906, 115.1621) — dovrebbe avere walk score alto e noise moderato/alto.

**Step 4: Commit**

```bash
git add app_dashboard.py
git commit -m "feat: walk score e noise map via OSM Overpass"
```

---

### Task 5: Storico IDR/USD nel modulo ROI Calculator

**Files:**

- Modify: `app_dashboard.py` — modulo ROI Calculator, dopo `st.table(...)`

**Step 1: Trova il punto**

```bash
grep -n "st.table(pd.DataFrame(rows)" /Users/nuzantara/Desktop/nuzantara/app_dashboard.py
```

**Step 2: Aggiungi chart storico**

Inserire dopo `st.table(pd.DataFrame(rows).set_index("Costo Costruzione"))`:

```python
# Storico IDR/USD 12 mesi
with st.expander("📈 Storico IDR/USD — 12 mesi"):
    try:
        import altair as alt
        from datetime import date, timedelta
        start_date = (date.today() - timedelta(days=365)).isoformat()
        end_date = date.today().isoformat()
        hist_r = requests.get(
            f"https://api.frankfurter.app/{start_date}..{end_date}",
            params={"from": "USD", "to": "IDR"},
            timeout=10,
        )
        hist_data = hist_r.json().get("rates", {})
        if hist_data:
            hist_rows = [
                {"data": d, "IDR per 1 USD": v["IDR"]}
                for d, v in hist_data.items()
            ]
            hist_df = pd.DataFrame(hist_rows)
            hist_df["data"] = pd.to_datetime(hist_df["data"])
            chart = alt.Chart(hist_df).mark_line(color="#0d6efd").encode(
                x=alt.X("data:T", title="Data"),
                y=alt.Y("IDR per 1 USD:Q", scale=alt.Scale(zero=False)),
                tooltip=["data:T", "IDR per 1 USD:Q"],
            ).properties(height=200)
            st.altair_chart(chart, use_container_width=True)
            latest = hist_df["IDR per 1 USD"].iloc[-1]
            oldest = hist_df["IDR per 1 USD"].iloc[0]
            delta_pct = (latest - oldest) / oldest * 100
            st.caption(f"Variazione 12m: {delta_pct:+.1f}%  |  Attuale: {latest:,.0f} IDR/USD")
    except Exception:
        st.caption("Storico non disponibile.")
```

**Step 3: Verifica**

Aprire ROI Calculator, generare una sensitivity matrix, espandere il box storico.

**Step 4: Commit**

```bash
git add app_dashboard.py
git commit -m "feat: storico IDR/USD 12 mesi con Altair nel ROI Calculator"
```

---

### Task 6: CSV Export in Land Intel

**Files:**

- Modify: `app_dashboard.py` — in fondo al blocco `if btn_intel:`, dopo il blocco AI Assessment

**Step 1: Trova il punto**

```bash
grep -n "except requests.exceptions.Timeout" /Users/nuzantara/Desktop/nuzantara/app_dashboard.py
```

**Step 2: Aggiungi CSV export**

Inserire subito prima di `except requests.exceptions.Timeout:` (ma dentro il `try` principale):

```python
# ── CSV EXPORT ────────────────────────────────────────────
st.divider()
export_data = {
    "timestamp": [pd.Timestamp.now().isoformat()],
    "lat": [lat_in],
    "lon": [lon_in],
    "indirizzo": [st.session_state.get("geo_label", "")],
    "zona_code": [zone_code],
    "zona_name": [zone_name],
    "desa": [desa],
    "kdb": [kdb],
    "klb": [klb],
    "kdh": [kdh],
    "altezza_max": [tb],
    "superficie_m2": [li_size],
    "prezzo_idr": [li_price],
    "prezzo_usd": [round(li_price * fx_usd, 0) if fx_usd else None],
    "roi_pct": [gs.get("roi") if "gs" in locals() else None],
    "break_even_anni": [gs.get("bey") if "gs" in locals() else None],
    "bpn_tipehak": [bpn_feats[0].get("properties", {}).get("tipehak") if bpn_feats else None],
    "bpn_luas_m2": [bpn_feats[0].get("properties", {}).get("luas") if bpn_feats else None],
    "bpn_nomor": [bpn_feats[0].get("properties", {}).get("nomor") if bpn_feats else None],
    "vincoli": [", ".join(vincoli.keys()) if "vincoli" in locals() and vincoli else ""],
    "walk_score": [walk_score if "walk_score" in locals() else None],
    "noise_level": [noise_label if "noise_label" in locals() else None],
    "elevazione_m": [elev_m if "elev_m" in locals() else None],
    "densita_500m": [density_results.get("500m") if "density_results" in locals() else None],
    "densita_1km": [density_results.get("1km") if "density_results" in locals() else None],
    "densita_2km": [density_results.get("2km") if "density_results" in locals() else None],
}
export_df = pd.DataFrame(export_data)
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
fname = f"land_intel_{lat_in:.4f}_{lon_in:.4f}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv"
st.download_button("📥 Esporta dati CSV", data=csv_bytes, file_name=fname, mime="text/csv")
```

**Step 3: Verifica**

Eseguire un'analisi completa e cliccare il bottone. Verificare che il CSV scaricato contenga tutti i campi.

**Step 4: Commit**

```bash
git add app_dashboard.py
git commit -m "feat: CSV export da Land Intel con tutti i dati raccolti"
```

---

## Test finale end-to-end

1. Aprire `http://localhost:8501`
2. Login con TOTP
3. Sidebar: verificare widget cambio IDR/USD/EUR
4. Land Intel: cercare "Canggu Beach, Bali" → coordinate auto-popolate
5. Inserire size 500m², prezzo 3.250.000.000 IDR → verificare conversione valuta sotto campo
6. Click ANALIZZA TERRENO
7. Verificare in sequenza: parametri BATARA → elevazione → walk score + noise → BPN → densità → AI Assessment
8. Click "📥 Esporta dati CSV" → aprire il file e verificare tutti i campi
9. Modulo ROI Calculator: generare matrix → espandere storico IDR/USD
