import streamlit as st
import requests
import pandas as pd
import folium
from folium import GeoJson, GeoJsonTooltip, LayerControl
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
import pyotp
import time
import json
import glob
import os

# --- CONFIGURAZIONE ---
API_URL = "http://127.0.0.1:8000"
TIMEOUT_SECS = 30 * 60  # 30 Minuti

st.set_page_config(page_title="Nuzantara Prime", layout="wide", page_icon="💎")

# --- GATEKEEPER SYSTEM ---
MASTER_KEY = "CFBNKDIYV22K7RFPA7USEBP3ON7FP24Q"

def check_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = 0

    if st.session_state.authenticated:
        now = time.time()
        elapsed = now - st.session_state.last_activity
        if elapsed > TIMEOUT_SECS:
            st.session_state.authenticated = False
            st.warning("⏱️ Sessione scaduta. Rilogga.")
            time.sleep(2)
            st.rerun()
        st.session_state.last_activity = now

    if not st.session_state.authenticated:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>💎 Nuzantara Prime</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Secure Intelligence Access</p>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            code_input = st.text_input("Codice Sicurezza", max_chars=6, type="password")
            if st.button("ACCEDI AL SISTEMA", use_container_width=True):
                try:
                    totp = pyotp.TOTP(MASTER_KEY)
                    if totp.verify(code_input, valid_window=1):
                        st.session_state.authenticated = True
                        st.session_state.last_activity = time.time()
                        st.rerun()
                    else:
                        st.error("⛔ Accesso Negato.")
                except Exception:
                    st.error("⚠️ Configurazione Chiave Errata")
        return False
    return True

if not check_session():
    st.stop()

# ==========================================
# WAR ROOM
# ==========================================

st.sidebar.title("💎 PRIME")
st.sidebar.caption("Status: ONLINE 🟢")

if st.sidebar.button("🔒 Disconnetti"):
    st.session_state.authenticated = False
    st.rerun()

mode = st.sidebar.radio("Modulo:", ["📍 Land Intel", "🧭 Zone Finder", "🧮 ROI Calculator", "🛰️ Geo-Compare"])


@st.cache_data(ttl=600)
def get_zones():
    try:
        return requests.get(f"{API_URL}/zones", timeout=5).json()
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def load_rdtr_geojson(kecamatan_filter: str = "all"):
    """Carica i GeoJSON RDTR di Badung (tutti i kecamatan o uno specifico)."""
    geojson_dir = "/Users/nuzantara/Desktop/harvested_zones/badung_full"
    if kecamatan_filter == "all":
        files = glob.glob(os.path.join(geojson_dir, "*.json"))
    else:
        files = glob.glob(os.path.join(geojson_dir, f"{kecamatan_filter}_*.json"))
    features = []
    for fpath in files:
        try:
            with open(fpath) as f:
                d = json.load(f)
            for feat in d.get("features", []):
                zone = feat["properties"].get("attribute", {}).get("zone", {})
                feat["properties"]["_zone_code"] = zone.get("code", "N/A")
                feat["properties"]["_zone_name"] = zone.get("name", "N/A")
                feat["properties"]["_zone_color"] = zone.get("color", "200 200 200")
                features.append(feat)
        except Exception:
            continue
    return {"type": "FeatureCollection", "features": features}


def batara_color_to_hex(color_str: str, alpha: float = 0.5) -> tuple[str, float]:
    """Converte 'R G B' o 'R,G,B' in hex e restituisce (hex, opacity)."""
    try:
        parts = color_str.replace(",", " ").split()
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        return f"#{r:02x}{g:02x}{b:02x}", alpha
    except Exception:
        return "#aaaaaa", alpha


zones = get_zones()
zone_options = list(zones.keys()) if zones else []

if not zone_options:
    st.sidebar.error("API Offline — avvia main.py")

