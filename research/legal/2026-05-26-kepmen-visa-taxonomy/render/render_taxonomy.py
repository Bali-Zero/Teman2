"""Kepmen visa taxonomy A4 brand render — EN + ID HTML + PDF via Playwright.

Riusa palette + base CSS dal C5A dossier 2026-05-26. Compact tabular surface.
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

OUT_DIR = Path(__file__).parent
MATRIX_PATH = Path("/tmp/kepmen-matrix-final.json")

PALETTE = {
    "ivory_bg": "#FAF7F0",
    "deep_teal": "#0F4C5C",
    "navy_accent": "#13293D",
    "muted_grey": "#6B6F76",
    "border": "#D6D3C9",
    "subtle_bg": "#F0EBE0",
    "rule_red": "#7F1F2A",
    "verified_green": "#2E5F3F",
    "alt_row": "#F5F0E5",
}

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

@page {{
    size: A4;
    margin: 18mm 14mm 20mm 14mm;
    @bottom-left {{
        content: "Bali Zero — Kepmen Visa Taxonomy 2025 — Internal Reference";
        font-family: 'Inter', sans-serif;
        font-size: 7.5pt;
        color: {PALETTE['muted_grey']};
    }}
    @bottom-right {{
        content: counter(page) " / " counter(pages);
        font-family: 'Inter', sans-serif;
        font-size: 7.5pt;
        color: {PALETTE['muted_grey']};
    }}
}}

* {{ box-sizing: border-box; }}

body {{
    font-family: 'Crimson Pro', Georgia, serif;
    font-size: 9pt;
    line-height: 1.4;
    color: {PALETTE['navy_accent']};
    background: {PALETTE['ivory_bg']};
    margin: 0;
    padding: 0;
    -webkit-font-smoothing: antialiased;
}}

.cover {{
    page-break-after: always;
    padding: 55mm 0 0;
    text-align: center;
}}

.cover .logo {{
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 22pt;
    color: {PALETTE['deep_teal']};
    letter-spacing: 0.06em;
    margin-bottom: 4mm;
}}

.cover .tagline {{
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 8.5pt;
    color: {PALETTE['muted_grey']};
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 28mm;
}}

.cover .title {{
    font-size: 24pt;
    font-weight: 600;
    color: {PALETTE['navy_accent']};
    margin: 0 12mm 8mm;
    line-height: 1.2;
}}

.cover .subtitle {{
    font-style: italic;
    font-size: 11pt;
    color: {PALETTE['deep_teal']};
    margin: 0 16mm 20mm;
}}

.cover .meta {{
    font-family: 'Inter', sans-serif;
    font-size: 8.5pt;
    color: {PALETTE['muted_grey']};
    margin-top: 50mm;
    line-height: 1.7;
}}

.cover .confidential {{
    display: inline-block;
    border: 1.2px solid {PALETTE['rule_red']};
    color: {PALETTE['rule_red']};
    font-family: 'Inter', sans-serif;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    padding: 3mm 7mm;
    margin-top: 8mm;
}}

h1 {{
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 16pt;
    color: {PALETTE['deep_teal']};
    border-bottom: 1.5px solid {PALETTE['deep_teal']};
    padding-bottom: 2mm;
    margin: 8mm 0 5mm;
    page-break-after: avoid;
}}

h2 {{
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 12pt;
    color: {PALETTE['navy_accent']};
    margin: 6mm 0 3mm;
    page-break-after: avoid;
}}

h3 {{
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 10pt;
    color: {PALETTE['deep_teal']};
    margin: 4mm 0 2mm;
    page-break-after: avoid;
}}

p {{ margin: 2mm 0; }}

table {{
    width: 100%;
    border-collapse: collapse;
    margin: 3mm 0;
    font-size: 7.5pt;
    font-family: 'Inter', sans-serif;
    page-break-inside: auto;
}}

table.master {{
    font-size: 7pt;
}}

thead {{
    display: table-header-group;
}}

th {{
    background: {PALETTE['deep_teal']};
    color: {PALETTE['ivory_bg']};
    font-weight: 600;
    text-align: left;
    padding: 2mm 2mm;
    border-bottom: 1.5px solid {PALETTE['navy_accent']};
    font-family: 'Inter', sans-serif;
    font-size: 7.5pt;
}}

td {{
    padding: 1.5mm 2mm;
    border-bottom: 0.4px solid {PALETTE['border']};
    vertical-align: top;
    font-family: 'Inter', sans-serif;
    font-size: 7.5pt;
}}

tr:nth-child(even) td {{
    background: {PALETTE['alt_row']};
}}

td.code {{
    font-family: 'Inter', monospace;
    font-weight: 700;
    color: {PALETTE['deep_teal']};
    white-space: nowrap;
}}

.callout {{
    background: {PALETTE['subtle_bg']};
    border-left: 3px solid {PALETTE['deep_teal']};
    padding: 3mm 4mm;
    margin: 3mm 0;
    font-size: 8.5pt;
    page-break-inside: avoid;
}}

.toc {{
    page-break-after: always;
    padding: 12mm 0;
}}

.toc ol {{
    font-family: 'Inter', sans-serif;
    font-size: 10pt;
    line-height: 1.9;
    padding-left: 6mm;
}}

.toc a {{
    color: {PALETTE['navy_accent']};
    text-decoration: none;
}}

.toc .toc-dots {{
    color: {PALETTE['muted_grey']};
}}

.section-page {{ page-break-before: always; }}

.summary-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4mm;
    margin: 4mm 0;
}}

.summary-card {{
    background: {PALETTE['subtle_bg']};
    border-left: 2px solid {PALETTE['deep_teal']};
    padding: 3mm 4mm;
    font-size: 8.5pt;
}}

.summary-card .metric {{
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 14pt;
    color: {PALETTE['deep_teal']};
    margin: 0 0 1mm;
}}

.summary-card .label {{
    font-family: 'Inter', sans-serif;
    font-size: 8pt;
    color: {PALETTE['muted_grey']};
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}

.footer-note {{
    font-size: 7.5pt;
    color: {PALETTE['muted_grey']};
    font-style: italic;
    margin-top: 4mm;
}}

.verbatim {{
    font-family: 'Crimson Pro', serif;
    font-style: italic;
    font-size: 8.5pt;
    color: {PALETTE['navy_accent']};
    background: {PALETTE['ivory_bg']};
    border: 0.5px solid {PALETTE['border']};
    padding: 2mm 3mm;
    margin: 2mm 0;
}}
"""

