import streamlit as st
import requests
import pandas as pd
import folium
from folium import GeoJson, GeoJsonTooltip, LayerControl
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
import time
import json
import glob
import os
import math

from i18n_dashboard import T, set_language, get_language

API_URL = "http://localhost:8000"
GMAPS_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "AIzaSyCWPZb1_aSV_NVvS9ZSR0Mlq9El8qO8uLQ")

st.set_page_config(page_title="Nuzantara Prime", layout="wide", page_icon="💎")


st.sidebar.title("💎 PRIME")
st.sidebar.caption(T("sidebar_status"))

# ── Language Selector ─────────────────────────────────────────────────
_lang_options = {"🇮🇹 Italiano": "it", "🇬🇧 English": "en", "🇮🇩 Indonesia": "id"}
_lang_label = st.sidebar.selectbox(
    "🌐",
    list(_lang_options.keys()),
    index=list(_lang_options.values()).index(st.session_state.get("lang", "it")),
    key="lang_select",
)
_selected_lang = _lang_options[_lang_label]
st.session_state["lang"] = _selected_lang
set_language(_selected_lang)

mode = st.sidebar.radio(T("sidebar_module"), ["📍 Land Intel", "🧭 Zone Finder", "🧮 ROI Calculator", "🛰️ Geo-Compare", "📌 Saved Parcels"])

st.sidebar.divider()
st.sidebar.caption(T("sidebar_fx"))

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
    st.sidebar.caption(T("sidebar_fx_unavailable"))

# ── Dashboard Stats (sidebar) ────────────────────────────────────────
st.sidebar.divider()
st.sidebar.caption(T("sidebar_stats"))

@st.cache_data(ttl=120)
def get_dashboard_stats():
    try:
        r = requests.get(f"{API_URL}/api/dashboard/map/stats", timeout=5)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

_stats = get_dashboard_stats()
if _stats and not _stats.get("error"):
    st.sidebar.metric(T("sidebar_active_clients"), _stats.get("total_clients", 0))
    st.sidebar.metric(T("sidebar_open_practices"), _stats.get("total_practices", 0))
    st.sidebar.metric(T("sidebar_lookups_24h"), _stats.get("map_lookups_24h", 0))
else:
    st.sidebar.caption(T("sidebar_stats_unavailable"))


@st.cache_data(ttl=600)
def get_zones():
    try:
        return requests.get(f"{API_URL}/zones", timeout=5).json()
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_clients_geo():
    """Fetch active clients with addresses for CRM map layer."""
    try:
        r = requests.get(f"{API_URL}/api/dashboard/map/clients/geo", timeout=5)
        if r.status_code == 200:
            return r.json().get("clients", [])
        return []
    except Exception:
        return []


def _log_analytics_lookup(user_email: str, kbli_code: str = None, location: str = None, notes: str = None):
    """Silent POST to log a map lookup event. Non-blocking."""
    try:
        requests.post(
            f"{API_URL}/api/dashboard/map/analytics/log-lookup",
            json={
                "user_email": user_email or "dashboard_user",
                "kbli_code": kbli_code,
                "location": location,
                "notes": notes,
            },
            timeout=3,
        )
    except Exception:
        pass