# ─────────────────────────────────────────────────────────
# MODULO 0: LAND INTEL
# ─────────────────────────────────────────────────────────
if mode == "📍 Land Intel":
    st.title("📍 Land Intel")
    st.caption("Inserisci le coordinate GPS di un terreno. Il sistema interroga BATARA live e calcola tutto.")

    col_in, col_map = st.columns([1, 1.5])

    with col_in:
        st.subheader("Localizzazione")
        lat_in = st.number_input("Latitudine", value=-8.64780, format="%.6f", key="li_lat")
        lon_in = st.number_input("Longitudine", value=115.13200, format="%.6f", key="li_lon")

        st.subheader("Dati Terreno")
        li_size = st.number_input("Superficie (m²)", min_value=50, max_value=50_000, value=500, step=50, key="li_size")
        li_price = st.number_input("Prezzo Richiesto (IDR)", min_value=100_000_000,
                                   max_value=500_000_000_000, value=3_250_000_000,
                                   step=50_000_000, format="%d", key="li_price")

        btn_intel = st.button("🔍 ANALIZZA TERRENO", use_container_width=True, type="primary")

    with col_map:
        st.subheader("Mappa")
        m_li = folium.Map(
            location=[lat_in, lon_in],
            zoom_start=16,
            tiles=None,
        )

        # Base layer 1: Satellite Esri
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="🛰️ Satellite",
            overlay=False,
            control=True,
        ).add_to(m_li)

        # Base layer 2: OSM con strade
        folium.TileLayer(
            tiles="OpenStreetMap",
            name="🗺️ Strade (OSM)",
            overlay=False,
            control=True,
        ).add_to(m_li)

        # Overlay: etichette strade Esri sopra satellite
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="🔤 Nomi strade (su satellite)",
            overlay=True,
            control=True,
            opacity=0.8,
        ).add_to(m_li)

        # Layer RDTR locale
        rdtr_li = load_rdtr_geojson("Kuta Utara")

        def rdtr_style_li(feature):
            color_str = feature["properties"].get("_zone_color", "200 200 200")
            hex_color, _ = batara_color_to_hex(color_str)
            return {"fillColor": hex_color, "color": hex_color, "weight": 0.8, "fillOpacity": 0.35}

        GeoJson(
            rdtr_li,
            name="Zone RDTR",
            style_function=rdtr_style_li,
            tooltip=GeoJsonTooltip(
                fields=["_zone_code", "_zone_name"],
                aliases=["Zona:", "Nome:"],
                sticky=True,
                style="font-size:12px; font-weight:bold;",
            ),
        ).add_to(m_li)

        # Pin terreno
        folium.Marker(
            [lat_in, lon_in],
            popup=folium.Popup(f"<b>Terreno</b><br>{li_size} m²", max_width=200),
            tooltip="Terreno analizzato",
            icon=folium.Icon(color="green", icon="crosshairs", prefix="fa"),
        ).add_to(m_li)

        Fullscreen(position="topleft", title="Fullscreen", title_cancel="Esci").add_to(m_li)
        LayerControl(collapsed=False).add_to(m_li)
        st_folium(m_li, height=480, use_container_width=True)

    # ANALISI LIVE
    if btn_intel:
        with st.spinner("Interrogazione BATARA in corso..."):
            try:
                batara_payload = {"x": lon_in, "y": lat_in, "informationType": "RDTR"}
                batara_headers = {
                    "Content-Type": "application/json",
                    "Referer": "https://app.batara.badungkab.go.id/",
                    "Origin": "https://app.batara.badungkab.go.id",
                    "User-Agent": "Mozilla/5.0",
                }
                br = requests.post(
                    "https://secure.pelayanan-dpupr.badungkab.go.id/api/certificate/point",
                    json=batara_payload, headers=batara_headers, timeout=12
                )
                bd = br.json().get("data", {})
                geom_list = bd.get("territorials", {}).get("geom", [])

                if not geom_list:
                    st.error("BATARA non ha restituito dati per queste coordinate. Prova a spostare il punto.")
                    st.stop()

                geom0 = geom_list[0]
                zone = geom0.get("zone", {})
                location = geom0.get("location", {})
                reqs = zone.get("zone_intensity_requirements", [])
                req = reqs[0] if reqs else {}

                zone_code = zone.get("code", "N/A")
                zone_name = zone.get("name", "N/A")
                zone_def  = zone.get("definition", "")
                desa      = location.get("name", "N/A")
                kdb       = req.get("maximum_kdb", "N/A")
                klb       = req.get("maximum_klb", "N/A")
                kdh       = req.get("mininum_kdh", "N/A")
                tb        = req.get("old_building_height", "N/A")
                gsb       = req.get("old_minimum_gsb", "N/A")

                st.divider()

                # Header zona con colore BATARA
                zone_color_str = zone.get("color", "180 180 180")
                hex_col, _ = batara_color_to_hex(zone_color_str)
                st.markdown(f"""
                <div style="background:{hex_col}33; padding:14px; border-radius:8px;
                            border-left:6px solid {hex_col}; margin-bottom:16px;">
                    <h2 style="margin:0">{zone_code} — {zone_name}</h2>
                    <p style="margin:4px 0 0 0; color:#555; font-size:0.9em">{desa} &nbsp;|&nbsp; {zone_def[:120]}{"..." if len(zone_def)>120 else ""}</p>
                </div>
                """, unsafe_allow_html=True)

                # Parametri urbanistici
                col_urb, col_roi = st.columns(2)
                with col_urb:
                    st.subheader("Parametri Urbanistici (BATARA live)")
                    u1, u2, u3, u4 = st.columns(4)
                    u1.metric("KDB", kdb)
                    u2.metric("KLB", klb)
                    u3.metric("KDH", kdh)
                    u4.metric("Altezza Max", tb)
                    st.caption(f"GSB: {gsb}")

                with col_roi:
                    st.subheader("ROI Proiettato")
                    if zone_code in [z for z in zone_options]:
                        try:
                            roi_payload = {
                                "land_size_m2": li_size,
                                "price_total_idr": li_price,
                                "zone_code": zone_code,
                            }
                            rr = requests.post(f"{API_URL}/calculator",
                                               json=roi_payload, timeout=10).json()
                            gs = rr.get("golden_strategy", {})
                            urb = rr.get("urbanistica", {})
                            st.metric("ROI Ottimale", f"{gs.get('roi', 0):.2f}%")
                            st.metric("Break Even", f"{gs.get('bey', 0):.1f} anni")
                            st.info(f"**{gs.get('build')}** + **{gs.get('yield')}**")
                            st.caption(f"Buildable: {urb.get('max_build_m2')} m²  |  Footprint: {urb.get('max_footprint')} m²")
                        except Exception:
                            st.warning("Calcolo ROI non disponibile per questa zona.")
                    else:
                        st.warning(f"Zona {zone_code} non nel database ROI (non edificabile o non residenziale).")

                # Sensitivity matrix
                if zone_code in zone_options:
                    st.subheader("Sensitivity Matrix — ROI Netto")
                    try:
                        matrix = rr.get("sensitivity_matrix", {})
                        rows = []
                        for bk, yields in matrix.items():
                            row = {"Costo Costruzione": bk.replace("_", " ")}
                            for yk, mv in yields.items():
                                roi_v = mv["roi_pct"]
                                tag = " 🔥" if roi_v >= 12 else " ✅" if roi_v >= 8 else " 🟡" if roi_v >= 4 else " 🔴"
                                row[yk.replace("_", " ")] = f"{roi_v:.2f}%{tag}"
                            rows.append(row)
                        st.table(pd.DataFrame(rows).set_index("Costo Costruzione"))
                    except Exception:
                        pass

                # Extra layers info
                extra_fields = {
                    "kkop_1": "KKOP (Zona Aeroporto)",
                    "lp2b_2": "LP2B (Lahan Pertanian)",
                    "krb_03": "KRB (Rawan Bencana)",
                    "teb_05": "Sempadan Tebing",
                    "cagbud": "Cagar Budaya",
                    "resair": "Resapan Air",
                }
                vincoli = {label: geom0.get(field) for field, label in extra_fields.items()
                           if geom0.get(field) not in (None, "", "0", 0)}
                if vincoli:
                    with st.expander("⚠️ Vincoli e Overlay rilevati"):
                        for label, val in vincoli.items():
                            st.markdown(f"- **{label}**: {val}")
                else:
                    st.success("Nessun vincolo overlay rilevato (KKOP, LP2B, KRB, ecc.)")

            except requests.exceptions.Timeout:
                st.error("BATARA non risponde. Riprova tra qualche secondo.")
            except Exception as e:
                st.error(f"Errore: {e}")