# ------------------------------------------------------------
# Content builders
# ------------------------------------------------------------

PNBP_BY_PREFIX = {
    'A': {'visa_idr': 0, 'note': 'Bebas (visa-free, 86+ nationalities)'},
    'B': {'visa_idr': 500000, 'note': 'VOA 30 days, +30 extension once'},
    'F': {'visa_idr': 250000, 'note': 'VOA 7 days, non-extendable'},
    'C': {'visa_idr': 1000000, 'note': 'Single-entry 60 days, +60+60 extension typical'},
    'D': {'visa_idr': 3000000, 'note': 'Multi-entry 1 year baseline'},
    'E': {'visa_idr': 500000, 'note': 'KITAS Visa (Rp 500K) + ITAS permit separately (Rp 3-7M)'},
}


def cover_html_en():
    return """
<div class="cover">
    <div class="logo">BALI ZERO</div>
    <div class="tagline">From Zero to Infinity ∞</div>
    <div class="title">Indonesia Visa Classification 2025</div>
    <div class="subtitle">Complete Reference — Kepmen M.IP-08.GR.01.01/2025</div>
    <div class="meta">
        110 indeks visa · 80-page Kepmen · Effective 01 June 2025<br>
        Cross-referenced with PP 45/2024 (PNBP tariffs)<br>
        Mapped to Bali Zero Service Portfolio 1-7<br>
        <br>
        Compiled 26 May 2026<br>
        Authority: Direktorat Jenderal Imigrasi
    </div>
    <div class="confidential">Confidential — Internal Use Only</div>
</div>
"""