@st.cache_data(ttl=3600)
def _simplify_coords(coords: list, tolerance: float = 0.0001) -> list:
    """Reduce polygon vertex count via Douglas-Peucker-like point skipping."""
    if len(coords) <= 6:
        return coords
    step = max(1, len(coords) // 40)
    simplified = coords[::step]
    if simplified[-1] != coords[-1]:
        simplified.append(coords[-1])
    return simplified


@st.cache_data(ttl=3600)
def load_rdtr_geojson(kecamatan_filter: str | tuple[str, ...] = "all"):
    geojson_dir = "/Users/nuzantara/Desktop/harvested_zones/badung_full"
    if kecamatan_filter == "all":
        files = glob.glob(os.path.join(geojson_dir, "*.json"))
    elif isinstance(kecamatan_filter, (list, tuple)):
        files = []
        for kec in kecamatan_filter:
            files.extend(glob.glob(os.path.join(geojson_dir, f"{kec}_*.json")))
    else:
        files = glob.glob(os.path.join(geojson_dir, f"{kecamatan_filter}_*.json"))
    features = []
    for fpath in files:
        try:
            with open(fpath) as f:
                d = json.load(f)
            for feat in d.get("features", []):
                zone = feat["properties"].get("attribute", {}).get("zone", {})
                feat["properties"] = {
                    "_zone_code": zone.get("code", "N/A"),
                    "_zone_name": zone.get("name", "N/A"),
                    "_zone_color": zone.get("color", "200 200 200"),
                }
                geom = feat.get("geometry", {})
                gtype = geom.get("type", "")
                if gtype == "Polygon":
                    geom["coordinates"] = [_simplify_coords(ring) for ring in geom["coordinates"]]
                elif gtype == "MultiPolygon":
                    geom["coordinates"] = [[_simplify_coords(ring) for ring in poly] for poly in geom["coordinates"]]
                features.append(feat)
        except Exception:
            continue
    return {"type": "FeatureCollection", "features": features}


OSM_ZONE_COLORS = {
    "residential": "#f4a460",
    "farmland": "#aad66b",
    "orchard": "#6dbf67",
    "beach": "#ffe066",
    "grass": "#c8e6c9",
    "wetland": "#80cbc4",
    "brownfield": "#bcaaa4",
    "construction": "#ff8a65",
    "industrial": "#b0bec5",
    "forest": "#388e3c",
    "meadow": "#dcedc8",
    "cemetery": "#9e9e9e",
    "park": "#81c784",
    "garden": "#a5d6a7",
    "resort": "#ce93d8",
    "hotel": "#ce93d8",
    "attraction": "#ffb74d",
    "zoo": "#ffb74d",
    "retail": "#ef9a9a",
    "commercial": "#ef9a9a",
    "swimming_pool": "#64b5f6",
    "pitch": "#4db6ac",
    "unknown": "#cccccc",
}


def point_in_polygon_osm(lat: float, lon: float, coords: list) -> bool:
    """Ray casting per verificare se un punto è dentro un poligono GeoJSON."""
    x, y = lon, lat
    n = len(coords)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = coords[i]
        xj, yj = coords[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _get_polygon_rings(geom: dict) -> list[list]:
    """Extract outer rings from Polygon or MultiPolygon geometry."""
    gtype = geom.get("type", "")
    if gtype == "Polygon":
        return [geom["coordinates"][0]]
    elif gtype == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def lookup_tabanan_zone(lat: float, lon: float) -> dict | None:
    """Cerca la zona OSM Tabanan per un punto lat/lon. Ritorna le properties o None."""
    data = load_tabanan_geojson()
    best = None
    best_dist = 9999.0
    for feat in data.get("features", []):
        geom = feat.get("geometry", {})
        rings = _get_polygon_rings(geom)
        if not rings:
            continue
        for coords in rings:
            if point_in_polygon_osm(lat, lon, coords):
                return feat["properties"]
        # fallback: distanza al centroide del primo ring
        coords = rings[0]
        cx = sum(c[0] for c in coords) / len(coords)
        cy = sum(c[1] for c in coords) / len(coords)
        dist = ((cx - lon) ** 2 + (cy - lat) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best = feat["properties"]
    if best_dist < 0.005:  # ~500m
        return best
    return None


@st.cache_data(ttl=3600)
def load_osm_geojson(directory: str, code_pattern: str, label: str, max_per_file: int = 3000):
    """Carica zone OSM da una directory di kecamatan.

    Generico: usato per Tabanan, Denpasar, ecc.
    max_per_file: cap features per file (evita crash su file da 80MB+).
    File ordinati per dimensione crescente — zone abitate caricate per intero.
    """
    files = sorted(
        glob.glob(os.path.join(directory, f"*_{code_pattern}.json")),
        key=os.path.getsize
    )
    features = []
    for fpath in files:
        try:
            with open(fpath) as f:
                d = json.load(f)
            file_features = d.get("features", [])
            if len(file_features) > max_per_file:
                file_features = file_features[:max_per_file]
            kec_name = os.path.basename(fpath).split("_")[0]
            for feat in file_features:
                props = feat.get("properties", {})
                zone_type = props.get("zone_type", props.get("landuse", props.get("leisure",
                            props.get("tourism", props.get("amenity", "unknown")))))
                props["_zone_code"] = zone_type[:4].upper() if zone_type else "UNKN"
                props["_zone_name"] = props.get("name", zone_type)
                props["_zone_color"] = OSM_ZONE_COLORS.get(zone_type, "#cccccc")
                props["_source"] = f"OSM / {label} ({kec_name})"
                features.append(feat)
        except Exception:
            continue
    return {"type": "FeatureCollection", "features": features}


def load_tabanan_geojson():
    return load_osm_geojson(
        "/Users/nuzantara/Desktop/harvested_zones/tabanan",
        "5106[0-9][0-9][0-9]",
        "Tabanan"
    )


def load_denpasar_geojson():
    return load_osm_geojson(
        "/Users/nuzantara/Desktop/harvested_zones/denpasar",
        "5171[0-9][0-9][0-9]",
        "Denpasar"
    )


def batara_color_to_hex(color_str: str, alpha: float = 0.5) -> tuple[str, float]:
    try:
        parts = color_str.replace(",", " ").split()
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        return f"#{r:02x}{g:02x}{b:02x}", alpha
    except Exception:
        return "#aaaaaa", alpha


import io
import psycopg2
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgres://backend_rag_v2:PASSWORD@localhost:15432/nuzantara_rag?sslmode=disable",
)

def get_pg_conn():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception:
        return None

def init_db():
    conn = get_pg_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
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
                )
            """)
            conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def generate_pdf(data: dict) -> bytes:
    """Generate dark-themed Land Intelligence Report PDF matching Bali Zero branding."""
    from reportlab.platypus import KeepTogether
    from reportlab.lib.colors import HexColor

    # ── Brand colours ────────────────────────────────────
    BG = HexColor("#1a1a2e")
    CARD = HexColor("#252540")
    CYAN = HexColor("#00d4ff")
    GREEN = HexColor("#4caf50")
    YELLOW = HexColor("#ffd600")
    RED = HexColor("#ff5252")
    WHITE = HexColor("#f0f0f0")
    GREY = HexColor("#999999")
    SECTION_BAR = HexColor("#ff3333")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    elems = []

    # ── Helper: dark card table ──────────────────────────
    def card_row(label: str, value, color=CYAN):
        val = str(value) if value not in (None, "", "None") else "\u2014"
        return [
            Paragraph(f'<font color="#999999" size="8">{label}</font>', styles["Normal"]),
            Paragraph(f'<font color="{color}" size="12"><b>{val}</b></font>', styles["Normal"]),
        ]

    def section_header(title: str):
        elems.append(Spacer(1, 0.4 * cm))
        t = Table(
            [[Paragraph(f'<font color="#ffffff" size="11"><b>{title}</b></font>', styles["Normal"])]],
            colWidths=[17 * cm],
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG),
            ("LEFTPADDING", (0, 0), (0, 0), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBEFORECOL", (0, 0), (0, -1), 3, SECTION_BAR),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 0.15 * cm))

    def card_table(rows, col_widths=None):
        if not col_widths:
            col_widths = [8.5 * cm, 8.5 * cm]
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CARD),
            ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#333355")),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        elems.append(t)

    def card_grid(items, cols=3):
        """items = [(label, value, color), ...]"""
        rows_data = []
        row = []
        cw = 17 * cm / cols
        for label, value, col in items:
            val = str(value) if value not in (None, "", "None") else "\u2014"
            cell = Paragraph(
                f'<font color="#999999" size="7">{label}</font><br/>'
                f'<font color="{col}" size="13"><b>{val}</b></font>',
                styles["Normal"],
            )
            row.append(cell)
            if len(row) == cols:
                rows_data.append(row)
                row = []
        if row:
            while len(row) < cols:
                row.append("")
            rows_data.append(row)
        t = Table(rows_data, colWidths=[cw] * cols)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CARD),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#333355")),
        ]))
        elems.append(t)

    # ── PAGE BACKGROUND ──────────────────────────────────
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BG)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    # ── HEADER ───────────────────────────────────────────
    desa = data.get("desa", "")
    header = Table(
        [[
            Paragraph(
                f'<font color="#ff3333" size="9">ZANTARA PRIME</font><br/>'
                f'<font color="#ffffff" size="18"><b>Land Intelligence Report</b></font><br/>'
                f'<font color="#999999" size="9">{data.get("timestamp", "")} WITA</font>',
                styles["Normal"],
            ),
            Paragraph(
                f'<font color="#ff3333" size="16"><b>BALI</b></font><br/>'
                f'<font color="#00d4ff" size="16"><b>ZERO</b></font>',
                ParagraphStyle("logo", parent=styles["Normal"], alignment=2),
            ),
        ]],
        colWidths=[13 * cm, 4 * cm],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elems.append(header)

    # Coordinate badge
    coord_text = f'\u25a0  {data.get("lat", 0):.6f}, {data.get("lon", 0):.6f}  \u2014  {desa}'
    coord_tbl = Table(
        [[Paragraph(f'<font color="#00d4ff" size="9">{coord_text}</font>', styles["Normal"])]],
        colWidths=[17 * cm],
    )
    coord_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#2a2a4a")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elems.append(coord_tbl)
    elems.append(Spacer(1, 0.2 * cm))

    # ── ZONA RDTR ────────────────────────────────────────
    section_header("ZONA RDTR (Tata Ruang)")
    card_grid([
        ("Kode Zona", data.get("zona_code"), CYAN),
        ("Nama Zona", data.get("zona_name"), CYAN),
        ("Desa", desa, WHITE),
    ])

    # ── PARAMETER TATA RUANG ─────────────────────────────
    section_header("PARAMETER TATA RUANG")
    card_grid([
        ("KDB", data.get("kdb"), CYAN),
        ("KLB", data.get("klb"), CYAN),
        ("KDH", data.get("kdh"), GREEN),
    ])
    card_grid([
        ("Tinggi Maks", data.get("tb"), YELLOW),
        ("GSB", data.get("gsb"), WHITE),
    ], cols=2)

    # ── ANALISI FINANSIAL ────────────────────────────────
    section_header("ANALISI FINANSIAL")
    prezzo_usd = f"USD ${data.get('prezzo_usd', 0):,.0f}" if data.get("prezzo_usd") else "\u2014"
    card_grid([
        ("Luas Tanah", f"{data.get('superficie_m2')} m\u00b2", CYAN),
        ("Harga (IDR)", f"IDR {data.get('prezzo_idr', 0):,.0f}", GREEN),
        ("Harga (USD)", prezzo_usd, GREEN),
    ])
    # Price per m2
    m2 = data.get("superficie_m2", 1) or 1
    idr_m2 = data.get("prezzo_idr", 0) / m2
    usd_m2 = data.get("prezzo_usd", 0) / m2 if data.get("prezzo_usd") else 0
    roi_str = f"ROI: {data.get('roi_pct', 0):.2f}% | Break-even: {data.get('break_even', 0):.1f} yr | {data.get('strategia', '')}" if data.get("roi_pct") else "\u2014"
    meta_row = Table(
        [[
            Paragraph(f'<font color="#999999" size="8">Harga per m\u00b2:</font>', styles["Normal"]),
            Paragraph(f'<font color="#ffd600" size="9"><b>IDR {idr_m2:,.0f} / m\u00b2  \u2248  USD ${usd_m2:,.0f} / m\u00b2</b></font>', styles["Normal"]),
            Paragraph(f'<font color="#999999" size="8">ROI / Break-even / Strategi: {roi_str}</font>', styles["Normal"]),
        ]],
        colWidths=[3.5 * cm, 7 * cm, 6.5 * cm],
    )
    meta_row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#333355")),
    ]))
    elems.append(meta_row)

    # ── BIDANG TANAH BPN ─────────────────────────────────
    section_header("BIDANG TANAH BPN")
    card_grid([
        ("Jenis Hak", data.get("bpn_tipehak"), YELLOW),
        ("Luas Sertifikat", f"{data.get('bpn_luas')} m\u00b2" if data.get("bpn_luas") else "\u2014", CYAN),
    ], cols=2)
    card_grid([
        ("Nomor Sertifikat", data.get("bpn_nomor"), WHITE),
        ("Tahun Terbit", data.get("bpn_tahun"), WHITE),
    ], cols=2)
    # Nota if area mismatch
    if data.get("bpn_luas") and data.get("superficie_m2") and data.get("bpn_luas") != data.get("superficie_m2"):
        note = Table(
            [[Paragraph(
                f'<font color="#ffd600" size="8">\u25a0 Nota: Luas dijual ({data.get("superficie_m2")} m\u00b2) \u2260 '
                f'luas sertifikat ({data.get("bpn_luas")} m\u00b2) \u2014 kemungkinan penjualan sebagian bidang (pemecahan).</font>',
                styles["Normal"],
            )]],
            colWidths=[17 * cm],
        )
        note.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#3a3500")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elems.append(note)

    # ── KONTEKS PERKOTAAN ────────────────────────────────
    section_header("KONTEKS PERKOTAAN")
    ws = f"{data.get('walk_score')}/100" if data.get("walk_score") is not None else "\u2014"
    elev = f"{data.get('elev_m'):.1f} m dpl" if data.get("elev_m") else "\u2014"
    coast = f"{data.get('dist_coast_km'):.1f} km" if data.get("dist_coast_km") else "\u2014"
    ws_color = RED if data.get("walk_score", 0) == 0 else (YELLOW if (data.get("walk_score") or 0) < 50 else GREEN)
    card_grid([
        ("Walk Score", ws, ws_color),
        ("Kebisingan", data.get("noise_label"), CYAN),
        ("Elevasi", elev, WHITE),
        ("Jarak Pantai", coast, CYAN),
    ], cols=4)
    # Elevation safe badge
    elev_val = data.get("elev_m") or 0
    if elev_val >= 5:
        badge_text = '\u2191 \u2705 Elevasi aman'
        badge_bg = HexColor("#1b3a1b")
    else:
        badge_text = '\u2193 \u26a0\ufe0f Elevasi rendah — risiko banjir'
        badge_bg = HexColor("#3a2a00")
    badge = Table(
        [[Paragraph(f'<font color="#ffffff" size="8">{badge_text}</font>', styles["Normal"])]],
        colWidths=[17 * cm],
    )
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), badge_bg),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elems.append(badge)

    # ── KENDALA OVERLAY ──────────────────────────────────
    section_header("KENDALA OVERLAY")
    vincoli = data.get("vincoli", [])
    overlay_names = {
        "KKOP": "Kawasan Keselamatan Operasi Penerbangan",
        "LP2B": "Lahan Pertanian Pangan Berkelanjutan",
        "KRB": "Kawasan Rawan Bencana",
        "Sempadan Tebing": "Sempadan Tebing",
        "Cagar Budaya": "Cagar Budaya",
        "HANKAM": "Kawasan Pertahanan Keamanan",
    }
    overlay_rows = []
    checked_overlays = {v for v in vincoli}
    for code, desc in overlay_names.items():
        is_active = code in checked_overlays
        status_text = f'<font color="#ff5252">\u26a0 Terdeteksi</font>' if is_active else f'<font color="#4caf50">\u2713 Aman</font>'
        overlay_rows.append([
            Paragraph(f'<font color="#cccccc" size="9">{code} \u2014 {desc}</font>', styles["Normal"]),
            Paragraph(status_text, ParagraphStyle("right", parent=styles["Normal"], alignment=2)),
        ])
    if overlay_rows:
        t = Table(overlay_rows, colWidths=[12 * cm, 5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CARD),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#333355")),
        ]))
        elems.append(t)
    note_aman = Table(
        [[Paragraph('<font color="#999999" size="7">\u2713 Aman = tidak terdapat kendala pada overlay tersebut.</font>', styles["Normal"])]],
        colWidths=[17 * cm],
    )
    note_aman.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BG)]))
    elems.append(note_aman)

    # ── PASAR WISATA (OSM) ───────────────────────────────
    section_header("PASAR WISATA (OSM)")
    card_grid([
        ("Fasilitas dalam 500m", data.get("densita_500m"), YELLOW),
        ("Fasilitas dalam 1km", data.get("densita_1km"), YELLOW),
        ("Fasilitas dalam 2km", data.get("densita_2km"), YELLOW),
    ])

    # ── KBLI COMPLIANCE (if present) ─────────────────────
    if data.get("kbli_code"):
        section_header("CEK KEPATUHAN KBLI")
        kbli_state = data.get("kbli_state", "")
        state_colors = {"APPROVED": GREEN, "WARNING": YELLOW, "REJECTED": RED}
        state_col = state_colors.get(kbli_state, GREY)
        card_grid([
            ("Kode KBLI", data.get("kbli_code"), CYAN),
            ("Judul", data.get("kbli_title"), WHITE),
            ("Status", kbli_state, state_col),
        ])
        card_grid([
            ("Alasan", data.get("kbli_reason", "").replace("_", " "), GREY),
            ("Risiko OSS", data.get("kbli_oss_risk"), YELLOW),
            ("Maks Kepemilikan Asing", f"{data.get('kbli_max_foreign', '')}%", GREEN),
        ])

    # ── INVESTMENT SCORE (if present) ────────────────────
    if data.get("invest_score") is not None:
        section_header("ANALISIS INVESTASI LENGKAP")
        score = data.get("invest_score", 0)
        risk = data.get("invest_risk", "UNKNOWN")
        risk_colors = {"LOW": GREEN, "MEDIUM": YELLOW, "HIGH": RED}
        risk_col = risk_colors.get(risk, GREY)
        verdict_icons = {"LOW": "\u2705 LAYAK INVESTASI", "MEDIUM": "\u26a0\ufe0f INVESTASI BERSYARAT", "HIGH": "\u274c TIDAK DIREKOMENDASIKAN"}
        verdict_text = verdict_icons.get(risk, "?")
        verdict_box = Table(
            [[
                Paragraph(f'<font color="#ffffff" size="14"><b>{verdict_text}</b></font>', styles["Normal"]),
                Paragraph(f'<font color="{risk_col}" size="16"><b>{score}</b></font><font color="#999999" size="9"> /100</font>',
                          ParagraphStyle("score_right", parent=styles["Normal"], alignment=2)),
            ]],
            colWidths=[12 * cm, 5 * cm],
        )
        verdict_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#1b3a1b") if risk == "LOW" else (HexColor("#3a3500") if risk == "MEDIUM" else HexColor("#3a1b1b"))),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ]))
        elems.append(verdict_box)
        summary_text = data.get("invest_summary", "")
        if summary_text:
            s = Table(
                [[Paragraph(f'<font color="#cccccc" size="8">{summary_text}</font>', styles["Normal"])]],
                colWidths=[17 * cm],
            )
            s.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), CARD),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]))
            elems.append(s)

    # ── SUMBER DATA ──────────────────────────────────────
    elems.append(Spacer(1, 0.5 * cm))
    section_header("SUMBER DATA")
    sources = [
        "BATARA Live \u2014 Dinas PUPR Kabupaten Badung (RDTR & overlay data)",
        "BPN BHUMI \u2014 Badan Pertanahan Nasional (data bidang tanah)",
        "OSM Overpass \u2014 OpenStreetMap (fasilitas & amenities)",
        "Open-Elevation \u2014 API elevasi global",
    ]
    src_rows = [[Paragraph(f'<font color="#cccccc" size="8">\u2022 {s}</font>', styles["Normal"])] for s in sources]
    src_t = Table(src_rows, colWidths=[17 * cm])
    src_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    elems.append(src_t)

    # ── FOOTER ───────────────────────────────────────────
    elems.append(Spacer(1, 0.5 * cm))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    elems.append(Paragraph(
        f'<font color="#999999" size="7">Report generato da Zantara Prime \u2014 Bali Zero Consulting \u2014 {data.get("timestamp", "")}<br/>'
        f'Questo report \u00e8 a scopo informativo. Si consiglia verifica indipendente prima di qualsiasi decisione d\'investimento.</font>',
        ParagraphStyle("footer", parent=styles["Normal"], alignment=TA_LEFT),
    ))

    doc.build(elems, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()

db_ok = init_db()

zones = get_zones()
zone_options = list(zones.keys()) if zones else []

if not zone_options:
    st.sidebar.error(T("sidebar_api_offline"))

if mode == "📍 Land Intel":
    st.title(T("land_intel_title"))
    st.caption(T("land_intel_caption"))

    col_in, col_map = st.columns([1, 1.5])

    with col_in:
        st.subheader(T("localization"))

        # ── Google Places Search ───────────────────────────
        _search_q = st.text_input(
            T("search_address"),
            placeholder=T("search_placeholder"),
            key="gmaps_search_input",
        )

        # Live autocomplete suggestions via Google Places API
        if _search_q and len(_search_q) >= 3:
            @st.cache_data(ttl=300)
            def _gmaps_autocomplete(query: str) -> list:
                try:
                    r = requests.get(
                        "https://maps.googleapis.com/maps/api/place/autocomplete/json",
                        params={
                            "input": query,
                            "components": "country:id",
                            "location": "-8.65,115.2",
                            "radius": 50000,
                            "key": GMAPS_KEY,
                        },
                        timeout=5,
                    )
                    data = r.json()
                    if data.get("status") == "OK":
                        return [
                            {"desc": p["description"], "place_id": p["place_id"]}
                            for p in data["predictions"][:5]
                        ]
                except Exception:
                    pass
                return []

            suggestions = _gmaps_autocomplete(_search_q)
            if suggestions:
                options = [s["desc"] for s in suggestions]
                chosen = st.selectbox(
                    "📍",
                    options,
                    key="gmaps_suggestion",
                    label_visibility="collapsed",
                )
                chosen_place = next((s for s in suggestions if s["desc"] == chosen), None)

                if st.button("✅ " + T("search"), key="gmaps_select_btn"):
                    if chosen_place:
                        # Get coordinates via Place Details
                        try:
                            det = requests.get(
                                "https://maps.googleapis.com/maps/api/place/details/json",
                                params={
                                    "place_id": chosen_place["place_id"],
                                    "fields": "geometry,formatted_address",
                                    "key": GMAPS_KEY,
                                },
                                timeout=5,
                            ).json()
                            loc = det["result"]["geometry"]["location"]
                            st.session_state["li_lat"] = loc["lat"]
                            st.session_state["li_lon"] = loc["lng"]
                            st.session_state["geo_label"] = det["result"].get(
                                "formatted_address", chosen_place["desc"]
                            )
                            st.rerun()
                        except Exception:
                            st.warning(T("geocoding_unavailable"))
            elif _search_q.strip():
                st.caption("No results — try a different search")

        if "geo_label" in st.session_state and st.session_state["geo_label"]:
            st.caption(f"📍 {st.session_state['geo_label']}")

        lat_in = st.number_input(T("latitude"), value=st.session_state.get("li_lat", -8.64780), format="%.6f", key="li_lat")
        lon_in = st.number_input(T("longitude"), value=st.session_state.get("li_lon", 115.13200), format="%.6f", key="li_lon")

        st.subheader(T("land_data"))
        li_size = st.number_input(T("area_m2"), min_value=50, max_value=50_000, value=500, step=50, key="li_size")
        li_price = st.number_input(T("asking_price_idr"), min_value=100_000_000,
                                   max_value=500_000_000_000, value=3_250_000_000,
                                   step=50_000_000, format="%d", key="li_price")
        if fx_usd:
            st.caption(f"≈ ${li_price * fx_usd:,.0f} USD  |  €{li_price * fx_eur:,.0f} EUR")

        btn_intel = st.button(T("analyze_land"), use_container_width=True, type="primary")

    with col_map:
        st.subheader(T("map"))
        m_li = folium.Map(
            location=[lat_in, lon_in],
            zoom_start=16,
            tiles=None,
        )

        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google",
            name="🛰️ Google Satellite",
            overlay=False,
            control=True,
        ).add_to(m_li)

        folium.TileLayer(
            tiles="OpenStreetMap",
            name="🗺️ Strade (OSM)",
            overlay=False,
            control=True,
        ).add_to(m_li)

        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google",
            name="🛰️ Google Hybrid",
            overlay=False,
            control=True,
        ).add_to(m_li)

        folium.WmsTileLayer(
            url="https://bhumi.atrbpn.go.id/mprx/service",
            layers="bhumi_persil",
            fmt="image/png",
            transparent=True,
            version="1.3.0",
            name="🏛️ Parcelle BPN (catasto)",
            overlay=True,
            control=True,
            opacity=0.7,
        ).add_to(m_li)

        rdtr_li = load_rdtr_geojson(("Kuta", "Kuta Selatan", "Kuta Utara"))

        def rdtr_style_li(feature):
            color_str = feature["properties"].get("_zone_color", "200 200 200")
            hex_color, _ = batara_color_to_hex(color_str)
            return {"fillColor": hex_color, "color": hex_color, "weight": 0.8, "fillOpacity": 0.35}

        if rdtr_li["features"]:
            GeoJson(
                rdtr_li,
                name="Zone RDTR (Badung — 3 kec.)",
                style_function=rdtr_style_li,
                show=False,
                tooltip=GeoJsonTooltip(
                    fields=["_zone_code", "_zone_name"],
                    aliases=["Zona:", "Nome:"],
                    sticky=True,
                    style="font-size:12px; font-weight:bold;",
                ),
            ).add_to(m_li)

        tabanan_data = load_tabanan_geojson()
        if tabanan_data["features"]:
            def tabanan_style_li(feature):
                color = feature["properties"].get("_zone_color", "#cccccc")
                return {"fillColor": color, "color": color, "weight": 1.0, "fillOpacity": 0.40, "dashArray": "4"}

            GeoJson(
                tabanan_data,
                name="Zone OSM (Tabanan — 10 kec.)",
                style_function=tabanan_style_li,
                show=False,
                tooltip=GeoJsonTooltip(
                    fields=["_zone_code", "_zone_name", "_source"],
                    aliases=["Zona:", "Nome:", "Fonte:"],
                    sticky=True,
                    style="font-size:12px; font-weight:bold;",
                ),
            ).add_to(m_li)

        denpasar_data = load_denpasar_geojson()
        if denpasar_data["features"]:
            def denpasar_style_li(feature):
                color = feature["properties"].get("_zone_color", "#cccccc")
                return {"fillColor": color, "color": color, "weight": 1.0, "fillOpacity": 0.40, "dashArray": "2"}

            GeoJson(
                denpasar_data,
                name="Zone OSM (Denpasar — 4 kec.)",
                style_function=denpasar_style_li,
                show=False,
                tooltip=GeoJsonTooltip(
                    fields=["_zone_code", "_zone_name", "_source"],
                    aliases=["Zona:", "Nome:", "Fonte:"],
                    sticky=True,
                    style="font-size:12px; font-weight:bold;",
                ),
            ).add_to(m_li)

        folium.Marker(
            [lat_in, lon_in],
            popup=folium.Popup(f"<b>Terreno</b><br>{li_size} m²", max_width=200),
            tooltip="Terreno analizzato",
            icon=folium.Icon(color="green", icon="crosshairs", prefix="fa"),
        ).add_to(m_li)

        # Marker fisso Casa Tera - Kedungu
        folium.Marker(
            [-8.5970391, 115.0941105],
            popup=folium.Popup(
                "<b>Casa Tera</b><br>C33V+7MQ, Jl. Pantai Kedungu<br>Belalang, Kediri, Tabanan<br><i>Zona: OSM non classificata</i>",
                max_width=220,
            ),
            tooltip="Casa Tera (Kedungu)",
            icon=folium.Icon(color="orange", icon="star", prefix="fa"),
        ).add_to(m_li)

        # ── CRM Client Layer ──────────────────────────────────
        crm_clients = get_clients_geo()
        crm_layer = folium.FeatureGroup(name="👤 Clienti CRM")
        for cl in crm_clients:
            addr = cl.get("address")
            if addr:
                folium.Marker(
                    [lat_in, lon_in],  # placeholder — no lat/lon in DB yet
                    popup=folium.Popup(
                        f"<b>{cl.get('full_name', 'N/A')}</b><br>"
                        f"{cl.get('email', '')}<br>"
                        f"{addr[:80]}",
                        max_width=220,
                    ),
                    tooltip=cl.get("full_name", "Cliente"),
                    icon=folium.Icon(color="green", icon="user", prefix="fa"),
                ).add_to(crm_layer)
        if crm_clients:
            crm_layer.add_to(m_li)

        Fullscreen(position="topleft", title="Fullscreen", title_cancel="Esci").add_to(m_li)
        LayerControl(collapsed=False).add_to(m_li)
        st_folium(m_li, height=480, use_container_width=True)

    # ── Fetch BATARA on button click, cache in session_state ──
    if btn_intel:
        with st.spinner(T("querying_batara")):
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
                    st.error(T("batara_no_data"))
                    st.stop()

                geom0 = geom_list[0]
                # Cache full BATARA response in session_state
                st.session_state["li_geom0"] = geom0
                st.session_state["li_coords"] = (lat_in, lon_in)
                st.session_state["li_sizes"] = (li_size, li_price)
            except requests.exceptions.Timeout:
                st.error(T("batara_timeout"))
            except Exception as e:
                st.session_state.pop("li_geom0", None)
                st.warning(T("batara_fallback_gistaru", err_type=type(e).__name__))
                # Try GISTARU fallback
                try:
                    gr = requests.post(
                        f"{API_URL}/api/dashboard/map/gistaru-zone",
                        json={"lat": lat_in, "lon": lon_in}, timeout=60,
                    )
                    gd = gr.json()
                    if gd.get("found"):
                        st.session_state["li_gistaru"] = gd
                        st.session_state["li_coords"] = (lat_in, lon_in)
                        st.session_state["li_sizes"] = (li_size, li_price)
                except Exception:
                    pass

    # ── Render from session_state (survives KBLI / Invest button reruns) ──
    _li_show = (
        st.session_state.get("li_coords") == (lat_in, lon_in)
        and "li_geom0" in st.session_state
    )
    if _li_show:
        geom0 = st.session_state["li_geom0"]
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
            st.subheader(T("urban_params"))
            u1, u2, u3, u4 = st.columns(4)
            u1.metric("KDB", kdb)
            u2.metric("KLB", klb)
            u3.metric("KDH", kdh)
            u4.metric(T("max_height"), tb)
            st.caption(f"GSB: {gsb}")
            try:
                # Primary: open-elevation.com | Fallback: open-meteo.com
                try:
                    elev_r = requests.get(
                        "https://api.open-elevation.com/api/v1/lookup",
                        params={"locations": f"{lat_in},{lon_in}"},
                        timeout=6,
                    )
                    elev_m = elev_r.json()["results"][0]["elevation"]
                except Exception:
                    elev_r2 = requests.get(
                        "https://api.open-meteo.com/v1/elevation",
                        params={"latitude": lat_in, "longitude": lon_in},
                        timeout=6,
                    )
                    elev_m = elev_r2.json()["elevation"][0]

                # Bali coastline reference points (~3-5 km spacing)
                _coast_pts = [
                    (-8.5920, 115.0890),  # Tanah Lot west
                    (-8.6250, 115.1100),  # Pererenan
                    (-8.6380, 115.1300),  # Canggu / Echo Beach
                    (-8.6480, 115.1460),  # Berawa
                    (-8.6520, 115.1570),  # Seminyak / Petitenget
                    (-8.6700, 115.1630),  # Legian
                    (-8.6950, 115.1680),  # Kuta Beach
                    (-8.7230, 115.1680),  # Jimbaran south
                    (-8.7650, 115.1550),  # Dreamland / Bingin
                    (-8.8150, 115.0920),  # Uluwatu south tip
                    (-8.8290, 115.1250),  # Suluban / Blue Point
                    (-8.7910, 115.1700),  # Padang Padang
                    (-8.8100, 115.2300),  # Nusa Dua south
                    (-8.7740, 115.2350),  # Nusa Dua north / BTDC
                    (-8.7540, 115.2620),  # Tanjung Benoa
                    (-8.7250, 115.2530),  # Serangan island
                    (-8.6840, 115.2620),  # Sanur south
                    (-8.6640, 115.2660),  # Sanur north
                    (-8.6120, 115.2710),  # Ketewel / Gianyar coast
                    (-8.5440, 115.3260),  # Sukawati coast
                    (-8.5260, 115.3700),  # Klungkung coast
                    (-8.5070, 115.4430),  # Candidasa / Karangasem
                    (-8.4600, 115.4800),  # Padang Bai
                    (-8.4200, 115.5050),  # Amed west
                    (-8.3500, 115.5800),  # Amed east / Tulamben
                    (-8.3180, 115.4130),  # East Singaraja coast
                    (-8.1520, 115.0600),  # Lovina Beach
                    (-8.1100, 115.0900),  # Lovina west / Kalibukbuk
                    (-8.1600, 115.1800),  # Singaraja harbour
                    (-8.2350, 115.2800),  # Tejakula coast
                    (-8.2870, 115.1700),  # Pemuteran / West Bali
                    (-8.3300, 115.0900),  # Menjangan area
                    (-8.3810, 114.9550),  # Gilimanuk
                    (-8.4500, 114.9600),  # Negara coast
                    (-8.5240, 114.9700),  # Balian Beach / Tabanan west
                    (-8.5600, 115.0300),  # Soka Beach
                ]
                dist_coast_km = min(
                    6371 * 2 * math.asin(math.sqrt(
                        math.sin(math.radians(lat_in - clat) / 2) ** 2
                        + math.cos(math.radians(lat_in)) * math.cos(math.radians(clat))
                        * math.sin(math.radians(lon_in - clon) / 2) ** 2
                    ))
                    for clat, clon in _coast_pts
                )

                # Flood risk: combine elevation + coast proximity
                if elev_m < 3 and dist_coast_km < 2:
                    elev_risk = T("flood_risk_high")
                elif elev_m < 5 and dist_coast_km < 1:
                    elev_risk = T("flood_risk_high")
                elif elev_m < 8 and dist_coast_km < 1.5:
                    elev_risk = T("low_zone_check")
                else:
                    elev_risk = T("safe_elevation")

                # Sea view: hillside properties close to coast
                sea_view = (
                    (elev_m > 15 and dist_coast_km < 3)
                    or (elev_m > 8 and dist_coast_km < 0.8)
                )

                e1, e2 = st.columns(2)
                e1.metric(T("elevation_asl"), f"{elev_m:.1f} m", delta=elev_risk, delta_color="off")
                e2.metric(T("coast_distance"), f"{dist_coast_km:.1f} km",
                          delta=T("sea_view_possible") if sea_view else None, delta_color="off")
            except Exception:
                st.caption(T("elevation_unavailable"))

        with col_roi:
            st.subheader(T("roi_projected"))
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
                    st.metric(T("optimal_roi"), f"{gs.get('roi', 0):.2f}%")
                    st.metric(T("break_even"), f"{gs.get('bey', 0):.1f} {T('years')}")
                    st.info(f"**{gs.get('build')}** + **{gs.get('yield')}**")
                    st.caption(f"Buildable: {urb.get('max_build_m2')} m²  |  Footprint: {urb.get('max_footprint')} m²")
                except Exception:
                    st.warning(T("roi_unavailable"))
            else:
                st.warning(T("zone_not_in_roi_db", zone_code=zone_code))

        # Sensitivity matrix
        if zone_code in zone_options:
            st.subheader(T("sensitivity_matrix"))
            try:
                matrix = rr.get("sensitivity_matrix", {})
                rows = []
                for bk, yields in matrix.items():
                    row = {T("construction_cost"): bk.replace("_", " ")}
                    for yk, mv in yields.items():
                        roi_v = mv["roi_pct"]
                        tag = " 🔥" if roi_v >= 12 else " ✅" if roi_v >= 8 else " 🟡" if roi_v >= 4 else " 🔴"
                        row[yk.replace("_", " ")] = f"{roi_v:.2f}%{tag}"
                    rows.append(row)
                st.table(pd.DataFrame(rows).set_index(T("construction_cost")))
            except Exception:
                pass

        extra_fields = {
            "kkop_1": T("overlay_kkop"),
            "lp2b_2": T("overlay_lp2b"),
            "krb_03": T("overlay_krb"),
            "teb_05": T("overlay_teb"),
            "cagbud": T("overlay_cagbud"),
            "resair": T("overlay_resair"),
        }
        vincoli = {label: geom0.get(field) for field, label in extra_fields.items()
                   if geom0.get(field) not in (None, "", "0", 0)}
        if vincoli:
            with st.expander(T("constraints_detected")):
                for label, val in vincoli.items():
                    st.markdown(f"- **{label}**: {val}")
        else:
            st.success(T("no_constraints"))

        # ── KBLI COMPLIANCE CHECK ────────────────────────────────
        st.subheader(T("kbli_compliance_title"))
        kbli_input = st.text_input(
            T("kbli_code_input"),
            key="kbli_compliance_input",
        )
        kbli_col1, kbli_col2 = st.columns([1, 3])
        with kbli_col1:
            kbli_pma = st.checkbox(T("pma_foreign"), value=True, key="kbli_pma_check")
        with kbli_col2:
            kbli_btn = st.button(T("verify_compliance"), key="kbli_validate_btn")

        if kbli_btn and kbli_input:
            try:
                kbli_resp = requests.post(
                    f"{API_URL}/api/dashboard/map/validate-property",
                    json={
                        "kbli_code": kbli_input.strip(),
                        "is_pma": kbli_pma,
                        "location": "Bali",
                    },
                    timeout=5,
                )
                if kbli_resp.status_code == 200:
                    kd = kbli_resp.json()
                    audit = kd.get("audit", kd)
                    state = audit.get("state", kd.get("state", "UNKNOWN"))

                    badge_colors = {
                        "APPROVED": ("#198754", "✅"),
                        "WARNING": ("#fd7e14", "⚠️"),
                        "REJECTED": ("#dc3545", "❌"),
                        "ERROR": ("#6c757d", "🔴"),
                    }
                    color, icon = badge_colors.get(state, ("#6c757d", "❓"))

                    title = kd.get("title", kbli_input)
                    reason = audit.get("reason_code", kd.get("reason_code", ""))
                    oss_risk = audit.get("oss_risk", "")

                    st.markdown(f"""
                    <div style="background:{color}22; padding:14px; border-radius:8px;
                                border-left:6px solid {color}; margin:8px 0;">
                        <span style="font-size:1.3em">{icon} <b>{state}</b></span>
                        &nbsp;—&nbsp; <b>{kd.get('kbli_2025', kbli_input)}</b> {title}
                        <br><span style="color:#555; font-size:0.85em">
                            {T("reason")}: {reason.replace('_', ' ')}
                            {f' | {T("oss_risk")}: {oss_risk}' if oss_risk else ''}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                    pma = kd.get("pma_logic", {})
                    if pma:
                        st.caption(
                            f"{T('max_foreign_ownership')}: {pma.get('max_foreign_ownership', '?')}%"
                            f" | {T('umkm_reserved')}: {T('yes') if pma.get('is_umkm_reserved') else T('no')}"
                        )
                else:
                    st.warning(T("backend_error"))
            except requests.exceptions.ConnectionError:
                st.caption(T("backend_unreachable_kbli"))
            except Exception as kbli_err:
                st.caption(T("kbli_unavailable", err=kbli_err))
        elif kbli_btn and not kbli_input:
            st.info(T("enter_kbli_code"))

        # ── ANALISI INVESTIMENTO UNIFICATA ──────────────────────
        st.subheader(T("invest_title"))
        st.caption(T("invest_caption"))
        invest_btn = st.button(
            T("invest_title"),
            use_container_width=True,
            type="secondary",
            key="invest_analysis_btn",
        )

        if invest_btn:
            invest_payload = {
                "lat": lat_in,
                "lon": lon_in,
                "is_pma": kbli_pma,
                "land_size_m2": li_size,
                "price_idr": li_price,
            }
            # Include KBLI code if provided
            _kbli_val = st.session_state.get("kbli_compliance_input", "").strip()
            if _kbli_val:
                invest_payload["kbli_code"] = _kbli_val

            # Pass geo data from previous analysis (if available in session_state)
            _geo = {}
            if st.session_state.get("li_geo_data"):
                _geo = st.session_state["li_geo_data"]
            invest_payload["geo_data"] = _geo if _geo else None

            try:
                inv_resp = requests.post(
                    f"{API_URL}/api/dashboard/map/analyze-investment",
                    json=invest_payload,
                    timeout=25,
                )
                if inv_resp.status_code == 200:
                    inv = inv_resp.json()
                    verdict = inv.get("verdict", {})
                    risk = verdict.get("risk_level", "UNKNOWN")
                    can = verdict.get("can_invest", False)
                    inv_score = verdict.get("score", 0)
                    breakdown = verdict.get("breakdown", {})
                    hard_blocks = verdict.get("hard_blocks", [])
                    modifiers = verdict.get("modifiers", [])

                    # Verdict box with score
                    v_colors = {"LOW": "#198754", "MEDIUM": "#fd7e14", "HIGH": "#dc3545"}
                    v_icons = {"LOW": "✅", "MEDIUM": "⚠️", "HIGH": "❌"}
                    v_col = v_colors.get(risk, "#6c757d")
                    v_ico = v_icons.get(risk, "❓")

                    # Score bar color gradient
                    if inv_score >= 65:
                        bar_color = "#198754"
                    elif inv_score >= 35:
                        bar_color = "#fd7e14"
                    else:
                        bar_color = "#dc3545"

                    st.markdown(f"""
                    <div style="background:{v_col}22; padding:16px; border-radius:10px;
                                border-left:6px solid {v_col}; margin:12px 0;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:1.5em">{v_ico} <b>{T('investable') if can else T('not_investable')}</b></span>
                            <div style="text-align:right;">
                                <span style="background:{v_col}; color:white; padding:4px 12px;
                                             border-radius:4px; font-weight:bold;">{risk} RISK</span>
                                <span style="font-size:1.8em; font-weight:bold; margin-left:10px; color:{bar_color};">{inv_score}</span>
                                <span style="color:#888; font-size:0.8em">/100</span>
                            </div>
                        </div>
                        <div style="background:#e0e0e0; border-radius:4px; height:8px; margin:10px 0 6px 0;">
                            <div style="background:{bar_color}; width:{inv_score}%; height:100%; border-radius:4px;"></div>
                        </div>
                        <span style="color:#555; font-size:0.9em; display:block;">
                            {verdict.get('summary', '')}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                    # Hard blocks (if any)
                    if hard_blocks:
                        for hb in hard_blocks:
                            st.error(f"🚫 {hb}")

                    # 3-column detail cards
                    inv_c1, inv_c2, inv_c3 = st.columns(3)

                    with inv_c1:
                        st.markdown(f"**{T('zone_rdtr')}**")
                        z = inv.get("zone", {})
                        if z and z.get("source") != "unavailable":
                            st.metric(T("zone"), z.get("code", "N/A"))
                            st.caption(f"{z.get('name', '')} — {z.get('desa', '')}")
                            st.caption(f"KDB {z.get('kdb')} | KLB {z.get('klb')} | KDH {z.get('kdh')}")
                        else:
                            st.caption(T("batara_unavailable"))

                    with inv_c2:
                        st.markdown(f"**{T('kbli_compliance')}**")
                        k = inv.get("kbli")
                        if k:
                            k_st = k.get("state", "?")
                            k_colors = {"APPROVED": "🟢", "WARNING": "🟡", "REJECTED": "🔴"}
                            st.metric(T("status"), f"{k_colors.get(k_st, '⚪')} {k_st}")
                            st.caption(f"{k.get('code', '')} {k.get('title', '')}")
                            if k.get("oss_risk"):
                                st.caption(f"{T('oss_risk')}: {k['oss_risk']}")
                        else:
                            st.caption(T("no_kbli_provided"))

                    with inv_c3:
                        st.markdown(f"**{T('roi_projection')}**")
                        r = inv.get("roi", {})
                        gs = r.get("golden_strategy", {})
                        if gs.get("roi"):
                            st.metric("ROI", f"{gs['roi']:.1f}%")
                            st.metric(T("break_even"), f"{gs.get('bey', '?')} {T('years')}")
                            st.caption(f"{gs.get('build', '')} + {gs.get('yield', '')}")
                        elif r.get("error"):
                            st.caption(T("roi_not_calculable", err=r['error']))
                        else:
                            st.caption(T("insufficient_data_roi"))

                    # Score breakdown (expandable)
                    if breakdown:
                        with st.expander(T("score_breakdown"), expanded=False):
                            _factor_labels = {
                                "roi": ("ROI", 30),
                                "zone_kbli_fit": ("Zona-KBLI", 20),
                                "break_even": ("Break-Even", 15),
                                "flood_risk": ("Flood Risk", 10),
                                "market": ("Market", 10),
                                "regulatory": ("Regolatorio", 10),
                                "amenity": ("Amenity", 5),
                            }
                            for key, (label, max_pts) in _factor_labels.items():
                                bd = breakdown.get(key, {})
                                pts = bd.get("score", 0)
                                pct = int(pts / max_pts * 100) if max_pts > 0 else 0
                                if pct >= 70:
                                    _bc = "#198754"
                                elif pct >= 40:
                                    _bc = "#fd7e14"
                                else:
                                    _bc = "#dc3545"
                                val_str = ""
                                if bd.get("value") is not None:
                                    val_str = f" ({bd['value']})"
                                elif bd.get("state"):
                                    val_str = f" ({bd['state']})"
                                st.markdown(f"""
                                <div style="margin:4px 0;">
                                    <span style="display:inline-block;width:100px;font-size:0.85em;">{label}</span>
                                    <span style="font-weight:bold;color:{_bc};">{pts}/{max_pts}</span>
                                    <span style="color:#888;font-size:0.8em;">{val_str}</span>
                                    <div style="background:#e0e0e0;border-radius:3px;height:6px;margin-top:2px;">
                                        <div style="background:{_bc};width:{pct}%;height:100%;border-radius:3px;"></div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            if modifiers:
                                st.markdown("---")
                                for mod in modifiers:
                                    st.caption(mod)

                else:
                    st.warning(T("backend_http_error", code=inv_resp.status_code))
            except requests.exceptions.ConnectionError:
                st.warning(T("backend_unreachable_invest"))
            except Exception as inv_err:
                st.warning(T("invest_unavailable", err=inv_err))

        # ── WALK SCORE + NOISE MAP ───────────────────────────────
        st.subheader(T("urban_context"))
        try:
            overpass_url_ctx = "https://overpass-api.de/api/interpreter"
            # Amenity score: proximity to daily-life services (NOT true walkability)
            q_walk = f"""
[out:json][timeout:25];
(
  node["shop"~"supermarket|convenience"](around:800,{lat_in},{lon_in});
  way["shop"~"supermarket|convenience"](around:800,{lat_in},{lon_in});
  node["amenity"~"restaurant|cafe"](around:600,{lat_in},{lon_in});
  node["amenity"~"hospital|clinic|doctors"](around:2000,{lat_in},{lon_in});
  node["amenity"="atm"](around:1000,{lat_in},{lon_in});
  node["amenity"="pharmacy"](around:1000,{lat_in},{lon_in});
  node["natural"="beach"](around:2000,{lat_in},{lon_in});
);
out body;
"""
            rq_walk = requests.post(overpass_url_ctx, data={"data": q_walk}, timeout=30)
            walk_els = rq_walk.json().get("elements", []) if rq_walk.status_code == 200 else []

            supermarket = sum(1 for e in walk_els if any(k in e.get("tags", {}).get("shop", "") for k in ("supermarket", "convenience")))
            restaurant = sum(1 for e in walk_els if e.get("tags", {}).get("amenity") in ("restaurant", "cafe"))
            hospital = sum(1 for e in walk_els if e.get("tags", {}).get("amenity") in ("hospital", "clinic", "doctors"))
            atm = sum(1 for e in walk_els if e.get("tags", {}).get("amenity") == "atm")
            pharmacy = sum(1 for e in walk_els if e.get("tags", {}).get("amenity") == "pharmacy")
            beach = sum(1 for e in walk_els if e.get("tags", {}).get("natural") == "beach")

            # Weighted: shops(25) + food(25) + health(20) + finance(15) + beach(15) = 100
            walk_score = min(100, (
                min(supermarket, 3) * 8 +       # max 24 — daily shopping
                min(restaurant, 4) * 6 +         # max 24 — food & drink
                min(hospital, 1) * 12 +          # max 12 — medical access
                min(pharmacy, 1) * 8 +           # max 8  — pharmacy
                min(atm, 2) * 7 +                # max 14 — financial
                min(beach, 1) * 8 +              # max 8  — lifestyle (Bali context)
                (10 if supermarket >= 2 and restaurant >= 2 else 0)  # density bonus
            ))

            q_noise = f"""
[out:json][timeout:15];
(
  node["amenity"~"bar|pub|nightclub|biergarten"](around:400,{lat_in},{lon_in});
  way["amenity"~"bar|pub|nightclub|biergarten"](around:400,{lat_in},{lon_in});
  way["highway"~"primary|trunk|motorway"](around:100,{lat_in},{lon_in});
  way["highway"="secondary"](around:80,{lat_in},{lon_in});
  node["leisure"="bleaching"](around:300,{lat_in},{lon_in});
);
out body;
"""
            rq_noise = requests.post(overpass_url_ctx, data={"data": q_noise}, timeout=20)
            noise_els = rq_noise.json().get("elements", []) if rq_noise.status_code == 200 else []
            # Separate nightlife vs traffic noise
            bars = sum(1 for e in noise_els if e.get("tags", {}).get("amenity") in ("bar", "pub", "nightclub", "biergarten"))
            roads = sum(1 for e in noise_els if e.get("tags", {}).get("highway") in ("primary", "trunk", "motorway", "secondary"))
            noise_score = bars * 2 + roads  # bars weigh more (night disturbance)

            if noise_score == 0:
                noise_label = T("silent")
                noise_yield = T("noise_yield_quiet")
            elif noise_score <= 4:
                noise_label = T("moderate")
                noise_yield = T("noise_yield_moderate")
            else:
                noise_label = T("noisy")
                noise_yield = T("noise_yield_noisy")

            ws_label = T("walk_excellent") if walk_score >= 65 else T("walk_good") if walk_score >= 35 else T("walk_isolated")

            w1, w2 = st.columns(2)
            w1.metric(T("walk_score"), f"{walk_score}/100", delta=ws_label, delta_color="off")
            w2.metric(T("noise_level"), noise_label, delta=noise_yield, delta_color="off")

        except Exception as ctx_err:
            st.caption(T("urban_context_unavailable", err=ctx_err))

        # ── BPN CATASTO ──────────────────────────────────────
        st.subheader(T("bpn_catasto"))
        bpn_feats = []
        try:
            bpn_params = {
                "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo",
                "FORMAT": "image/png", "TRANSPARENT": "true",
                "QUERY_LAYERS": "bhumi_persil", "LAYERS": "bhumi_persil",
                "INFO_FORMAT": "application/json",
                "I": "50", "J": "50", "CRS": "EPSG:4326", "STYLES": "",
                "WIDTH": "101", "HEIGHT": "101",
                "BBOX": f"{lat_in-0.001},{lon_in-0.001},{lat_in+0.001},{lon_in+0.001}",
            }
            bpn_r = requests.get(
                "https://bhumi.atrbpn.go.id/mprx/service",
                params=bpn_params,
                headers={"Referer": "https://bhumi.atrbpn.go.id/peta", "User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            bpn_feats = bpn_r.json().get("features", [])

            if bpn_feats:
                for bf in bpn_feats:
                    bp = bf.get("properties", {})
                    tipehak = bp.get("tipehak", "N/A")
                    luas_bpn = bp.get("luas", "N/A")
                    nomor = bp.get("nomor", "N/A")
                    tahun = bp.get("tahun", "N/A")
                    nib_bpn = bp.get("nib") or "—"
                    akurasi = bp.get("akurasibidang") or "—"

                    hak_color = {
                        "Hak Milik": "#198754",
                        "Hak Guna Bangunan": "#0d6efd",
                        "Hak Pakai": "#fd7e14",
                        "Hak Guna Usaha": "#dc3545",
                    }.get(tipehak, "#6c757d")

                    st.markdown(f"""
                    <div style="background:{hak_color}22; padding:12px; border-radius:8px;
                                border-left:5px solid {hak_color}; margin-bottom:8px;">
                        <b style="color:{hak_color}; font-size:1.1em">{tipehak}</b>
                    </div>
                    """, unsafe_allow_html=True)

                    b1, b2, b3, b4 = st.columns(4)
                    b1.metric("Luas BPN", f"{luas_bpn:,} m²" if isinstance(luas_bpn, (int,float)) else luas_bpn)
                    b2.metric(T("registration_year"), tahun)
                    b3.metric("NIB", nib_bpn)
                    b4.metric(T("accuracy"), akurasi)
                    st.caption(f"{T('certificate_number')}: `{nomor}`")

                    if bf.get("geometry"):
                        folium.GeoJson(
                            {"type": "FeatureCollection", "features": [bf]},
                            name="Bidang Tanah BPN",
                            style_function=lambda x, c=hak_color: {
                                "color": c, "weight": 2.5,
                                "fillColor": c, "fillOpacity": 0.15,
                            },
                            tooltip=folium.GeoJsonTooltip(
                                fields=["tipehak", "luas", "nomor"],
                                aliases=["Tipe Hak:", "Luas (m²):", "Nomor:"],
                            ),
                        ).add_to(m_li)
            else:
                st.info(T("no_bpn_parcel"))

        except Exception as bpn_err:
            st.warning(T("bpn_unreachable", err=bpn_err))

        # ── AIRBNB DENSITY (OSM Overpass) ─────────────────────
        st.subheader(T("tourism_density"))
        try:
            overpass_url = "https://overpass-api.de/api/interpreter"
            # Single query for 2km radius, then filter by distance for sub-radii
            q_density = f"""
[out:json][timeout:25];
(
  node["tourism"~"villa|guest_house|hotel|hostel|apartment"](around:2000,{lat_in},{lon_in});
  way["tourism"~"villa|guest_house|hotel|hostel|apartment"](around:2000,{lat_in},{lon_in});
);
out center;
"""
            rq_dens = requests.post(overpass_url, data={"data": q_density}, timeout=30)
            density_results = {}
            _all_tourism_els = []
            if rq_dens.status_code == 200 and rq_dens.text.strip():
                _all_tourism_els = rq_dens.json().get("elements", [])
                for radius, label in [(500, "500m"), (1000, "1km"), (2000, "2km")]:
                    count = 0
                    for el in _all_tourism_els:
                        c = el.get("center", el)
                        elat, elon = c.get("lat"), c.get("lon")
                        if elat and elon:
                            # Fast approximate distance (good enough for <5km)
                            dlat_r = math.radians(lat_in - elat)
                            dlon_r = math.radians(lon_in - elon)
                            a_d = dlat_r**2 + (dlon_r * math.cos(math.radians(lat_in)))**2
                            dist_m = 6371000 * math.sqrt(a_d)
                            if dist_m <= radius:
                                count += 1
                    density_results[label] = count

            if density_results:
                d1, d2, d3 = st.columns(3)
                cols = [d1, d2, d3]
                thresholds = {"500m": (10, 25), "1km": (30, 70), "2km": (80, 150)}
                for i, (label, count) in enumerate(density_results.items()):
                    low, high = thresholds.get(label, (20, 50))
                    if count >= high:
                        signal = T("saturated_zone")
                    elif count >= low:
                        signal = T("active_market")
                    else:
                        signal = T("low_competition")
                    cols[i].metric(T("structures_within", radius=label), count, delta=signal, delta_color="off")

                if _all_tourism_els:
                    for el in _all_tourism_els:
                        c = el.get("center", el)
                        elat = c.get("lat")
                        elon = c.get("lon")
                        if elat and elon:
                            name = el.get("tags", {}).get("name", "Villa")
                            tourism = el.get("tags", {}).get("tourism", "villa")
                            folium.CircleMarker(
                                [elat, elon],
                                radius=5,
                                color="#FF6B35",
                                fill=True,
                                fill_color="#FF6B35",
                                fill_opacity=0.6,
                                tooltip=f"{tourism}: {name}",
                            ).add_to(m_li)

                st.caption(T("osm_source_note"))
            else:
                st.info(T("density_unavailable"))

        except Exception as osm_err:
            st.warning(T("osm_unreachable", err=osm_err))

        # ── Store geo data in session_state for investment scoring ──
        _geo_store = {}
        if "walk_score" in locals():
            _geo_store["walk_score"] = walk_score
        if "elev_m" in locals():
            _geo_store["elev_m"] = elev_m
        if "dist_coast_km" in locals():
            _geo_store["dist_coast_km"] = dist_coast_km
        if "sea_view" in locals():
            _geo_store["sea_view"] = sea_view
        if "density_results" in locals():
            _geo_store["densita_1km"] = density_results.get("1km")
        # Map flood risk to scoring key
        if "elev_risk" in locals():
            flood_key = "safe"
            if elev_risk == T("flood_risk_high"):
                flood_key = "high"
            elif elev_risk == T("low_zone_check"):
                flood_key = "check"
            _geo_store["flood_risk"] = flood_key
        if _geo_store:
            st.session_state["li_geo_data"] = _geo_store

        # ── AI ASSESSMENT (Qwen 32B locale) ───────────────────
        st.subheader(T("ai_assessment"))
        st.caption(T("ai_caption"))

        _bpn_str = ""
        try:
            if bpn_feats:
                bp0 = bpn_feats[0].get("properties", {})
                _bpn_str = (
                    f"Tipo diritto: {bp0.get('tipehak','N/A')}, "
                    f"Luas: {bp0.get('luas','N/A')} m², "
                    f"Anno: {bp0.get('tahun','N/A')}, "
                    f"NIB: {bp0.get('nib') or '—'}"
                )
        except Exception:
            _bpn_str = T("unavailable")

        _vincoli_str = ", ".join(vincoli.keys()) if "vincoli" in locals() and vincoli else T("none_detected")
        _density_str = ", ".join(
            f"{k}: {v} strutture" for k, v in density_results.items()
        ) if "density_results" in locals() and density_results else T("unavailable")

        _roi_str = ""
        try:
            if "gs" in locals():
                _roi_str = f"ROI: {gs.get('roi',0):.2f}%, Break-even: {gs.get('bey',0):.1f} {T('years')}, {T('pdf_strategy')}: {gs.get('build','')} + {gs.get('yield','')}"
            else:
                _roi_str = T("unavailable")
        except Exception:
            _roi_str = T("unavailable")

        _ai_lang = T("ai_prompt_lang")
        ai_prompt = f"""Sei un consulente immobiliare specializzato in Bali. Analizza questo terreno e dai un giudizio professionale CONCISO (max 200 parole) in {_ai_lang}.

DATI TERRENO:
- Coordinate: {lat_in:.6f}, {lon_in:.6f}
- Zona RDTR: {zone_code} — {zone_name}
- Desa: {desa}
- Parametri: KDB {kdb}, KLB {klb}, KDH {kdh}, Altezza max {tb}
- Dimensione: {li_size} m²
- Prezzo totale: IDR {li_price:,.0f}

ANALISI ROI:
{_roi_str}

CATASTO BPN:
{_bpn_str}

VINCOLI OVERLAY:
{_vincoli_str}

MERCATO TURISTICO (OSM):
{_density_str}

Dai un giudizio su: (1) potenziale di sviluppo, (2) rischi principali, (3) raccomandazione finale (acquista/valuta/evita) con breve motivazione."""

        if st.button(T("generate_ai_report"), key="ai_report_btn"):
            try:
                ollama_url = "http://localhost:11434/api/generate"
                payload_ai = {
                    "model": "qwen2.5-coder:32b-instruct-q4_K_M",
                    "prompt": ai_prompt,
                    "stream": True,
                    "options": {"num_predict": 300, "temperature": 0.3},
                }
                ai_placeholder = st.empty()
                ai_text = ""
                with st.spinner(T("qwen_processing")):
                    resp_ai = requests.post(
                        ollama_url, json=payload_ai, stream=True, timeout=120
                    )
                    for line in resp_ai.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line.decode("utf-8"))
                                ai_text += chunk.get("response", "")
                                ai_placeholder.markdown(ai_text + "▌")
                                if chunk.get("done"):
                                    break
                            except Exception:
                                pass
                ai_placeholder.markdown(ai_text)
            except requests.exceptions.ConnectionError:
                st.error(T("ollama_unreachable"))
            except Exception as ai_err:
                st.error(T("ai_error", err=ai_err))

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
        st.download_button(T("export_csv"), data=csv_bytes, file_name=fname, mime="text/csv")
        # ── SALVA TERRENO ─────────────────────────────────────
        st.subheader(T("save_land"))
        if db_ok:
            nota_input = st.text_area(T("note_optional"), key="nota_salvataggio", height=80)
            if st.button(T("save_to_archive"), key="save_parcel_btn"):
                conn_s = get_pg_conn()
                if conn_s:
                    try:
                        with conn_s.cursor() as cur:
                            cur.execute("""
                                INSERT INTO saved_parcels
                                (lat, lon, indirizzo, zona_code, zona_name, desa,
                                 superficie_m2, prezzo_idr, roi_pct, walk_score,
                                 noise_level, elevazione_m, bpn_tipehak, densita_1km, note)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """, (
                                lat_in, lon_in,
                                st.session_state.get("geo_label", ""),
                                zone_code, zone_name, desa,
                                li_size, li_price,
                                gs.get("roi") if "gs" in locals() else None,
                                walk_score if "walk_score" in locals() else None,
                                noise_label if "noise_label" in locals() else None,
                                elev_m if "elev_m" in locals() else None,
                                bpn_feats[0].get("properties", {}).get("tipehak") if bpn_feats else None,
                                density_results.get("1km") if "density_results" in locals() else None,
                                nota_input or None,
                            ))
                            conn_s.commit()
                        st.success(T("land_saved"))
                    except Exception as save_err:
                        st.error(T("save_error", err=save_err))
                    finally:
                        conn_s.close()
                else:
                    st.warning(T("pg_unreachable"))
        else:
            st.caption(T("db_unavailable"))

        # ── ANALYTICS LOG (silent) ────────────────────────────
        _log_analytics_lookup(
            user_email="dashboard_user",
            kbli_code=st.session_state.get("kbli_compliance_input"),
            location=f"{lat_in},{lon_in}",
            notes=f"zone={zone_code}, size={li_size}m2",
        )

        # ── PDF EXPORT ────────────────────────────────────────
        pdf_data = {
            "timestamp": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
            "lat": lat_in,
            "lon": lon_in,
            "zona_code": zone_code,
            "zona_name": zone_name,
            "desa": desa,
            "kdb": kdb, "klb": klb, "kdh": kdh, "tb": tb, "gsb": gsb,
            "superficie_m2": li_size,
            "prezzo_idr": li_price,
            "prezzo_usd": round(li_price * fx_usd, 0) if fx_usd else None,
            "roi_pct": gs.get("roi") if "gs" in locals() else None,
            "break_even": gs.get("bey") if "gs" in locals() else None,
            "strategia": f"{gs.get('build','')} + {gs.get('yield','')}" if "gs" in locals() else None,
            "bpn_tipehak": bpn_feats[0].get("properties", {}).get("tipehak") if bpn_feats else None,
            "bpn_luas": bpn_feats[0].get("properties", {}).get("luas") if bpn_feats else None,
            "bpn_nomor": bpn_feats[0].get("properties", {}).get("nomor") if bpn_feats else None,
            "bpn_tahun": bpn_feats[0].get("properties", {}).get("tahun") if bpn_feats else None,
            "walk_score": walk_score if "walk_score" in locals() else None,
            "noise_label": noise_label if "noise_label" in locals() else None,
            "elev_m": elev_m if "elev_m" in locals() else None,
            "dist_coast_km": dist_coast_km if "dist_coast_km" in locals() else None,
            "densita_500m": density_results.get("500m") if "density_results" in locals() else None,
            "densita_1km": density_results.get("1km") if "density_results" in locals() else None,
            "densita_2km": density_results.get("2km") if "density_results" in locals() else None,
            "vincoli": list(vincoli.keys()) if "vincoli" in locals() and vincoli else [],
        }
        # Enrich with KBLI data if available
        _kbli_session = st.session_state.get("kbli_compliance_input", "").strip()
        if _kbli_session:
            pdf_data["kbli_code"] = _kbli_session
            # Try to get cached KBLI result
            try:
                _kr = requests.post(
                    f"{API_URL}/api/dashboard/map/validate-property",
                    json={"kbli_code": _kbli_session, "is_pma": True, "location": "Bali"},
                    timeout=3,
                )
                if _kr.status_code == 200:
                    _kd = _kr.json()
                    _au = _kd.get("audit", _kd)
                    pdf_data["kbli_title"] = _kd.get("title", "")
                    pdf_data["kbli_state"] = _au.get("state", "")
                    pdf_data["kbli_reason"] = _au.get("reason_code", "")
                    pdf_data["kbli_oss_risk"] = _au.get("oss_risk", "")
                    pdf_data["kbli_max_foreign"] = _kd.get("pma_logic", {}).get("max_foreign_ownership", "")
            except Exception:
                pass
        # Enrich with investment analysis if available
        try:
            _inv_payload = {"lat": lat_in, "lon": lon_in, "is_pma": True, "land_size_m2": li_size, "price_idr": li_price}
            if _kbli_session:
                _inv_payload["kbli_code"] = _kbli_session
            _ir = requests.post(f"{API_URL}/api/dashboard/map/analyze-investment", json=_inv_payload, timeout=20)
            if _ir.status_code == 200:
                _inv = _ir.json()
                _v = _inv.get("verdict", {})
                pdf_data["invest_score"] = _v.get("score")
                pdf_data["invest_risk"] = _v.get("risk_level")
                pdf_data["invest_summary"] = _v.get("summary", "")
        except Exception:
            pass
        try:
            pdf_bytes = generate_pdf(pdf_data)
            pdf_fname = f"land_intel_{lat_in:.4f}_{lon_in:.4f}_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf"
            st.download_button(T("export_pdf"), data=pdf_bytes, file_name=pdf_fname, mime="application/pdf")
        except Exception as pdf_err:
            st.warning(T("pdf_error", err=pdf_err))



elif mode == "🧭 Zone Finder":
    st.title(T("opp_finder_title"))
    st.caption(T("opp_finder_caption"))

    col1, col2 = st.columns(2)
    with col1:
        budget = st.slider(T("total_budget_usd"), 50_000, 1_000_000, 250_000, step=10_000,
                           format="$%d")
    with col2:
        min_roi = st.slider(T("target_roi_min"), 5.0, 20.0, 10.0, step=0.5)

    if st.button(T("start_scan"), use_container_width=True):
        with st.spinner(T("scanning_db")):
            try:
                payload = {"budget_usd": budget, "min_roi": min_roi}
                resp = requests.post(f"{API_URL}/finder", json=payload, timeout=15).json()
                hits = resp.get("top_opportunities", [])

                if hits:
                    st.success(T("assets_found", found=resp['found'], top=min(10, len(hits))))
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
                        with st.expander(T("zones_to_exclude")):
                            for z in avoid:
                                st.markdown(f"**{z['zone_code']}** — {z['zone_name']}: {z['reason']}")
                else:
                    st.warning(T("no_targets_found"))
            except Exception as e:
                st.error(T("api_error", err=e))

elif mode == "🧮 ROI Calculator":
    st.title(T("deep_analysis_title"))
    st.caption(T("deep_analysis_caption"))

    c1, c2, c3 = st.columns(3)
    with c1:
        zone = st.selectbox(T("urban_zone"), zone_options)
    with c2:
        size = st.number_input(T("area_m2"), min_value=100, max_value=10_000, value=500, step=50)
    with c3:
        price = st.number_input(
            T("total_land_price"),
            min_value=100_000_000,
            max_value=100_000_000_000,
            value=3_250_000_000,
            step=50_000_000,
            format="%d",
        )

    if st.button(T("generate_matrix"), use_container_width=True):
        with st.spinner(T("calculating")):
            payload = {"land_size_m2": size, "price_total_idr": price, "zone_code": zone}
            try:
                resp = requests.post(f"{API_URL}/calculator", json=payload, timeout=15).json()

                zi = resp.get("zone_info", {})
                urb = resp.get("urbanistica", {})
                gs = resp.get("golden_strategy", {})

                col_u, col_g = st.columns(2)
                with col_u:
                    st.subheader(T("urban_params_table"))
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
                    st.subheader(T("optimal_strategy"))
                    st.metric(T("max_roi"), f"{gs.get('roi', 0):.2f}%")
                    st.metric(T("break_even"), f"{gs.get('bey', 0):.1f} {T('years')}")
                    st.info(f"**{gs.get('build')}** + **{gs.get('yield')}**")

                st.subheader(T("sensitivity_matrix"))
                matrix = resp.get("sensitivity_matrix", {})
                rows = []
                for bk, yields in matrix.items():
                    row = {T("construction_cost"): bk.replace("_", " ")}
                    for yk, m in yields.items():
                        roi = m["roi_pct"]
                        tag = " 🔥" if roi >= 12 else " ✅" if roi >= 8 else " 🟡" if roi >= 4 else " 🔴"
                        row[yk.replace("_", " ")] = f"{roi:.2f}%{tag}"
                    rows.append(row)
                st.table(pd.DataFrame(rows).set_index(T("construction_cost")))

                with st.expander(T("fx_history_12m")):
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
                            st.caption(T("fx_variation", delta=f"{delta_pct:+.1f}", latest=f"{latest:,.0f}"))
                    except Exception:
                        st.caption(T("history_unavailable"))

            except Exception as e:
                st.error(T("calc_error", err=e))

elif mode == "🛰️ Geo-Compare":
    st.title(T("geo_compare_title"))
    st.caption(T("geo_compare_caption"))

    col_params, col_map = st.columns([1, 1.5])

    with col_params:
        st.subheader(T("asset_params"))
        t1, t2 = st.tabs(["Asset A (Blu)", "Asset B (Rosso)"])

        with t1:
            zA = st.selectbox("Zona A", zone_options, key="zA")
            sA = st.number_input(f"{T('area_m2')} A", min_value=100, value=500, key="sA")
            pA = st.number_input(f"{T('price')} A (IDR)", min_value=100_000_000, value=3_250_000_000,
                                 step=50_000_000, format="%d", key="pA")
            st.markdown(f"**{T('gps_coordinates')}**")
            latA = st.number_input("Lat A", value=-8.64300, format="%.5f", key="latA")
            lonA = st.number_input("Lon A", value=115.14100, format="%.5f", key="lonA")

        with t2:
            zB_idx = min(1, len(zone_options) - 1)
            zB = st.selectbox("Zona B", zone_options, index=zB_idx, key="zB")
            sB = st.number_input(f"{T('area_m2')} B", min_value=100, value=500, key="sB")
            pB = st.number_input(f"{T('price')} B (IDR)", min_value=100_000_000, value=9_000_000_000,
                                 step=50_000_000, format="%d", key="pB")
            st.markdown(f"**{T('gps_coordinates')}**")
            latB = st.number_input("Lat B", value=-8.65300, format="%.5f", key="latB")
            lonB = st.number_input("Lon B", value=115.12300, format="%.5f", key="lonB")

        btn_calc = st.button(T("calculate_delta"), use_container_width=True, type="primary")

    with col_map:
        st.subheader(T("satellite_view"))

        kec_options = {
            "Kuta Utara (default)": "Kuta Utara",
            "Kuta": "Kuta",
            "Kuta Selatan": "Kuta Selatan",
            "Mengwi": "Mengwi",
            "Abiansemal": "Abiansemal",
            "Petang": "Petang",
            T("all_badung_slow"): "all",
        }
        kec_sel = st.selectbox(T("load_rdtr_for"), list(kec_options.keys()), key="kec_filter")
        kec_filter = kec_options[kec_sel]

        center_lat = (latA + latB) / 2
        center_lon = (lonA + lonB) / 2

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=14,
            tiles=None,
        )

        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google",
            name="🛰️ Google Satellite",
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
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google",
            name="🛰️ Google Hybrid",
            overlay=False,
            control=True,
        ).add_to(m)

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
            name="Zone RDTR (Badung)",
            style_function=rdtr_style,
            tooltip=GeoJsonTooltip(
                fields=["_zone_code", "_zone_name"],
                aliases=["Zona:", "Denominazione:"],
                localize=True,
                sticky=True,
                style="font-size:12px; font-weight:bold;",
            ),
        ).add_to(m)

        tabanan_data_cmp = load_tabanan_geojson()
        if tabanan_data_cmp["features"]:
            def tabanan_style_cmp(feature):
                color = feature["properties"].get("_zone_color", "#cccccc")
                return {"fillColor": color, "color": color, "weight": 1.0, "fillOpacity": 0.40, "dashArray": "4"}

            GeoJson(
                tabanan_data_cmp,
                name="Zone OSM (Tabanan — 10 kec.)",
                style_function=tabanan_style_cmp,
                tooltip=GeoJsonTooltip(
                    fields=["_zone_code", "_zone_name", "_source"],
                    aliases=["Zona:", "Nome:", "Fonte:"],
                    sticky=True,
                    style="font-size:12px; font-weight:bold;",
                ),
            ).add_to(m)

        denpasar_data_cmp = load_denpasar_geojson()
        if denpasar_data_cmp["features"]:
            def denpasar_style_cmp(feature):
                color = feature["properties"].get("_zone_color", "#cccccc")
                return {"fillColor": color, "color": color, "weight": 1.0, "fillOpacity": 0.40, "dashArray": "2"}

            GeoJson(
                denpasar_data_cmp,
                name="Zone OSM (Denpasar — 4 kec.)",
                style_function=denpasar_style_cmp,
                tooltip=GeoJsonTooltip(
                    fields=["_zone_code", "_zone_name", "_source"],
                    aliases=["Zona:", "Nome:", "Fonte:"],
                    sticky=True,
                    style="font-size:12px; font-weight:bold;",
                ),
            ).add_to(m)

        folium.Marker(
            [latA, lonA],
            popup=folium.Popup(f"<b>Asset A</b><br>Zona: {zA}<br>{sA} m²", max_width=200),
            tooltip="Asset A",
            icon=folium.Icon(color="blue", icon="home", prefix="fa"),
        ).add_to(m)

        folium.Marker(
            [latB, lonB],
            popup=folium.Popup(f"<b>Asset B</b><br>Zona: {zB}<br>{sB} m²", max_width=200),
            tooltip="Asset B",
            icon=folium.Icon(color="red", icon="home", prefix="fa"),
        ).add_to(m)

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

    if btn_calc:
        payload = {
            "option_a": {"land_size_m2": sA, "price_total_idr": pA, "zone_code": zA},
            "option_b": {"land_size_m2": sB, "price_total_idr": pB, "zone_code": zB},
        }
        with st.spinner(T("differential_analysis")):
            try:
                resp = requests.post(f"{API_URL}/compare", json=payload, timeout=15).json()
                winner  = resp["winner"]
                comp    = resp["comparison"]
                verdict = resp["verdict"]

                st.divider()

                if winner == "TIE":
                    bg, border, label = "rgba(255,243,205,0.6)", "orange", T("technical_tie")
                elif winner == "A":
                    bg, border, label = "rgba(209,231,221,0.6)", "green", T("asset_a_dominant")
                else:
                    bg, border, label = "rgba(248,215,218,0.6)", "red", T("asset_b_dominant")

                st.markdown(f"""
                <div style="background:{bg}; padding:16px; border-radius:8px;
                            border-left:5px solid {border}; margin-bottom:16px;">
                    <h3 style="margin:0 0 6px 0">{label}</h3>
                    <p style="margin:0; color:#444">{verdict}</p>
                </div>
                """, unsafe_allow_html=True)

                k1, k2, k3, k4 = st.columns(4)
                roi_delta = comp["roi_best_scenario"]["delta"]
                bey_delta = comp["break_even_years"]["delta"]

                k1.metric("ROI Netto — A", comp["roi_best_scenario"]["A"],
                          delta=roi_delta if winner == "A" else None)
                k2.metric("ROI Netto — B", comp["roi_best_scenario"]["B"],
                          delta=roi_delta if winner == "B" else None)
                k3.metric("Break Even — A", comp["break_even_years"]["A"])
                k4.metric("Break Even — B", comp["break_even_years"]["B"])

                k5, k6, k7, k8 = st.columns(4)
                k5.metric("Investimento — A", comp["total_investment"]["A"])
                k6.metric("Investimento — B", comp["total_investment"]["B"])
                k7.metric("Net Annuo — A", comp["net_annual"]["A"])
                k8.metric("Net Annuo — B", comp["net_annual"]["B"])

                with st.expander(T("all_scenarios_detail")):
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
                st.error(T("analysis_error", err=e))

