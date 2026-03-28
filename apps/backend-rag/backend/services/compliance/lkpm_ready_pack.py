"""
LKPM Ready Pack Generator — HTML output formatted for OSS copy-paste.

All values are deterministic. Same input = same output, always.
Narrative uses pre-written templates with fill-in-the-blank, NOT AI generation.
"""

import logging
from datetime import datetime, timezone
from html import escape as html_escape

from backend.app.models.lkpm import LKPMReadyPack, ValidationSeverity

logger = logging.getLogger(__name__)

# Pre-written obstacle templates in Bahasa Indonesia (NO AI generation)
OBSTACLE_TEMPLATES = {
    "covid_impact": (
        "Dampak pandemi COVID-19 masih mempengaruhi operasional perusahaan, "
        "termasuk keterlambatan pengiriman peralatan dan pembatasan perjalanan "
        "tenaga kerja asing."
    ),
    "permit_delay": (
        "Proses perizinan yang memerlukan waktu lebih lama dari yang direncanakan, "
        "termasuk pengurusan izin {permit_type} yang masih dalam proses."
    ),
    "supply_chain": (
        "Gangguan rantai pasokan global menyebabkan keterlambatan pengadaan "
        "peralatan dan material yang diperlukan untuk realisasi investasi."
    ),
    "construction_delay": ("Proses pembangunan/renovasi mengalami keterlambatan akibat {reason}."),
    "market_conditions": (
        "Kondisi pasar yang belum stabil mempengaruhi rencana ekspansi "
        "dan realisasi investasi perusahaan."
    ),
    "no_obstacles": ("Tidak ada hambatan signifikan dalam realisasi investasi pada periode ini."),
}


def format_idr(amount: int) -> str:
    """Format amount in IDR with titik separator (Indonesian format)."""
    if amount == 0:
        return "0"
    formatted = f"{abs(amount):,}".replace(",", ".")
    return f"-{formatted}" if amount < 0 else formatted