# ─────────────────────────────────────────────────────────
# MODULO 1: FINDER
# ─────────────────────────────────────────────────────────
elif mode == "🧭 Zone Finder":
    st.title("🧭 Opportunity Finder")
    st.caption("Identifica gli asset con il miglior profilo rischio/rendimento per il budget disponibile.")

    col1, col2 = st.columns(2)
    with col1:
        budget = st.slider("Budget Totale (USD)", 50_000, 1_000_000, 250_000, step=10_000,
                           format="$%d")
    with col2:
        min_roi = st.slider("Target ROI Minimo (%)", 5.0, 20.0, 10.0, step=0.5)

    if st.button("🔍 Avvia Scansione", use_container_width=True):
        with st.spinner("Scansione database in corso..."):
            try:
                payload = {"budget_usd": budget, "min_roi": min_roi}
                resp = requests.post(f"{API_URL}/finder", json=payload, timeout=15).json()
                hits = resp.get("top_opportunities", [])

                if hits:
                    st.success(f"Identificati {resp['found']} asset compatibili. Visualizzati Top {min(10, len(hits))}.")
                    df = pd.DataFrame(hits)
                    display_cols = {
                        "zone_code": "Zona",
                        "zone_name": "Denominazione",
                        "land_are": "Are",
                        "roi_pct": "ROI (%)",
                        "break_even_years": "Break Even (y)",
                        "total_investment_usd": "Investimento ($)",
                        "net_annual_usd": "Net Annuo ($)",
                        "rating": "Rating",
                    }
                    df_display = df[[c for c in display_cols if c in df.columns]].rename(columns=display_cols)
                    st.dataframe(
                        df_display.style.format({
                            "ROI (%)": "{:.2f}%",
                            "Break Even (y)": "{:.1f}y",
                            "Investimento ($)": "${:,.0f}",
                            "Net Annuo ($)": "${:,.0f}",
                        }),
                        use_container_width=True,
                    )

                    avoid = resp.get("zones_to_avoid", [])
                    if avoid:
                        with st.expander("⚠️ Zone da escludere con questo budget"):
                            for z in avoid:
                                st.markdown(f"**{z['zone_code']}** — {z['zone_name']}: {z['reason']}")
                else:
                    st.warning("Nessun target trovato. Aumenta il budget o abbassa il target ROI.")
            except Exception as e:
                st.error(f"Errore connessione API: {e}")

