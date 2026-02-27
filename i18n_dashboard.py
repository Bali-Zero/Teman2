"""
i18n translations for Nuzantara Prime dashboard.

Usage:
    from i18n_dashboard import T, set_language
    set_language("en")  # or "it", "id"
    st.title(T("land_intel_title"))
"""

from typing import Dict

_current_lang: str = "it"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ── Sidebar ───────────────────────────────────────────────────────
    "sidebar_status": {
        "it": "Status: ONLINE 🟢",
        "en": "Status: ONLINE 🟢",
        "id": "Status: ONLINE 🟢",
    },
    "sidebar_module": {
        "it": "Modulo:",
        "en": "Module:",
        "id": "Modul:",
    },
    "sidebar_fx": {
        "it": "💱 Cambio live",
        "en": "💱 Live FX Rate",
        "id": "💱 Kurs Live",
    },
    "sidebar_fx_unavailable": {
        "it": "FX non disponibile",
        "en": "FX rate unavailable",
        "id": "Kurs tidak tersedia",
    },
    "sidebar_stats": {
        "it": "📊 Dashboard Stats",
        "en": "📊 Dashboard Stats",
        "id": "📊 Statistik Dashboard",
    },
    "sidebar_active_clients": {
        "it": "Clienti Attivi",
        "en": "Active Clients",
        "id": "Klien Aktif",
    },
    "sidebar_open_practices": {
        "it": "Pratiche Aperte",
        "en": "Open Practices",
        "id": "Praktik Terbuka",
    },
    "sidebar_lookups_24h": {
        "it": "Lookup 24h",
        "en": "Lookups 24h",
        "id": "Pencarian 24j",
    },
    "sidebar_stats_unavailable": {
        "it": "Stats non disponibili",
        "en": "Stats unavailable",
        "id": "Statistik tidak tersedia",
    },
    "sidebar_api_offline": {
        "it": "API Offline — avvia main.py",
        "en": "API Offline — start main.py",
        "id": "API Offline — jalankan main.py",
    },

    # ── Land Intel ────────────────────────────────────────────────────
    "land_intel_title": {
        "it": "📍 Land Intel",
        "en": "📍 Land Intel",
        "id": "📍 Land Intel",
    },
    "land_intel_caption": {
        "it": "Inserisci le coordinate GPS di un terreno. Il sistema interroga BATARA live e calcola tutto.",
        "en": "Enter the GPS coordinates of a plot. The system queries BATARA live and calculates everything.",
        "id": "Masukkan koordinat GPS lahan. Sistem akan query BATARA live dan menghitung semuanya.",
    },
    "localization": {
        "it": "Localizzazione",
        "en": "Location",
        "id": "Lokasi",
    },
    "search_address": {
        "it": "🔎 Cerca indirizzo o luogo",
        "en": "🔎 Search address or place",
        "id": "🔎 Cari alamat atau tempat",
    },
    "search_placeholder": {
        "it": "es. Jl. Batu Bolong 47 Canggu, Finns Beach Club...",
        "en": "e.g. Jl. Batu Bolong 47 Canggu, Finns Beach Club...",
        "id": "mis. Jl. Batu Bolong 47 Canggu, Finns Beach Club...",
    },
    "search": {
        "it": "Cerca",
        "en": "Search",
        "id": "Cari",
    },
    "place_not_found": {
        "it": "Luogo non trovato. Prova con un indirizzo più specifico.",
        "en": "Place not found. Try a more specific address.",
        "id": "Tempat tidak ditemukan. Coba alamat yang lebih spesifik.",
    },
    "geocoding_unavailable": {
        "it": "Geocoding non disponibile.",
        "en": "Geocoding unavailable.",
        "id": "Geocoding tidak tersedia.",
    },
    "latitude": {
        "it": "Latitudine",
        "en": "Latitude",
        "id": "Lintang",
    },
    "longitude": {
        "it": "Longitudine",
        "en": "Longitude",
        "id": "Bujur",
    },
    "land_data": {
        "it": "Dati Terreno",
        "en": "Land Data",
        "id": "Data Lahan",
    },
    "area_m2": {
        "it": "Superficie (m²)",
        "en": "Area (m²)",
        "id": "Luas (m²)",
    },
    "asking_price_idr": {
        "it": "Prezzo Richiesto (IDR)",
        "en": "Asking Price (IDR)",
        "id": "Harga (IDR)",
    },
    "analyze_land": {
        "it": "🔍 ANALIZZA TERRENO",
        "en": "🔍 ANALYZE LAND",
        "id": "🔍 ANALISIS LAHAN",
    },
    "map": {
        "it": "Mappa",
        "en": "Map",
        "id": "Peta",
    },
    "querying_batara": {
        "it": "Interrogazione BATARA in corso...",
        "en": "Querying BATARA...",
        "id": "Mengquery BATARA...",
    },
    "batara_no_data": {
        "it": "BATARA non ha restituito dati per queste coordinate. Prova a spostare il punto.",
        "en": "BATARA returned no data for these coordinates. Try moving the point.",
        "id": "BATARA tidak mengembalikan data untuk koordinat ini. Coba geser titiknya.",
    },
    "urban_params": {
        "it": "Parametri Urbanistici (BATARA live)",
        "en": "Urban Parameters (BATARA live)",
        "id": "Parameter Tata Ruang (BATARA live)",
    },
    "max_height": {
        "it": "Altezza Max",
        "en": "Max Height",
        "id": "Tinggi Maks",
    },
    "flood_risk_high": {
        "it": "⚠️ Rischio alluvione alto",
        "en": "⚠️ High flood risk",
        "id": "⚠️ Risiko banjir tinggi",
    },
    "low_zone_check": {
        "it": "🟡 Zona bassa — verificare",
        "en": "🟡 Low zone — verify",
        "id": "🟡 Zona rendah — perlu verifikasi",
    },
    "safe_elevation": {
        "it": "✅ Elevazione sicura",
        "en": "✅ Safe elevation",
        "id": "✅ Elevasi aman",
    },
    "elevation_asl": {
        "it": "Elevazione slm",
        "en": "Elevation ASL",
        "id": "Elevasi dpl",
    },
    "coast_distance": {
        "it": "Distanza costa",
        "en": "Coast distance",
        "id": "Jarak pantai",
    },
    "sea_view_possible": {
        "it": "🌊 Possibile vista mare",
        "en": "🌊 Possible sea view",
        "id": "🌊 Kemungkinan pemandangan laut",
    },
    "elevation_unavailable": {
        "it": "Elevazione non disponibile.",
        "en": "Elevation unavailable.",
        "id": "Elevasi tidak tersedia.",
    },
    "roi_projected": {
        "it": "ROI Proiettato",
        "en": "Projected ROI",
        "id": "ROI Proyeksi",
    },
    "optimal_roi": {
        "it": "ROI Ottimale",
        "en": "Optimal ROI",
        "id": "ROI Optimal",
    },
    "break_even": {
        "it": "Break Even",
        "en": "Break Even",
        "id": "Break Even",
    },
    "years": {
        "it": "anni",
        "en": "years",
        "id": "tahun",
    },
    "roi_unavailable": {
        "it": "Calcolo ROI non disponibile per questa zona.",
        "en": "ROI calculation unavailable for this zone.",
        "id": "Perhitungan ROI tidak tersedia untuk zona ini.",
    },
    "zone_not_in_roi_db": {
        "it": "Zona {zone_code} non nel database ROI (non edificabile o non residenziale).",
        "en": "Zone {zone_code} not in ROI database (non-buildable or non-residential).",
        "id": "Zona {zone_code} tidak ada di database ROI (tidak bisa dibangun atau non-residensial).",
    },
    "sensitivity_matrix": {
        "it": "Sensitivity Matrix — ROI Netto",
        "en": "Sensitivity Matrix — Net ROI",
        "id": "Sensitivity Matrix — ROI Bersih",
    },
    "construction_cost": {
        "it": "Costo Costruzione",
        "en": "Construction Cost",
        "id": "Biaya Konstruksi",
    },
    "constraints_detected": {
        "it": "⚠️ Vincoli e Overlay rilevati",
        "en": "⚠️ Constraints & Overlays detected",
        "id": "⚠️ Kendala & Overlay terdeteksi",
    },
    "no_constraints": {
        "it": "Nessun vincolo overlay rilevato (KKOP, LP2B, KRB, ecc.)",
        "en": "No overlay constraints detected (KKOP, LP2B, KRB, etc.)",
        "id": "Tidak ada kendala overlay terdeteksi (KKOP, LP2B, KRB, dll.)",
    },
    "overlay_kkop": {
        "it": "KKOP (Zona Aeroporto)",
        "en": "KKOP (Airport Zone)",
        "id": "KKOP (Kawasan Keselamatan Operasi Penerbangan)",
    },
    "overlay_lp2b": {
        "it": "LP2B (Lahan Pertanian)",
        "en": "LP2B (Agricultural Land)",
        "id": "LP2B (Lahan Pertanian Pangan Berkelanjutan)",
    },
    "overlay_krb": {
        "it": "KRB (Rawan Bencana)",
        "en": "KRB (Disaster Prone)",
        "id": "KRB (Kawasan Rawan Bencana)",
    },
    "overlay_teb": {
        "it": "Sempadan Tebing",
        "en": "Cliff Setback",
        "id": "Sempadan Tebing",
    },
    "overlay_cagbud": {
        "it": "Cagar Budaya",
        "en": "Cultural Heritage",
        "id": "Cagar Budaya",
    },
    "overlay_resair": {
        "it": "Resapan Air",
        "en": "Water Infiltration",
        "id": "Resapan Air",
    },

    # ── KBLI Compliance ───────────────────────────────────────────────
    "kbli_compliance_title": {
        "it": "📋 Verifica Compliance KBLI",
        "en": "📋 KBLI Compliance Check",
        "id": "📋 Cek Kepatuhan KBLI",
    },
    "kbli_code_input": {
        "it": "Codice KBLI (opzionale — es. 55203)",
        "en": "KBLI Code (optional — e.g. 55203)",
        "id": "Kode KBLI (opsional — mis. 55203)",
    },
    "pma_foreign": {
        "it": "PMA (straniero)",
        "en": "PMA (foreign)",
        "id": "PMA (asing)",
    },
    "verify_compliance": {
        "it": "🔍 Verifica Compliance",
        "en": "🔍 Verify Compliance",
        "id": "🔍 Cek Kepatuhan",
    },
    "reason": {
        "it": "Motivo",
        "en": "Reason",
        "id": "Alasan",
    },
    "oss_risk": {
        "it": "Rischio OSS",
        "en": "OSS Risk",
        "id": "Risiko OSS",
    },
    "max_foreign_ownership": {
        "it": "Max proprietà straniera",
        "en": "Max foreign ownership",
        "id": "Maks kepemilikan asing",
    },
    "umkm_reserved": {
        "it": "UMKM riservato",
        "en": "UMKM reserved",
        "id": "Dicadangkan UMKM",
    },
    "yes": {
        "it": "Sì",
        "en": "Yes",
        "id": "Ya",
    },
    "no": {
        "it": "No",
        "en": "No",
        "id": "Tidak",
    },
    "backend_error": {
        "it": "Errore nella risposta backend.",
        "en": "Backend response error.",
        "id": "Error respons backend.",
    },
    "backend_unreachable_kbli": {
        "it": "Backend non raggiungibile per verifica KBLI.",
        "en": "Backend unreachable for KBLI verification.",
        "id": "Backend tidak dapat dijangkau untuk verifikasi KBLI.",
    },
    "kbli_unavailable": {
        "it": "Verifica KBLI non disponibile: {err}",
        "en": "KBLI verification unavailable: {err}",
        "id": "Verifikasi KBLI tidak tersedia: {err}",
    },
    "enter_kbli_code": {
        "it": "Inserisci un codice KBLI per verificare la compliance.",
        "en": "Enter a KBLI code to verify compliance.",
        "id": "Masukkan kode KBLI untuk cek kepatuhan.",
    },

    # ── Investment Analysis ────────────────────────────────────────────
    "invest_title": {
        "it": "🎯 Analisi Investimento Completa",
        "en": "🎯 Full Investment Analysis",
        "id": "🎯 Analisis Investasi Lengkap",
    },
    "invest_caption": {
        "it": "Zona RDTR + Compliance KBLI + ROI in un'unica analisi",
        "en": "RDTR Zone + KBLI Compliance + ROI in a single analysis",
        "id": "Zona RDTR + Kepatuhan KBLI + ROI dalam satu analisis",
    },
    "investable": {
        "it": "INVESTIBILE",
        "en": "INVESTABLE",
        "id": "LAYAK INVESTASI",
    },
    "not_investable": {
        "it": "NON INVESTIBILE",
        "en": "NOT INVESTABLE",
        "id": "TIDAK LAYAK INVESTASI",
    },
    "zone_rdtr": {
        "it": "🗺️ Zona RDTR",
        "en": "🗺️ RDTR Zone",
        "id": "🗺️ Zona RDTR",
    },
    "zone": {
        "it": "Zona",
        "en": "Zone",
        "id": "Zona",
    },
    "batara_unavailable": {
        "it": "BATARA non disponibile",
        "en": "BATARA unavailable",
        "id": "BATARA tidak tersedia",
    },
    "kbli_compliance": {
        "it": "📋 KBLI Compliance",
        "en": "📋 KBLI Compliance",
        "id": "📋 Kepatuhan KBLI",
    },
    "status": {
        "it": "Stato",
        "en": "Status",
        "id": "Status",
    },
    "no_kbli_provided": {
        "it": "Nessun codice KBLI fornito",
        "en": "No KBLI code provided",
        "id": "Kode KBLI tidak diberikan",
    },
    "roi_projection": {
        "it": "📈 ROI Proiezione",
        "en": "📈 ROI Projection",
        "id": "📈 Proyeksi ROI",
    },
    "roi_not_calculable": {
        "it": "ROI non calcolabile: {err}",
        "en": "ROI not calculable: {err}",
        "id": "ROI tidak dapat dihitung: {err}",
    },
    "insufficient_data_roi": {
        "it": "Dati insufficienti per calcolo ROI",
        "en": "Insufficient data for ROI calculation",
        "id": "Data tidak cukup untuk perhitungan ROI",
    },
    "score_breakdown": {
        "it": "📊 Dettaglio Score (7 fattori)",
        "en": "📊 Score Breakdown (7 factors)",
        "id": "📊 Detail Skor (7 faktor)",
    },
    "backend_http_error": {
        "it": "Errore backend: HTTP {code}",
        "en": "Backend error: HTTP {code}",
        "id": "Error backend: HTTP {code}",
    },
    "backend_unreachable_invest": {
        "it": "Backend non raggiungibile per analisi investimento.",
        "en": "Backend unreachable for investment analysis.",
        "id": "Backend tidak dapat dijangkau untuk analisis investasi.",
    },
    "invest_unavailable": {
        "it": "Analisi investimento non disponibile: {err}",
        "en": "Investment analysis unavailable: {err}",
        "id": "Analisis investasi tidak tersedia: {err}",
    },

    # ── Walk Score / Urban Context ─────────────────────────────────────
    "urban_context": {
        "it": "🏃 Contesto Urbano",
        "en": "🏃 Urban Context",
        "id": "🏃 Konteks Perkotaan",
    },
    "silent": {
        "it": "🟢 Silenzioso",
        "en": "🟢 Quiet",
        "id": "🟢 Tenang",
    },
    "moderate": {
        "it": "🟡 Moderato",
        "en": "🟡 Moderate",
        "id": "🟡 Sedang",
    },
    "noisy": {
        "it": "🔴 Rumoroso",
        "en": "🔴 Noisy",
        "id": "🔴 Berisik",
    },
    "noise_yield_quiet": {
        "it": "+3% yield stimato",
        "en": "+3% estimated yield",
        "id": "+3% yield estimasi",
    },
    "noise_yield_moderate": {
        "it": "neutro",
        "en": "neutral",
        "id": "netral",
    },
    "noise_yield_noisy": {
        "it": "-5% yield stimato (vacanze brevi)",
        "en": "-5% estimated yield (short stays)",
        "id": "-5% yield estimasi (sewa jangka pendek)",
    },
    "walk_excellent": {
        "it": "🟢 Eccellente",
        "en": "🟢 Excellent",
        "id": "🟢 Sangat Baik",
    },
    "walk_good": {
        "it": "🟡 Buono",
        "en": "🟡 Good",
        "id": "🟡 Baik",
    },
    "walk_isolated": {
        "it": "🔴 Isolato",
        "en": "🔴 Isolated",
        "id": "🔴 Terpencil",
    },
    "walk_score": {
        "it": "Walk Score",
        "en": "Walk Score",
        "id": "Walk Score",
    },
    "noise_level": {
        "it": "Livello Rumore",
        "en": "Noise Level",
        "id": "Tingkat Kebisingan",
    },
    "urban_context_unavailable": {
        "it": "Contesto urbano non disponibile: {err}",
        "en": "Urban context unavailable: {err}",
        "id": "Konteks perkotaan tidak tersedia: {err}",
    },

    # ── BPN Catasto ────────────────────────────────────────────────────
    "bpn_catasto": {
        "it": "🏛️ Catasto BPN (Bidang Tanah)",
        "en": "🏛️ BPN Land Registry",
        "id": "🏛️ Bidang Tanah BPN",
    },
    "registration_year": {
        "it": "Anno Registrazione",
        "en": "Registration Year",
        "id": "Tahun Registrasi",
    },
    "accuracy": {
        "it": "Akurasi",
        "en": "Accuracy",
        "id": "Akurasi",
    },
    "certificate_number": {
        "it": "Nomor Sertifikat",
        "en": "Certificate Number",
        "id": "Nomor Sertifikat",
    },
    "no_bpn_parcel": {
        "it": "Nessuna parcella BPN trovata in questo punto. La parcella potrebbe non essere ancora registrata o digitalizzata.",
        "en": "No BPN parcel found at this point. The parcel may not be registered or digitized yet.",
        "id": "Tidak ada bidang tanah BPN di titik ini. Bidang tanah mungkin belum terdaftar atau terdigitalisasi.",
    },
    "bpn_unreachable": {
        "it": "BPN non raggiungibile: {err}",
        "en": "BPN unreachable: {err}",
        "id": "BPN tidak dapat dijangkau: {err}",
    },

    # ── Tourism Density ────────────────────────────────────────────────
    "tourism_density": {
        "it": "🏠 Densità Mercato Turistico",
        "en": "🏠 Tourism Market Density",
        "id": "🏠 Kepadatan Pasar Wisata",
    },
    "saturated_zone": {
        "it": "🔴 Zona satura",
        "en": "🔴 Saturated zone",
        "id": "🔴 Zona jenuh",
    },
    "active_market": {
        "it": "🟡 Mercato attivo",
        "en": "🟡 Active market",
        "id": "🟡 Pasar aktif",
    },
    "low_competition": {
        "it": "🟢 Bassa competizione",
        "en": "🟢 Low competition",
        "id": "🟢 Kompetisi rendah",
    },
    "structures_within": {
        "it": "Strutture entro {radius}",
        "en": "Structures within {radius}",
        "id": "Fasilitas dalam {radius}",
    },
    "osm_source_note": {
        "it": "Fonte: OpenStreetMap — ville, guest house e hotel censiti. Non include proprietà non mappate.",
        "en": "Source: OpenStreetMap — listed villas, guest houses and hotels. Does not include unmapped properties.",
        "id": "Sumber: OpenStreetMap — villa, guest house dan hotel yang terdaftar. Tidak termasuk properti yang belum dipetakan.",
    },
    "density_unavailable": {
        "it": "Dati densità non disponibili momentaneamente.",
        "en": "Density data temporarily unavailable.",
        "id": "Data kepadatan sementara tidak tersedia.",
    },
    "osm_unreachable": {
        "it": "OSM non raggiungibile: {err}",
        "en": "OSM unreachable: {err}",
        "id": "OSM tidak dapat dijangkau: {err}",
    },

    # ── AI Assessment ──────────────────────────────────────────────────
    "ai_assessment": {
        "it": "🤖 AI Assessment",
        "en": "🤖 AI Assessment",
        "id": "🤖 Penilaian AI",
    },
    "ai_caption": {
        "it": "Analisi sintetica generata da Qwen 32B (modello locale, nessun dato inviato al cloud).",
        "en": "Synthetic analysis by Qwen 32B (local model, no data sent to cloud).",
        "id": "Analisis sintetis oleh Qwen 32B (model lokal, tidak ada data dikirim ke cloud).",
    },
    "generate_ai_report": {
        "it": "🧠 Genera Report AI",
        "en": "🧠 Generate AI Report",
        "id": "🧠 Buat Laporan AI",
    },
    "qwen_processing": {
        "it": "Qwen 32B sta elaborando...",
        "en": "Qwen 32B is processing...",
        "id": "Qwen 32B sedang memproses...",
    },
    "ollama_unreachable": {
        "it": "Ollama non raggiungibile. Assicurati che sia avviato con: `ollama serve`",
        "en": "Ollama unreachable. Make sure it's running with: `ollama serve`",
        "id": "Ollama tidak dapat dijangkau. Pastikan sudah dijalankan: `ollama serve`",
    },
    "ai_error": {
        "it": "Errore AI: {err}",
        "en": "AI error: {err}",
        "id": "Error AI: {err}",
    },
    "unavailable": {
        "it": "Non disponibile",
        "en": "Unavailable",
        "id": "Tidak tersedia",
    },
    "none_detected": {
        "it": "Nessuno",
        "en": "None",
        "id": "Tidak ada",
    },

    # ── Export / Save ──────────────────────────────────────────────────
    "export_csv": {
        "it": "📥 Esporta dati CSV",
        "en": "📥 Export CSV data",
        "id": "📥 Ekspor data CSV",
    },
    "export_pdf": {
        "it": "📄 Esporta PDF",
        "en": "📄 Export PDF",
        "id": "📄 Ekspor PDF",
    },
    "pdf_error": {
        "it": "PDF non generato: {err}",
        "en": "PDF not generated: {err}",
        "id": "PDF tidak dibuat: {err}",
    },
    "save_land": {
        "it": "💾 Salva Terreno",
        "en": "💾 Save Land",
        "id": "💾 Simpan Lahan",
    },
    "note_optional": {
        "it": "Nota (opzionale)",
        "en": "Note (optional)",
        "id": "Catatan (opsional)",
    },
    "save_to_archive": {
        "it": "💾 Salva in archivio condiviso",
        "en": "💾 Save to shared archive",
        "id": "💾 Simpan ke arsip bersama",
    },
    "land_saved": {
        "it": "✅ Terreno salvato nell'archivio condiviso.",
        "en": "✅ Land saved to shared archive.",
        "id": "✅ Lahan disimpan ke arsip bersama.",
    },
    "save_error": {
        "it": "Errore salvataggio: {err}",
        "en": "Save error: {err}",
        "id": "Error penyimpanan: {err}",
    },
    "pg_unreachable": {
        "it": "PostgreSQL non raggiungibile. Avvia: `fly proxy 15432:5432 -a nuzantara-rag`",
        "en": "PostgreSQL unreachable. Start: `fly proxy 15432:5432 -a nuzantara-rag`",
        "id": "PostgreSQL tidak dapat dijangkau. Jalankan: `fly proxy 15432:5432 -a nuzantara-rag`",
    },
    "db_unavailable": {
        "it": "Database non disponibile — fly proxy non attivo.",
        "en": "Database unavailable — fly proxy not active.",
        "id": "Database tidak tersedia — fly proxy tidak aktif.",
    },

    # ── BATARA fallback (Tabanan/OSM) ──────────────────────────────────
    "batara_timeout": {
        "it": "BATARA non risponde. Riprova tra qualche secondo.",
        "en": "BATARA not responding. Try again in a few seconds.",
        "id": "BATARA tidak merespons. Coba lagi beberapa detik.",
    },
    "batara_fallback_osm": {
        "it": "⚠️ BATARA non disponibile ({err_type}). Provo lookup locale OSM…",
        "en": "⚠️ BATARA unavailable ({err_type}). Trying local OSM lookup…",
        "id": "⚠️ BATARA tidak tersedia ({err_type}). Mencoba pencarian OSM lokal…",
    },
    "batara_fallback_gistaru": {
        "it": "⚠️ BATARA non disponibile ({err_type}). Provo GISTARU RDTR (ATR/BPN nazionale)…",
        "en": "⚠️ BATARA unavailable ({err_type}). Trying GISTARU RDTR (national ATR/BPN)…",
        "id": "⚠️ BATARA tidak tersedia ({err_type}). Mencoba GISTARU RDTR (ATR/BPN nasional)…",
    },
    "gistaru_no_kdb": {
        "it": "ℹ️ Dati da GISTARU RDTR (ATR/BPN). Parametri urbanistici (KDB/KLB/KDH) non disponibili in questo dataset — solo BATARA (Badung) li fornisce. Per il certificato ufficiale: consulta DPUPR del kabupaten.",
        "en": "ℹ️ Data from GISTARU RDTR (ATR/BPN). Urban intensity parameters (KDB/KLB/KDH) not available in this dataset — only BATARA (Badung) provides them. For the official certificate: consult the kabupaten DPUPR.",
        "id": "ℹ️ Data dari GISTARU RDTR (ATR/BPN). Parameter intensitas (KDB/KLB/KDH) tidak tersedia di dataset ini — hanya BATARA (Badung) yang menyediakannya. Untuk sertifikat resmi: konsultasi DPUPR kabupaten.",
    },
    "overlay_constraints": {
        "it": "⚠️ Vincoli Overlay (Ketentuan Khusus)",
        "en": "⚠️ Overlay Constraints (Special Provisions)",
        "id": "⚠️ Ketentuan Khusus (Overlay)",
    },
    "tabanan_no_rdtr": {
        "it": "ℹ️ Coordinate fuori dalla copertura RDTR nota. Dati OSM mostrati come fallback. Consulta DPUPR per il certificato RDTR ufficiale.",
        "en": "ℹ️ Coordinates outside known RDTR coverage. OSM data shown as fallback. Consult DPUPR for the official RDTR certificate.",
        "id": "ℹ️ Koordinat di luar cakupan RDTR yang diketahui. Data OSM ditampilkan sebagai fallback. Konsultasi DPUPR untuk sertifikat RDTR resmi.",
    },
    "area_context": {
        "it": "📍 Contesto area",
        "en": "📍 Area context",
        "id": "📍 Konteks area",
    },
    "bpn_catasto_gistaru": {
        "it": "🏛️ Catasto BPN (GISTARU)",
        "en": "🏛️ BPN Land Registry (GISTARU)",
        "id": "🏛️ Bidang Tanah BPN (GISTARU)",
    },
    "osm_extra_tags": {
        "it": "Tags OSM aggiuntivi",
        "en": "Additional OSM tags",
        "id": "Tag OSM tambahan",
    },
    "no_zone_found": {
        "it": "Nessuna zona trovata. Coordinate fuori dalla coverage (BATARA + GISTARU RDTR + OSM). Verifica lat/lon.",
        "en": "No zone found. Coordinates outside coverage (BATARA + GISTARU RDTR + OSM). Check lat/lon.",
        "id": "Zona tidak ditemukan. Koordinat di luar cakupan (BATARA + GISTARU RDTR + OSM). Periksa lat/lon.",
    },
    "no_bpn_parcel_short": {
        "it": "Nessuna parcella BPN trovata in questo punto.",
        "en": "No BPN parcel found at this point.",
        "id": "Tidak ada bidang tanah BPN di titik ini.",
    },

    # ── Opportunity Finder ─────────────────────────────────────────────
    "opp_finder_title": {
        "it": "🧭 Opportunity Finder",
        "en": "🧭 Opportunity Finder",
        "id": "🧭 Pencari Peluang",
    },
    "opp_finder_caption": {
        "it": "Identifica gli asset con il miglior profilo rischio/rendimento per il budget disponibile.",
        "en": "Identify assets with the best risk/return profile for the available budget.",
        "id": "Identifikasi aset dengan profil risiko/pengembalian terbaik untuk anggaran yang tersedia.",
    },
    "total_budget_usd": {
        "it": "Budget Totale (USD)",
        "en": "Total Budget (USD)",
        "id": "Total Anggaran (USD)",
    },
    "target_roi_min": {
        "it": "Target ROI Minimo (%)",
        "en": "Minimum Target ROI (%)",
        "id": "Target ROI Minimum (%)",
    },
    "start_scan": {
        "it": "🔍 Avvia Scansione",
        "en": "🔍 Start Scan",
        "id": "🔍 Mulai Pemindaian",
    },
    "scanning_db": {
        "it": "Scansione database in corso...",
        "en": "Scanning database...",
        "id": "Memindai database...",
    },
    "assets_found": {
        "it": "Identificati {found} asset compatibili. Visualizzati Top {top}.",
        "en": "Found {found} compatible assets. Showing Top {top}.",
        "id": "Ditemukan {found} aset yang kompatibel. Menampilkan Top {top}.",
    },
    "zones_to_exclude": {
        "it": "⚠️ Zone da escludere con questo budget",
        "en": "⚠️ Zones to exclude with this budget",
        "id": "⚠️ Zona yang dikecualikan dengan anggaran ini",
    },
    "no_targets_found": {
        "it": "Nessun target trovato. Aumenta il budget o abbassa il target ROI.",
        "en": "No targets found. Increase budget or lower target ROI.",
        "id": "Tidak ada target ditemukan. Naikkan anggaran atau turunkan target ROI.",
    },
    "api_error": {
        "it": "Errore connessione API: {err}",
        "en": "API connection error: {err}",
        "id": "Error koneksi API: {err}",
    },

    # ── Deep Financial Analysis ────────────────────────────────────────
    "deep_analysis_title": {
        "it": "🧮 Deep Financial Analysis",
        "en": "🧮 Deep Financial Analysis",
        "id": "🧮 Analisis Finansial Mendalam",
    },
    "deep_analysis_caption": {
        "it": "Sensitivity matrix 3×3: costo costruzione vs rendimento da affitto.",
        "en": "3×3 sensitivity matrix: construction cost vs rental yield.",
        "id": "Sensitivity matrix 3×3: biaya konstruksi vs yield sewa.",
    },
    "urban_zone": {
        "it": "Zona Urbanistica",
        "en": "Urban Zone",
        "id": "Zona Tata Ruang",
    },
    "total_land_price": {
        "it": "Prezzo Totale Terreno (IDR)",
        "en": "Total Land Price (IDR)",
        "id": "Harga Total Tanah (IDR)",
    },
    "generate_matrix": {
        "it": "Genera Sensitivity Matrix",
        "en": "Generate Sensitivity Matrix",
        "id": "Buat Sensitivity Matrix",
    },
    "calculating": {
        "it": "Calcolo in corso...",
        "en": "Calculating...",
        "id": "Menghitung...",
    },
    "urban_params_table": {
        "it": "Parametri Urbanistici",
        "en": "Urban Parameters",
        "id": "Parameter Tata Ruang",
    },
    "optimal_strategy": {
        "it": "Strategia Ottimale",
        "en": "Optimal Strategy",
        "id": "Strategi Optimal",
    },
    "max_roi": {
        "it": "ROI Massimo Attingibile",
        "en": "Maximum Achievable ROI",
        "id": "ROI Maksimum yang Dapat Dicapai",
    },
    "fx_history_12m": {
        "it": "📈 Storico IDR/USD — 12 mesi",
        "en": "📈 IDR/USD History — 12 months",
        "id": "📈 Riwayat IDR/USD — 12 bulan",
    },
    "fx_variation": {
        "it": "Variazione 12m: {delta}%  |  Attuale: {current} IDR/USD",
        "en": "12m variation: {delta}%  |  Current: {current} IDR/USD",
        "id": "Variasi 12b: {delta}%  |  Saat ini: {current} IDR/USD",
    },
    "history_unavailable": {
        "it": "Storico non disponibile.",
        "en": "History unavailable.",
        "id": "Riwayat tidak tersedia.",
    },
    "calc_error": {
        "it": "Errore calcolo: {err}",
        "en": "Calculation error: {err}",
        "id": "Error perhitungan: {err}",
    },

    # ── Geo-Compare ────────────────────────────────────────────────────
    "geo_compare_title": {
        "it": "🛰️ Analisi Comparativa Geospaziale",
        "en": "🛰️ Geospatial Comparative Analysis",
        "id": "🛰️ Analisis Komparatif Geospasial",
    },
    "geo_compare_caption": {
        "it": "Confronto quantitativo tra due asset su mappa satellitare ad alta definizione.",
        "en": "Quantitative comparison of two assets on high-definition satellite map.",
        "id": "Perbandingan kuantitatif dua aset pada peta satelit definisi tinggi.",
    },
    "asset_params": {
        "it": "Parametri Asset",
        "en": "Asset Parameters",
        "id": "Parameter Aset",
    },
    "gps_coordinates": {
        "it": "Coordinate GPS",
        "en": "GPS Coordinates",
        "id": "Koordinat GPS",
    },
    "calculate_delta": {
        "it": "CALCOLA DELTA",
        "en": "CALCULATE DELTA",
        "id": "HITUNG DELTA",
    },
    "satellite_view": {
        "it": "Vista Satellitare + Zone RDTR",
        "en": "Satellite View + RDTR Zones",
        "id": "Tampilan Satelit + Zona RDTR",
    },
    "load_rdtr_for": {
        "it": "Carica zone RDTR per:",
        "en": "Load RDTR zones for:",
        "id": "Muat zona RDTR untuk:",
    },
    "all_badung_slow": {
        "it": "Tutta Badung (lento)",
        "en": "All Badung (slow)",
        "id": "Seluruh Badung (lambat)",
    },
    "differential_analysis": {
        "it": "Analisi differenziale in corso...",
        "en": "Differential analysis in progress...",
        "id": "Analisis diferensial sedang berlangsung...",
    },
    "technical_tie": {
        "it": "Pareggio Tecnico",
        "en": "Technical Tie",
        "id": "Seri Teknis",
    },
    "asset_a_dominant": {
        "it": "Asset A Dominante",
        "en": "Asset A Dominant",
        "id": "Aset A Dominan",
    },
    "asset_b_dominant": {
        "it": "Asset B Dominante",
        "en": "Asset B Dominant",
        "id": "Aset B Dominan",
    },
    "all_scenarios_detail": {
        "it": "📊 Dettaglio tutti gli scenari",
        "en": "📊 All scenarios detail",
        "id": "📊 Detail semua skenario",
    },
    "analysis_error": {
        "it": "Errore analisi: {err}",
        "en": "Analysis error: {err}",
        "id": "Error analisis: {err}",
    },

    # ── Saved Parcels ──────────────────────────────────────────────────
    "saved_parcels_title": {
        "it": "📌 Archivio Terreni",
        "en": "📌 Land Archive",
        "id": "📌 Arsip Lahan",
    },
    "saved_parcels_caption": {
        "it": "Terreni salvati da tutti gli utenti. Spazio condiviso.",
        "en": "Saved lands from all users. Shared space.",
        "id": "Lahan yang disimpan semua pengguna. Ruang bersama.",
    },
    "db_connection_failed": {
        "it": "Connessione DB fallita.",
        "en": "DB connection failed.",
        "id": "Koneksi DB gagal.",
    },
    "db_read_error": {
        "it": "Errore lettura DB: {err}",
        "en": "DB read error: {err}",
        "id": "Error baca DB: {err}",
    },
    "no_saved_lands": {
        "it": "Nessun terreno salvato ancora.",
        "en": "No saved lands yet.",
        "id": "Belum ada lahan yang disimpan.",
    },
    "filter_by_zone": {
        "it": "Filtra per zona",
        "en": "Filter by zone",
        "id": "Filter berdasarkan zona",
    },
    "all_zones": {
        "it": "Tutte",
        "en": "All",
        "id": "Semua",
    },
    "lands_found": {
        "it": "{n} terreni trovati",
        "en": "{n} lands found",
        "id": "{n} lahan ditemukan",
    },
    "surface": {
        "it": "Superficie",
        "en": "Area",
        "id": "Luas",
    },
    "price": {
        "it": "Prezzo",
        "en": "Price",
        "id": "Harga",
    },
    "edit_note": {
        "it": "Modifica nota",
        "en": "Edit note",
        "id": "Edit catatan",
    },
    "update_note": {
        "it": "💾 Aggiorna nota",
        "en": "💾 Update note",
        "id": "💾 Perbarui catatan",
    },
    "note_updated": {
        "it": "Nota aggiornata.",
        "en": "Note updated.",
        "id": "Catatan diperbarui.",
    },
    "delete": {
        "it": "🗑️ Elimina",
        "en": "🗑️ Delete",
        "id": "🗑️ Hapus",
    },
    "land_deleted": {
        "it": "Terreno eliminato.",
        "en": "Land deleted.",
        "id": "Lahan dihapus.",
    },

    # ── AI Prompt language ─────────────────────────────────────────────
    "ai_prompt_lang": {
        "it": "italiano",
        "en": "English",
        "id": "Bahasa Indonesia",
    },

    # ── PDF sections ───────────────────────────────────────────────────
    "pdf_zone_rdtr": {
        "it": "Zona RDTR",
        "en": "RDTR Zone",
        "id": "Zona RDTR",
    },
    "pdf_zone_code": {
        "it": "Codice zona",
        "en": "Zone code",
        "id": "Kode zona",
    },
    "pdf_zone_name": {
        "it": "Nome zona",
        "en": "Zone name",
        "id": "Nama zona",
    },
    "pdf_urban_params": {
        "it": "Parametri Urbanistici",
        "en": "Urban Parameters",
        "id": "Parameter Tata Ruang",
    },
    "pdf_max_height": {
        "it": "Altezza max",
        "en": "Max height",
        "id": "Tinggi maks",
    },
    "pdf_financial": {
        "it": "Analisi Finanziaria",
        "en": "Financial Analysis",
        "id": "Analisis Finansial",
    },
    "pdf_area": {
        "it": "Superficie",
        "en": "Area",
        "id": "Luas",
    },
    "pdf_price_idr": {
        "it": "Prezzo IDR",
        "en": "Price IDR",
        "id": "Harga IDR",
    },
    "pdf_price_usd": {
        "it": "Prezzo USD",
        "en": "Price USD",
        "id": "Harga USD",
    },
    "pdf_optimal_roi": {
        "it": "ROI ottimale",
        "en": "Optimal ROI",
        "id": "ROI optimal",
    },
    "pdf_break_even": {
        "it": "Break-even",
        "en": "Break-even",
        "id": "Break-even",
    },
    "pdf_strategy": {
        "it": "Strategia",
        "en": "Strategy",
        "id": "Strategi",
    },
    "pdf_catasto": {
        "it": "Catasto BPN",
        "en": "BPN Land Registry",
        "id": "Bidang Tanah BPN",
    },
    "pdf_land_right": {
        "it": "Tipo diritto",
        "en": "Land right type",
        "id": "Jenis hak",
    },
    "pdf_cert_number": {
        "it": "Nomor sertifikat",
        "en": "Certificate number",
        "id": "Nomor sertifikat",
    },
    "pdf_year": {
        "it": "Anno",
        "en": "Year",
        "id": "Tahun",
    },
    "pdf_urban_context": {
        "it": "Contesto Urbano",
        "en": "Urban Context",
        "id": "Konteks Perkotaan",
    },
    "pdf_noise": {
        "it": "Livello rumore",
        "en": "Noise level",
        "id": "Tingkat kebisingan",
    },
    "pdf_elevation": {
        "it": "Elevazione slm",
        "en": "Elevation ASL",
        "id": "Elevasi dpl",
    },
    "pdf_coast_dist": {
        "it": "Distanza costa",
        "en": "Coast distance",
        "id": "Jarak pantai",
    },
    "pdf_tourism": {
        "it": "Mercato Turistico (OSM)",
        "en": "Tourism Market (OSM)",
        "id": "Pasar Wisata (OSM)",
    },
    "pdf_within_500m": {
        "it": "Strutture entro 500m",
        "en": "Structures within 500m",
        "id": "Fasilitas dalam 500m",
    },
    "pdf_within_1km": {
        "it": "Strutture entro 1km",
        "en": "Structures within 1km",
        "id": "Fasilitas dalam 1km",
    },
    "pdf_within_2km": {
        "it": "Strutture entro 2km",
        "en": "Structures within 2km",
        "id": "Fasilitas dalam 2km",
    },
    "pdf_overlay": {
        "it": "Vincoli Overlay",
        "en": "Overlay Constraints",
        "id": "Kendala Overlay",
    },
}


def set_language(lang: str) -> None:
    """Set the active language. Must be 'it', 'en', or 'id'."""
    global _current_lang
    if lang in ("it", "en", "id"):
        _current_lang = lang


def get_language() -> str:
    """Get the current active language code."""
    return _current_lang


def T(key: str, **kwargs: object) -> str:
    """Translate a key to the current language. Supports {placeholder} formatting."""
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key  # fallback: return the key itself
    text = entry.get(_current_lang, entry.get("it", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