def cover_html_id():
    return """
<div class="cover">
    <div class="logo">BALI ZERO</div>
    <div class="tagline">Dari Nol ke Infinity ∞</div>
    <div class="title">Klasifikasi Visa Indonesia 2025</div>
    <div class="subtitle">Referensi Lengkap — Kepmen M.IP-08.GR.01.01/2025</div>
    <div class="meta">
        110 indeks visa · Kepmen 80 halaman · Berlaku 01 Juni 2025<br>
        Cross-referenced dengan PP 45/2024 (Tarif PNBP)<br>
        Dipetakan ke Portfolio Layanan Bali Zero 1-7<br>
        <br>
        Disusun 26 Mei 2026<br>
        Otoritas: Direktorat Jenderal Imigrasi
    </div>
    <div class="confidential">Rahasia — Untuk Penggunaan Internal</div>
</div>
"""


def toc_html(lang='en'):
    if lang == 'en':
        items = [
            "Executive Summary",
            "PNBP Tariff Schedule (PP 45/2024 verbatim)",
            "Master Matrix — All 110 Indeks (Prefix A-F)",
            "Visa Kunjungan (Prefix A · B · C · D · F)",
            "Visa Tinggal Terbatas (Prefix E)",
            "Bali Zero Service Mapping",
            "Open Questions Summary",
        ]
        title = "Table of Contents"
    else:
        items = [
            "Ringkasan Eksekutif",
            "Jadwal Tarif PNBP (PP 45/2024 verbatim)",
            "Matriks Master — Semua 110 Indeks (Prefix A-F)",
            "Visa Kunjungan (Prefix A · B · C · D · F)",
            "Visa Tinggal Terbatas (Prefix E)",
            "Pemetaan Layanan Bali Zero",
            "Ringkasan Pertanyaan Terbuka",
        ]
        title = "Daftar Isi"

    rows = ''.join(f'<li><a href="#sec{i}">{x}</a></li>' for i, x in enumerate(items, 1))
    return f'<div class="toc"><h1>{title}</h1><ol>{rows}</ol></div>'