# ─────────────────────────────────────────────────────────
# MODULO 2: CALCULATOR
# ─────────────────────────────────────────────────────────
elif mode == "🧮 ROI Calculator":
    st.title("🧮 Deep Financial Analysis")
    st.caption("Sensitivity matrix 3×3: costo costruzione vs rendimento da affitto.")

    c1, c2, c3 = st.columns(3)
    with c1:
        zone = st.selectbox("Zona Urbanistica", zone_options)
    with c2:
        size = st.number_input("Superficie (m²)", min_value=100, max_value=10_000, value=500, step=50)
    with c3:
        price = st.number_input(
            "Prezzo Totale Terreno (IDR)",
            min_value=100_000_000,
            max_value=100_000_000_000,
            value=3_250_000_000,
            step=50_000_000,
            format="%d",
        )

    if st.button("Genera Sensitivity Matrix", use_container_width=True):
        with st.spinner("Calcolo in corso..."):
            payload = {"land_size_m2": size, "price_total_idr": price, "zone_code": zone}
            try:
                resp = requests.post(f"{API_URL}/calculator", json=payload, timeout=15).json()

                zi = resp.get("zone_info", {})
                urb = resp.get("urbanistica", {})
                gs = resp.get("golden_strategy", {})

                col_u, col_g = st.columns(2)
                with col_u:
                    st.subheader("Parametri Urbanistici")
                    st.markdown(f"""
                    | Parametro | Valore |
                    |-----------|--------|
                    | Zona | **{zi.get('code')} — {zi.get('name')}** |
                    | KDB | {zi.get('KDB')} |
                    | KLB | {zi.get('KLB')} |
                    | KDH | {zi.get('KDH')} |
                    | Altezza Max | {zi.get('TB')} |
                    | Footprint Max | {urb.get('max_footprint')} m² |
                    | Superficie Costruibile | {urb.get('max_build_m2')} m² |
                    | Verde Minimo | {urb.get('green_min_m2')} m² |
                    """)
                with col_g:
                    st.subheader("Strategia Ottimale")
                    st.metric("ROI Massimo Attingibile", f"{gs.get('roi', 0):.2f}%")
                    st.metric("Break Even", f"{gs.get('bey', 0):.1f} anni")
                    st.info(f"**{gs.get('build')}** + **{gs.get('yield')}**")

                st.subheader("Sensitivity Matrix — ROI Netto")
                matrix = resp.get("sensitivity_matrix", {})
                rows = []
                for bk, yields in matrix.items():
                    row = {"Costo Costruzione": bk.replace("_", " ")}
                    for yk, m in yields.items():
                        roi = m["roi_pct"]
                        tag = " 🔥" if roi >= 12 else " ✅" if roi >= 8 else " 🟡" if roi >= 4 else " 🔴"
                        row[yk.replace("_", " ")] = f"{roi:.2f}%{tag}"
                    rows.append(row)
                st.table(pd.DataFrame(rows).set_index("Costo Costruzione"))

            except Exception as e:
                st.error(f"Errore calcolo: {e}")