elif mode == "📌 Saved Parcels":
    st.title(T("saved_parcels_title"))
    st.caption(T("saved_parcels_caption"))

    if not db_ok:
        st.warning(T("pg_unreachable"))
        st.stop()

    conn_view = get_pg_conn()
    if not conn_view:
        st.error(T("db_connection_failed"))
        st.stop()

    try:
        df_parcels = pd.read_sql(
            "SELECT * FROM saved_parcels ORDER BY saved_at DESC",
            conn_view,
        )
        conn_view.close()
    except Exception as e:
        st.error(T("db_read_error", err=e))
        st.stop()

    if df_parcels.empty:
        st.info(T("no_saved_lands"))
    else:
        _all_label = T("all_zones")
        zone_filter = st.selectbox(
            T("filter_by_zone"),
            [_all_label] + sorted(df_parcels["zona_code"].dropna().unique().tolist()),
        )
        if zone_filter != _all_label:
            df_parcels = df_parcels[df_parcels["zona_code"] == zone_filter]

        st.caption(T("lands_found", count=len(df_parcels)))

        for _, row in df_parcels.iterrows():
            with st.expander(f"📍 {row['zona_code']} — {row['indirizzo'] or str(round(row['lat'],4)) + ', ' + str(round(row['lon'],4))} | {pd.to_datetime(row['saved_at']).strftime('%d/%m/%Y')}"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(T("surface"), f"{row['superficie_m2']} m²")
                c2.metric(T("price"), f"IDR {row['prezzo_idr']:,.0f}" if row['prezzo_idr'] else "—")
                c3.metric("ROI", f"{row['roi_pct']:.2f}%" if row['roi_pct'] else "—")
                c4.metric(T("walk_score"), f"{row['walk_score']}/100" if row['walk_score'] else "—")

                c5, c6, c7 = st.columns(3)
                c5.metric("Noise", row['noise_level'] or "—")
                c6.metric("Elevazione", f"{row['elevazione_m']:.1f} m" if row['elevazione_m'] else "—")
                c7.metric("Densità 1km", row['densita_1km'] if row['densita_1km'] else "—")

                if row['bpn_tipehak']:
                    st.caption(f"BPN: {row['bpn_tipehak']}")

                if row['note']:
                    st.info(f"📝 {row['note']}")

                new_note = st.text_input(T("edit_note"), value=row['note'] or "", key=f"note_{row['id']}")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(T("update_note"), key=f"upd_{row['id']}"):
                        conn_u = get_pg_conn()
                        if conn_u:
                            try:
                                with conn_u.cursor() as cur:
                                    cur.execute("UPDATE saved_parcels SET note=%s WHERE id=%s", (new_note, row['id']))
                                    conn_u.commit()
                                st.success(T("note_updated"))
                                st.rerun()
                            finally:
                                conn_u.close()
                with col_btn2:
                    if st.button(T("delete"), key=f"del_{row['id']}"):
                        conn_d = get_pg_conn()
                        if conn_d:
                            try:
                                with conn_d.cursor() as cur:
                                    cur.execute("DELETE FROM saved_parcels WHERE id=%s", (row['id'],))
                                    conn_d.commit()
                                st.success(T("land_deleted"))
                                st.rerun()
                            finally:
                                conn_d.close()