def summary_html(lang='en'):
    if lang == 'en':
        title = "Executive Summary"
        intro = """The Keputusan Menteri Imigrasi dan Pemasyarakatan No. M.IP-08.GR.01.01 Tahun 2025
        (effective 01 June 2025) reorganized Indonesia's visa taxonomy into 110 distinct indeks across
        two top-level Lampiran sections: <b>A. Visa Kunjungan</b> (visit visas, prefix A/B/C/D/F) and
        <b>B. Visa Tinggal Terbatas</b> (limited stay, prefix E). The 2023 Kepmen
        (M.HH-02.GR.01.04/2023) was revoked."""
        cards = [
            ('110', 'Total Indeks'),
            ('2', 'Top-level Lampiran sections'),
            ('80', 'PDF pages in Kepmen'),
            ('7', 'Bali Zero Services mapped'),
        ]
        breakdown_title = "Prefix Breakdown"
        breakdown_rows = [
            ('A', 4, 'Bebas Visa Kunjungan (visa-free 30 days)'),
            ('B', 2, 'Visa Kunjungan Saat Kedatangan 30 Hari (VOA 30d)'),
            ('F', 2, 'Visa Kunjungan Saat Kedatangan 7 Hari (VOA 7d)'),
            ('C', 34, 'Visa Kunjungan 1× Perjalanan (single-entry 60d)'),
            ('D', 9, 'Visa Kunjungan Beberapa Kali Perjalanan (multi-entry)'),
            ('E', 59, 'Visa Tinggal Terbatas (KITAS-class)'),
        ]
        breakdown_headers = ['Prefix', 'Count', 'Description']
    else:
        title = "Ringkasan Eksekutif"
        intro = """Keputusan Menteri Imigrasi dan Pemasyarakatan Nomor M.IP-08.GR.01.01 Tahun 2025
        (berlaku 01 Juni 2025) mereorganisasi taksonomi visa Indonesia menjadi 110 indeks distinct
        dalam dua bagian Lampiran utama: <b>A. Visa Kunjungan</b> (visa kunjungan, prefix A/B/C/D/F)
        dan <b>B. Visa Tinggal Terbatas</b> (tinggal terbatas, prefix E). Kepmen 2023
        (M.HH-02.GR.01.04/2023) dicabut."""
        cards = [
            ('110', 'Total Indeks'),
            ('2', 'Bagian Lampiran utama'),
            ('80', 'Halaman PDF Kepmen'),
            ('7', 'Layanan Bali Zero terpetakan'),
        ]
        breakdown_title = "Rincian per Prefix"
        breakdown_rows = [
            ('A', 4, 'Bebas Visa Kunjungan (bebas visa 30 hari)'),
            ('B', 2, 'Visa Kunjungan Saat Kedatangan 30 Hari (VOA 30h)'),
            ('F', 2, 'Visa Kunjungan Saat Kedatangan 7 Hari (VOA 7h)'),
            ('C', 34, 'Visa Kunjungan 1× Perjalanan (sekali masuk 60h)'),
            ('D', 9, 'Visa Kunjungan Beberapa Kali Perjalanan (multi-entry)'),
            ('E', 59, 'Visa Tinggal Terbatas (kelas KITAS)'),
        ]
        breakdown_headers = ['Prefix', 'Jumlah', 'Deskripsi']

    card_html = ''.join(f'<div class="summary-card"><div class="metric">{m}</div><div class="label">{l}</div></div>' for m, l in cards)
    table_rows = ''.join(f'<tr><td class="code">{p}</td><td>{c}</td><td>{d}</td></tr>' for p, c, d in breakdown_rows)

    return f"""
<div class="section-page">
<h1 id="sec1">{title}</h1>
<p>{intro}</p>
<div class="summary-grid">{card_html}</div>
<h3>{breakdown_title}</h3>
<table>
<thead><tr>{''.join(f'<th>{h}</th>' for h in breakdown_headers)}</tr></thead>
<tbody>{table_rows}</tbody>
</table>
</div>
"""