# ─────────────────────────────────────────────────────────
# MODULO 3: GEO-COMPARE (SATELLITE)
# ─────────────────────────────────────────────────────────
elif mode == "🛰️ Geo-Compare":
    st.title("🛰️ Analisi Comparativa Geospaziale")
    st.caption("Confronto quantitativo tra due asset su mappa satellitare ad alta definizione.")

    col_params, col_map = st.columns([1, 1.5])

    with col_params:
        st.subheader("Parametri Asset")
        t1, t2 = st.tabs(["Asset A (Blu)", "Asset B (Rosso)"])

        with t1:
            zA = st.selectbox("Zona A", zone_options, key="zA")
            sA = st.number_input("Superficie A (m²)", min_value=100, value=500, key="sA")
            pA = st.number_input("Prezzo A (IDR)", min_value=100_000_000, value=3_250_000_000,
                                 step=50_000_000, format="%d", key="pA")
            st.markdown("**Coordinate GPS**")
            latA = st.number_input("Lat A", value=-8.64300, format="%.5f", key="latA")
            lonA = st.number_input("Lon A", value=115.14100, format="%.5f", key="lonA")

        with t2:
            zB_idx = min(1, len(zone_options) - 1)
            zB = st.selectbox("Zona B", zone_options, index=zB_idx, key="zB")
            sB = st.number_input("Superficie B (m²)", min_value=100, value=500, key="sB")
            pB = st.number_input("Prezzo B (IDR)", min_value=100_000_000, value=9_000_000_000,
                                 step=50_000_000, format="%d", key="pB")
            st.markdown("**Coordinate GPS**")
            latB = st.number_input("Lat B", value=-8.65300, format="%.5f", key="latB")
            lonB = st.number_input("Lon B", value=115.12300, format="%.5f", key="lonB")

        btn_calc = st.button("CALCOLA DELTA", use_container_width=True, type="primary")

    with col_map:
        st.subheader("Vista Satellitare + Zone RDTR")

        kec_options = {
            "Kuta Utara (default)": "Kuta Utara",
            "Kuta": "Kuta",
            "Kuta Selatan": "Kuta Selatan",
            "Mengwi": "Mengwi",
            "Abiansemal": "Abiansemal",
            "Petang": "Petang",
            "Tutta Badung (lento)": "all",
        }
        kec_sel = st.selectbox("Carica zone RDTR per:", list(kec_options.keys()), key="kec_filter")
        kec_filter = kec_options[kec_sel]

        center_lat = (latA + latB) / 2
        center_lon = (lonA + lonB) / 2

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=14,
            tiles=None,
        )

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="🛰️ Satellite",
            overlay=False,
            control=True,
        ).add_to(m)

        folium.TileLayer(
            tiles="OpenStreetMap",
            name="🗺️ Strade (OSM)",
            overlay=False,
            control=True,
        ).add_to(m)

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="🔤 Nomi strade (su satellite)",
            overlay=True,
            control=True,
            opacity=0.8,
        ).add_to(m)

        # Layer RDTR — poligoni di zona sovrapposti alla satellite
        rdtr_data = load_rdtr_geojson(kec_filter)

        def rdtr_style(feature):
            color_str = feature["properties"].get("_zone_color", "200 200 200")
            hex_color, _ = batara_color_to_hex(color_str)
            return {
                "fillColor": hex_color,
                "color": hex_color,
                "weight": 0.8,
                "fillOpacity": 0.35,
            }

        GeoJson(
            rdtr_data,
            name="Zone RDTR",
            style_function=rdtr_style,
            tooltip=GeoJsonTooltip(
                fields=["_zone_code", "_zone_name"],
                aliases=["Zona:", "Denominazione:"],
                localize=True,
                sticky=True,
                style="font-size:12px; font-weight:bold;",
            ),
        ).add_to(m)

        # Pin A — Blu
        folium.Marker(
            [latA, lonA],
            popup=folium.Popup(f"<b>Asset A</b><br>Zona: {zA}<br>{sA} m²", max_width=200),
            tooltip="Asset A",
            icon=folium.Icon(color="blue", icon="home", prefix="fa"),
        ).add_to(m)

        # Pin B — Rosso
        folium.Marker(
            [latB, lonB],
            popup=folium.Popup(f"<b>Asset B</b><br>Zona: {zB}<br>{sB} m²", max_width=200),
            tooltip="Asset B",
            icon=folium.Icon(color="red", icon="home", prefix="fa"),
        ).add_to(m)

        # Linea bianca tra i due asset
        folium.PolyLine(
            locations=[[latA, lonA], [latB, lonB]],
            color="white",
            weight=2,
            opacity=0.8,
            dash_array="6",
            tooltip="Distanza tra asset",
        ).add_to(m)

        Fullscreen(position="topleft", title="Fullscreen", title_cancel="Esci").add_to(m)
        LayerControl(collapsed=False).add_to(m)

        st_folium(m, height=520, use_container_width=True)

    # RISULTATI ANALITICI
    if btn_calc:
        payload = {
            "option_a": {"land_size_m2": sA, "price_total_idr": pA, "zone_code": zA},
            "option_b": {"land_size_m2": sB, "price_total_idr": pB, "zone_code": zB},
        }
        with st.spinner("Analisi differenziale in corso..."):
            try:
                resp = requests.post(f"{API_URL}/compare", json=payload, timeout=15).json()
                winner  = resp["winner"]
                comp    = resp["comparison"]
                verdict = resp["verdict"]

                st.divider()

                # Verdetto banner
                if winner == "TIE":
                    bg, border, label = "rgba(255,243,205,0.6)", "orange", "Pareggio Tecnico"
                elif winner == "A":
                    bg, border, label = "rgba(209,231,221,0.6)", "green", "Asset A Dominante"
                else:
                    bg, border, label = "rgba(248,215,218,0.6)", "red", "Asset B Dominante"

                st.markdown(f"""
                <div style="background:{bg}; padding:16px; border-radius:8px;
                            border-left:5px solid {border}; margin-bottom:16px;">
                    <h3 style="margin:0 0 6px 0">{label}</h3>
                    <p style="margin:0; color:#444">{verdict}</p>
                </div>
                """, unsafe_allow_html=True)

                # Metriche — riga 1
                k1, k2, k3, k4 = st.columns(4)
                roi_delta = comp["roi_best_scenario"]["delta"]
                bey_delta = comp["break_even_years"]["delta"]

                k1.metric("ROI Netto — A", comp["roi_best_scenario"]["A"],
                          delta=roi_delta if winner == "A" else None)
                k2.metric("ROI Netto — B", comp["roi_best_scenario"]["B"],
                          delta=roi_delta if winner == "B" else None)
                k3.metric("Break Even — A", comp["break_even_years"]["A"])
                k4.metric("Break Even — B", comp["break_even_years"]["B"])

                # Metriche — riga 2
                k5, k6, k7, k8 = st.columns(4)
                k5.metric("Investimento — A", comp["total_investment"]["A"])
                k6.metric("Investimento — B", comp["total_investment"]["B"])
                k7.metric("Net Annuo — A", comp["net_annual"]["A"])
                k8.metric("Net Annuo — B", comp["net_annual"]["B"])

                # Scenario detail
                with st.expander("📊 Dettaglio tutti gli scenari"):
                    scenario_data = {
                        "Scenario": ["Ottimale (Budget + Airbnb Pro)",
                                     "Medio (Standard + Airbnb Avg)",
                                     "Conservativo (Luxury + Long Term)"],
                        "ROI A": [comp["roi_best_scenario"]["A"],
                                  resp["mid_scenario"]["roi"]["A"],
                                  resp["worst_scenario"]["roi"]["A"]],
                        "ROI B": [comp["roi_best_scenario"]["B"],
                                  resp["mid_scenario"]["roi"]["B"],
                                  resp["worst_scenario"]["roi"]["B"]],
                        "Break Even A": [comp["break_even_years"]["A"],
                                         resp["mid_scenario"]["bey"]["A"],
                                         resp["worst_scenario"]["bey"]["A"]],
                        "Break Even B": [comp["break_even_years"]["B"],
                                         resp["mid_scenario"]["bey"]["B"],
                                         resp["worst_scenario"]["bey"]["B"]],
                    }
                    st.table(pd.DataFrame(scenario_data).set_index("Scenario"))

                st.caption(f"Rating A: {comp['rating']['A']}  |  Rating B: {comp['rating']['B']}  |  "
                           f"Efficienza capitale A: {comp['capital_efficiency']['A']}  "
                           f"B: {comp['capital_efficiency']['B']}")

            except Exception as e:
                st.error(f"Errore analisi: {e}")