def generate_ready_pack_html(pack: LKPMReadyPack) -> str:
    """Generate HTML Ready Pack for copy-paste into OSS."""
    logger.info(f"Generating Ready Pack HTML for draft {pack.draft_id}")

    # Validation status indicator
    validation_html = ""
    if pack.validation:
        for alert in pack.validation.alerts:
            color = {
                ValidationSeverity.GREEN: "#28a745",
                ValidationSeverity.YELLOW: "#ffc107",
                ValidationSeverity.RED: "#dc3545",
            }.get(alert.severity, "#6c757d")
            icon = {
                ValidationSeverity.GREEN: "&#10004;",
                ValidationSeverity.YELLOW: "&#9888;",
                ValidationSeverity.RED: "&#10006;",
            }.get(alert.severity, "&#8226;")
            validation_html += (
                f'<div style="color:{color};margin:2px 0;">{icon} {alert.message}</div>\n'
            )

    # Escape user-supplied strings to prevent XSS
    company = html_escape(pack.company_name)
    npwp = html_escape(pack.npwp or "—")
    nib = html_escape(pack.nib or "—")
    obstacles = html_escape(pack.narrative_obstacles or OBSTACLE_TEMPLATES["no_obstacles"])
    plans = html_escape(
        pack.narrative_plans
        or "Perusahaan akan melanjutkan realisasi investasi sesuai rencana yang telah disetujui.",
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>LKPM Ready Pack — {company} — {pack.quarter} {pack.year}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; color: #333; }}
        h1 {{ color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 8px; }}
        h2 {{ color: #2c3e50; margin-top: 24px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background-color: #f8f9fa; font-weight: 600; }}
        td.amount {{ text-align: right; font-family: monospace; }}
        .header-info {{ background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 20px; }}
        .header-info p {{ margin: 4px 0; }}
        .validation {{ background: #fff3cd; padding: 12px; border-radius: 6px; margin: 12px 0; }}
        .copy-hint {{ color: #6c757d; font-size: 0.85em; font-style: italic; }}
        .total-row {{ font-weight: bold; background-color: #e8f4fd; }}
        .pct {{ color: #6c757d; font-size: 0.9em; }}
        @media print {{ body {{ margin: 0; }} .no-print {{ display: none; }} }}
    </style>
</head>
<body>
    <h1>LKPM Ready Pack</h1>
    <p class="copy-hint no-print">Salin nilai dari tabel di bawah ke formulir OSS. Semua nilai dalam Rupiah (IDR).</p>

    <div class="header-info">
        <p><strong>Perusahaan:</strong> {company}</p>
        <p><strong>NPWP:</strong> {npwp}</p>
        <p><strong>NIB:</strong> {nib}</p>
        <p><strong>Periode:</strong> {pack.quarter} {pack.year}</p>
        <p><strong>KBLI:</strong> {", ".join(pack.kbli_codes) or "—"}</p>
        <p><strong>Realisasi terhadap Rencana:</strong> {pack.realization_percentage}%</p>
    </div>

    {f'<div class="validation"><strong>Validasi:</strong><br>{validation_html}</div>' if validation_html else ""}

    <h2>1. Realisasi Investasi — Periode Ini ({pack.quarter} {pack.year})</h2>
    <table>
        <thead>
            <tr>
                <th>Kategori</th>
                <th>Dalam Negeri (IDR)</th>
                <th>Impor (IDR)</th>
                <th>Total (IDR)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Peralatan/Mesin</td>
                <td class="amount">{format_idr(pack.realized.equipment_domestic)}</td>
                <td class="amount">{format_idr(pack.realized.equipment_import)}</td>
                <td class="amount">{format_idr(pack.realized.equipment_domestic + pack.realized.equipment_import)}</td>
            </tr>
            <tr>
                <td>Bangunan/Gedung</td>
                <td class="amount">{format_idr(pack.realized.building_domestic)}</td>
                <td class="amount">{format_idr(pack.realized.building_import)}</td>
                <td class="amount">{format_idr(pack.realized.building_domestic + pack.realized.building_import)}</td>
            </tr>
            <tr>
                <td>Kendaraan</td>
                <td class="amount">{format_idr(pack.realized.vehicle_domestic)}</td>
                <td class="amount">{format_idr(pack.realized.vehicle_import)}</td>
                <td class="amount">{format_idr(pack.realized.vehicle_domestic + pack.realized.vehicle_import)}</td>
            </tr>
            <tr>
                <td>Tanah</td>
                <td class="amount">{format_idr(pack.realized.land)}</td>
                <td class="amount">—</td>
                <td class="amount">{format_idr(pack.realized.land)}</td>
            </tr>
            <tr>
                <td>Modal Kerja</td>
                <td class="amount">{format_idr(pack.realized.working_capital)}</td>
                <td class="amount">—</td>
                <td class="amount">{format_idr(pack.realized.working_capital)}</td>
            </tr>
            <tr>
                <td>Lain-lain</td>
                <td class="amount">{format_idr(pack.realized.other)}</td>
                <td class="amount">—</td>
                <td class="amount">{format_idr(pack.realized.other)}</td>
            </tr>
            <tr class="total-row">
                <td>TOTAL</td>
                <td class="amount">{format_idr(pack.realized.total_domestic)}</td>
                <td class="amount">{format_idr(pack.realized.total_import)}</td>
                <td class="amount">{format_idr(pack.realized_total)}</td>
            </tr>
        </tbody>
    </table>

    <h2>2. Realisasi Kumulatif</h2>
    <table>
        <thead>
            <tr>
                <th>Kategori</th>
                <th>Kumulatif (IDR)</th>
                <th>Rencana (IDR)</th>
                <th>% Realisasi</th>
            </tr>
        </thead>
        <tbody>
            {_cumulative_row("Peralatan/Mesin DN", pack.cumulative.equipment_domestic, pack.plan.equipment_domestic)}
            {_cumulative_row("Peralatan/Mesin Impor", pack.cumulative.equipment_import, pack.plan.equipment_import)}
            {_cumulative_row("Bangunan DN", pack.cumulative.building_domestic, pack.plan.building_domestic)}
            {_cumulative_row("Bangunan Impor", pack.cumulative.building_import, pack.plan.building_import)}
            {_cumulative_row("Kendaraan DN", pack.cumulative.vehicle_domestic, pack.plan.vehicle_domestic)}
            {_cumulative_row("Kendaraan Impor", pack.cumulative.vehicle_import, pack.plan.vehicle_import)}
            {_cumulative_row("Tanah", pack.cumulative.land, pack.plan.land)}
            {_cumulative_row("Modal Kerja", pack.cumulative.working_capital, pack.plan.working_capital)}
            {_cumulative_row("Lain-lain", pack.cumulative.other, pack.plan.other)}
            <tr class="total-row">
                <td>TOTAL</td>
                <td class="amount">{format_idr(pack.cumulative_total)}</td>
                <td class="amount">{format_idr(pack.plan.grand_total)}</td>
                <td class="amount">{pack.realization_percentage}%</td>
            </tr>
        </tbody>
    </table>

    <h2>3. Tenaga Kerja</h2>
    <table>
        <thead>
            <tr><th>Kategori</th><th>Jumlah</th></tr>
        </thead>
        <tbody>
            <tr><td>TKI (Tenaga Kerja Indonesia)</td><td>{pack.employment.tki}</td></tr>
            <tr><td>TKA (Tenaga Kerja Asing)</td><td>{pack.employment.tka}</td></tr>
            <tr class="total-row"><td>TOTAL</td><td>{pack.employment.total}</td></tr>
        </tbody>
    </table>

    <h2>4. Pendapatan</h2>
    <table>
        <tbody>
            <tr><td>Pendapatan Triwulan</td><td class="amount">Rp {format_idr(pack.quarterly_revenue)}</td></tr>
            <tr><td>Pendapatan Tahunan</td><td class="amount">Rp {format_idr(pack.annual_revenue)}</td></tr>
        </tbody>
    </table>

    <h2>5. Hambatan & Rencana</h2>
    <div style="background:#f8f9fa;padding:12px;border-radius:6px;">
        <p><strong>Hambatan:</strong></p>
        <p>{obstacles}</p>
        <p><strong>Rencana Tindak Lanjut:</strong></p>
        <p>{plans}</p>
    </div>

    <div class="no-print" style="margin-top:24px;padding:12px;background:#e8f4fd;border-radius:6px;">
        <p><strong>Generated:</strong> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</p>
        <p><strong>Draft ID:</strong> {pack.draft_id}</p>
    </div>
</body>
</html>"""



def _cumulative_row(label: str, cumulative: int, planned: int) -> str:
    """Generate a cumulative comparison table row."""
    pct = f"{(cumulative / planned * 100):.1f}%" if planned > 0 else "—"
    return (
        f"<tr>"
        f"<td>{label}</td>"
        f'<td class="amount">{format_idr(cumulative)}</td>'
        f'<td class="amount">{format_idr(planned)}</td>'
        f'<td class="amount">{pct}</td>'
        f"</tr>"
    )