def pnbp_html(lang='en'):
    if lang == 'en':
        title = "PNBP Tariff Schedule (PP 45/2024 verbatim)"
        intro = """The following tariff lines are extracted verbatim from PP 45/2024 Lampiran B (VISA)
        and Lampiran B (IZIN KEIMIGRASIAN). The Kepmen 2025 indeks codes are NOT directly mapped
        to PP 45/2024 tariff lines — alignment is by duration + category."""
        sections = [
            ('Single-entry Visit Visa (Visa Kunjungan)', [
                ('7 days', 'per orang', 'Rp 250.000', '~$15'),
                ('14 days', 'per orang', 'Rp 350.000', '~$22'),
                ('30 days (VOA)', 'per orang', 'Rp 500.000', '~$31'),
                ('60 days (most C-series)', 'per orang', 'Rp 1.000.000', '~$62'),
                ('90 days', 'per orang', 'Rp 1.500.000', '~$93'),
                ('180 days', 'per orang', 'Rp 2.000.000', '~$124'),
            ]),
            ('Multi-entry Visit Visa (D-series)', [
                ('60 days', 'per orang', 'Rp 1.500.000', '~$93'),
                ('90 days', 'per orang', 'Rp 2.000.000', '~$124'),
                ('180 days', 'per orang', 'Rp 2.500.000', '~$155'),
                ('1 year', 'per orang', 'Rp 3.000.000', '~$186'),
                ('2 years', 'per orang', 'Rp 5.000.000', '~$310'),
                ('5 years', 'per orang', 'Rp 10.000.000', '~$620'),
                ('10 years', 'per orang', 'Rp 15.000.000', '~$930'),
            ]),
            ('KITAS Visa Tinggal Terbatas (E-series, base)', [
                ('Any duration', 'per permohonan', 'Rp 500.000', '~$31'),
            ]),
            ('KITAS ITAS Permit Fee (separate from visa)', [
                ('60 days', 'per permohonan', 'Rp 1.000.000', '~$62'),
                ('90 days', 'per permohonan', 'Rp 1.500.000', '~$93'),
                ('6 months', 'per permohonan', 'Rp 2.000.000', '~$124'),
                ('1 year', 'per permohonan', 'Rp 3.000.000', '~$186'),
                ('2 years', 'per permohonan', 'Rp 5.000.000', '~$310'),
                ('5 years', 'per permohonan', 'Rp 7.000.000', '~$434'),
            ]),
            ('Verification Surcharge (Biaya Verifikasi Visa untuk Tujuan Tertentu)', [
                ('Kategori I', 'per permohonan', 'Rp 1.000.000', '~$62'),
                ('Kategori II', 'per permohonan', 'Rp 2.000.000', '~$124'),
                ('Kategori III', 'per permohonan', 'Rp 8.000.000', '~$496'),
            ]),
        ]
        headers = ['Tariff Line', 'Unit', 'Amount (IDR)', 'USD est.']
    else:
        title = "Jadwal Tarif PNBP (PP 45/2024 verbatim)"
        intro = """Berikut adalah tarif PNBP verbatim dari PP 45/2024 Lampiran B (VISA) dan
        Lampiran B (IZIN KEIMIGRASIAN). Kode indeks Kepmen 2025 TIDAK dipetakan langsung ke
        baris tarif PP 45/2024 — penyelarasan berdasarkan durasi + kategori."""
        sections = [
            ('Visa Kunjungan Sekali Masuk (Single-entry)', [
                ('7 hari', 'per orang', 'Rp 250.000', '~$15'),
                ('14 hari', 'per orang', 'Rp 350.000', '~$22'),
                ('30 hari (VOA)', 'per orang', 'Rp 500.000', '~$31'),
                ('60 hari (sebagian besar seri C)', 'per orang', 'Rp 1.000.000', '~$62'),
                ('90 hari', 'per orang', 'Rp 1.500.000', '~$93'),
                ('180 hari', 'per orang', 'Rp 2.000.000', '~$124'),
            ]),
            ('Visa Kunjungan Beberapa Kali Perjalanan (Seri D)', [
                ('60 hari', 'per orang', 'Rp 1.500.000', '~$93'),
                ('90 hari', 'per orang', 'Rp 2.000.000', '~$124'),
                ('180 hari', 'per orang', 'Rp 2.500.000', '~$155'),
                ('1 tahun', 'per orang', 'Rp 3.000.000', '~$186'),
                ('2 tahun', 'per orang', 'Rp 5.000.000', '~$310'),
                ('5 tahun', 'per orang', 'Rp 10.000.000', '~$620'),
                ('10 tahun', 'per orang', 'Rp 15.000.000', '~$930'),
            ]),
            ('Visa Tinggal Terbatas KITAS (Seri E, base)', [
                ('Durasi apapun', 'per permohonan', 'Rp 500.000', '~$31'),
            ]),
            ('Biaya Izin Tinggal Terbatas (terpisah dari visa)', [
                ('60 hari', 'per permohonan', 'Rp 1.000.000', '~$62'),
                ('90 hari', 'per permohonan', 'Rp 1.500.000', '~$93'),
                ('6 bulan', 'per permohonan', 'Rp 2.000.000', '~$124'),
                ('1 tahun', 'per permohonan', 'Rp 3.000.000', '~$186'),
                ('2 tahun', 'per permohonan', 'Rp 5.000.000', '~$310'),
                ('5 tahun', 'per permohonan', 'Rp 7.000.000', '~$434'),
            ]),
            ('Biaya Verifikasi Visa untuk Tujuan Tertentu', [
                ('Kategori I', 'per permohonan', 'Rp 1.000.000', '~$62'),
                ('Kategori II', 'per permohonan', 'Rp 2.000.000', '~$124'),
                ('Kategori III', 'per permohonan', 'Rp 8.000.000', '~$496'),
            ]),
        ]
        headers = ['Baris Tarif', 'Satuan', 'Jumlah (IDR)', 'Estimasi USD']

    body = f'<div class="section-page"><h1 id="sec2">{title}</h1><p>{intro}</p>'

    for section_title, rows in sections:
        body += f'<h3>{section_title}</h3>'
        body += '<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>'
        for row in rows:
            body += '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>'
        body += '</tbody></table>'

    body += '</div>'
    return body


def master_matrix_html(matrix, lang='en'):
    if lang == 'en':
        title = "Master Matrix — 110 Indeks"
        intro = "All 110 indeks listed alphabetically by code. Verbatim Bahasa Indonesia descriptions preserved; English assist for operational use only (NOT regulatory)."
        headers = ['Code', 'Section', 'Pg', 'Target (ID verbatim)', 'Uraian Kegiatan (ID verbatim)', 'EN assist']
    else:
        title = "Matriks Master — 110 Indeks"
        intro = "Semua 110 indeks terdaftar urut alfabetik berdasarkan kode. Deskripsi Bahasa Indonesia verbatim dipertahankan; bantuan EN hanya untuk operasional (TIDAK regulator)."
        headers = ['Kode', 'Bagian', 'Hal', 'Sasaran (ID verbatim)', 'Uraian Kegiatan (ID verbatim)', 'EN assist']

    # Sort alphabetically
    def sort_key(e):
        p = e['prefix']
        rest = e['code'][1:]
        # Extract numeric + suffix
        import re
        m = re.match(r'(\d+)([A-Z]?)', rest)
        if m:
            return (p, int(m.group(1)), m.group(2))
        return (p, 0, '')

    sorted_matrix = sorted(matrix, key=sort_key)

    body = f'<div class="section-page"><h1 id="sec3">{title}</h1><p>{intro}</p>'
    body += '<table class="master"><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>'

    for e in sorted_matrix:
        sec = f"{e['section_letter']}.{e['section_num']}" if e['section_num'] != '-' else e['section_letter']
        ta = e['target_audience_clean'][:120].replace('|', '/')
        uk = e['uraian_kegiatan_clean'][:140].replace('|', '/')
        en = e['uraian_kegiatan_en'][:90]
        body += f'<tr><td class="code">{e["code"]}</td><td>{sec}</td><td>{e["first_page"]}</td><td>{ta}</td><td>{uk}</td><td>{en}</td></tr>'

    body += '</tbody></table></div>'
    return body


def bz_services_html(lang='en'):
    if lang == 'en':
        title = "Bali Zero Service Portfolio Mapping"
        intro = "The 110 Kepmen indeks are mapped to 7 Bali Zero service categories. Pricing ranges are indicative; actual quote requires client + duration + sponsor verification."
        services = [
            ('Service 1 — VOA 30 Days', 'B1, B4, F1, F4', '4', 'IDR 0.5-1.5M PNBP + agency'),
            ('Service 2 — Single-Entry 60d Visit Visa', 'All C-series (34)', '34', 'IDR 1-3M PNBP + 3-8M agency'),
            ('Service 3 — Multi-Entry Visit Visa', 'All D-series (9)', '9', 'IDR 3-15M PNBP + 5-15M agency'),
            ('Service 4 — KITAS Worker', 'E23/E25 series (13)', '13', 'IDR 3.5-7M PNBP + 15-35M agency'),
            ('Service 5 — KITAS Investor', 'E28 series (8)', '8', 'IDR 5.5-22M PNBP + 20-60M agency'),
            ('Service 6 — KITAS Family/Retiree', 'E26/E29/E30/E31/E32/E33 (37)', '37', 'IDR 3.5-12M PNBP + 12-30M agency'),
            ('Service 7 — KITAS Digital Nomad', 'E33G only (1)', '1', 'IDR 3.5M PNBP + 25-40M agency (premium)'),
            ('Outside portfolio — Visa-Free', 'A1/A4/A36/A37 (4)', '4', '0 PNBP, consultation only'),
        ]
        headers = ['Service', 'Indeks', 'Count', 'Pricing range']
    else:
        title = "Pemetaan Portfolio Layanan Bali Zero"
        intro = "110 indeks Kepmen dipetakan ke 7 kategori layanan Bali Zero. Rentang harga indikatif; quote sebenarnya memerlukan verifikasi klien + durasi + penjamin."
        services = [
            ('Layanan 1 — VOA 30 Hari', 'B1, B4, F1, F4', '4', 'IDR 0.5-1.5jt PNBP + agen'),
            ('Layanan 2 — Visa Kunjungan Sekali Masuk 60h', 'Semua seri C (34)', '34', 'IDR 1-3jt PNBP + 3-8jt agen'),
            ('Layanan 3 — Visa Kunjungan Multi-Entry', 'Semua seri D (9)', '9', 'IDR 3-15jt PNBP + 5-15jt agen'),
            ('Layanan 4 — KITAS Pekerja', 'Seri E23/E25 (13)', '13', 'IDR 3.5-7jt PNBP + 15-35jt agen'),
            ('Layanan 5 — KITAS Investor', 'Seri E28 (8)', '8', 'IDR 5.5-22jt PNBP + 20-60jt agen'),
            ('Layanan 6 — KITAS Keluarga/Pensiunan', 'Seri E26/E29/E30/E31/E32/E33 (37)', '37', 'IDR 3.5-12jt PNBP + 12-30jt agen'),
            ('Layanan 7 — KITAS Nomad Digital', 'Hanya E33G (1)', '1', 'IDR 3.5jt PNBP + 25-40jt agen (premium)'),
            ('Di luar portfolio — Bebas Visa', 'A1/A4/A36/A37 (4)', '4', '0 PNBP, konsultasi saja'),
        ]
        headers = ['Layanan', 'Indeks', 'Jumlah', 'Rentang Harga']

    body = f'<div class="section-page"><h1 id="sec6">{title}</h1><p>{intro}</p>'
    body += '<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>'
    for row in services:
        body += '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>'
    body += '</tbody></table></div>'
    return body


def oq_html(lang='en'):
    if lang == 'en':
        title = "Open Questions Summary"
        intro = "47 open questions identified across duration, surcharge assignment, ITAS edge cases, and PricingTool gaps. Priority-tagged for resolution."
        rows = [
            ('OQ-001 to OQ-019', 'Duration data (C/B/F series extensions)', '19', '13 partial · 6 open · P0-P2'),
            ('OQ-051 to OQ-059', 'D-series multi-entry duration', '9', '9 open · P0-P1'),
            ('OQ-101 to OQ-112', 'E-series KITAS duration verify', '12', 'partial · P0-P2'),
            ('OQ-115 to OQ-120', 'Surcharge Kategori I/II/III assignment', '6', '6 open · P0-P1'),
            ('OQ-201 to OQ-205', 'ITAS edge cases (10y, KITAP conversion)', '5', '4 open · P1-P2'),
            ('OQ-301 to OQ-305', 'Bali Zero PricingTool gaps', '5', '5 open · P0-P2 (blocked auth)'),
            ('OQ-401 to OQ-403', 'Visa-Free country lists', '3', '2 open · P0-P2'),
            ('OQ-501 to OQ-504', 'No-data cases (Data Belum Tersedia)', '4', '4 no_data · P0-P2'),
        ]
        headers = ['OQ Range', 'Domain', 'Count', 'Status']
    else:
        title = "Ringkasan Pertanyaan Terbuka"
        intro = "47 pertanyaan terbuka teridentifikasi terkait durasi, penugasan surcharge, ITAS edge case, dan gap PricingTool. Diberi tag prioritas untuk resolusi."
        rows = [
            ('OQ-001 s/d OQ-019', 'Data durasi (perpanjangan seri C/B/F)', '19', '13 partial · 6 terbuka · P0-P2'),
            ('OQ-051 s/d OQ-059', 'Durasi multi-entry seri D', '9', '9 terbuka · P0-P1'),
            ('OQ-101 s/d OQ-112', 'Verifikasi durasi KITAS seri E', '12', 'partial · P0-P2'),
            ('OQ-115 s/d OQ-120', 'Penugasan Surcharge Kategori I/II/III', '6', '6 terbuka · P0-P1'),
            ('OQ-201 s/d OQ-205', 'ITAS edge case (10t, konversi KITAP)', '5', '4 terbuka · P1-P2'),
            ('OQ-301 s/d OQ-305', 'Gap PricingTool Bali Zero', '5', '5 terbuka · P0-P2 (auth diblokir)'),
            ('OQ-401 s/d OQ-403', 'Daftar negara Bebas Visa', '3', '2 terbuka · P0-P2'),
            ('OQ-501 s/d OQ-504', 'Kasus no_data (Data Belum Tersedia)', '4', '4 no_data · P0-P2'),
        ]
        headers = ['Rentang OQ', 'Domain', 'Jumlah', 'Status']

    body = f'<div class="section-page"><h1 id="sec7">{title}</h1><p>{intro}</p>'
    body += '<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>'
    for row in rows:
        body += '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>'
    body += '</tbody></table>'

    body += '<div class="footer-note">See <code>04-open-questions.md</code> for full OQ inventory with next-action recommendations.</div></div>'
    return body


def build_html(lang='en'):
    matrix = json.loads(MATRIX_PATH.read_text())
    if lang == 'en':
        title = "Indonesia Visa Classification 2025 — Bali Zero Internal Reference"
    else:
        title = "Klasifikasi Visa Indonesia 2025 — Referensi Internal Bali Zero"

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
{cover_html_en() if lang == 'en' else cover_html_id()}
{toc_html(lang)}
{summary_html(lang)}
{pnbp_html(lang)}
{master_matrix_html(matrix, lang)}
{bz_services_html(lang)}
{oq_html(lang)}
</body>
</html>
"""
    return html


async def html_to_pdf(html_path, pdf_path):
    """Render HTML to PDF via Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{html_path}")
        await page.wait_for_load_state('networkidle')
        await page.pdf(
            path=str(pdf_path),
            format='A4',
            print_background=True,
            margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
        )
        await browser.close()


async def main():
    t0 = time.time()

    # EN
    print("Building EN HTML...")
    html_en = build_html('en')
    en_html_path = OUT_DIR / "kepmen-taxonomy-2025-EN.html"
    en_html_path.write_text(html_en)
    print(f"  Written: {en_html_path} ({len(html_en)} bytes)")

    # ID
    print("Building ID HTML...")
    html_id = build_html('id')
    id_html_path = OUT_DIR / "kepmen-taxonomy-2025-ID.html"
    id_html_path.write_text(html_id)
    print(f"  Written: {id_html_path} ({len(html_id)} bytes)")

    # PDFs
    print("Rendering EN PDF via Playwright...")
    en_pdf_path = OUT_DIR / "kepmen-taxonomy-2025-EN.pdf"
    await html_to_pdf(str(en_html_path), en_pdf_path)
    print(f"  Written: {en_pdf_path}")

    print("Rendering ID PDF via Playwright...")
    id_pdf_path = OUT_DIR / "kepmen-taxonomy-2025-ID.pdf"
    await html_to_pdf(str(id_html_path), id_pdf_path)
    print(f"  Written: {id_pdf_path}")

    elapsed = time.time() - t0
    print(f"\nTotal render time: {elapsed:.1f}s")
    print(f"Files in {OUT_DIR}:")
    for f in sorted(OUT_DIR.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name}: {size:,} bytes")


if __name__ == "__main__":
    asyncio.run(main())
