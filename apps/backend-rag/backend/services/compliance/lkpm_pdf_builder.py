"""
LKPM PDF Builder — reportlab Platypus implementation.

Generates a print-ready PDF (bytes) from LkpmPackData.
All rendering is synchronous (reportlab is blocking) — call from a thread
if needed, but for typical pack sizes (<1 MB) it completes in <200 ms.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ── Colour palette ────────────────────────────────────────────────────────
_BLUE_DARK = colors.HexColor("#1a5276")
_BLUE_LIGHT = colors.HexColor("#d6eaf8")
_GREY = colors.HexColor("#f2f3f4")
_BLACK = colors.black


# ── Data model ────────────────────────────────────────────────────────────


@dataclass
class LkpmPackData:
    """Input data for LkpmPdfBuilder.build()."""

    client_name: str
    pt_nib: str  # NIB of the PT PMA
    period: str  # e.g. "Q1 2026"
    kbli_rows: list[dict[str, Any]]  # each dict: {kbli_code, kegiatan_usaha_desc, ...}
    assignee: str  # tax consultant email
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional realization total (non-negative IDR).
    realization_idr: int = 0

    def __post_init__(self) -> None:
        if self.realization_idr < 0:
            raise ValueError(
                f"realization_idr must be non-negative, got {self.realization_idr}"
            )


# ── Builder ───────────────────────────────────────────────────────────────


class LkpmPdfBuilder:
    """Build an in-memory PDF from LkpmPackData."""

    PAGE_WIDTH, PAGE_HEIGHT = A4
    MARGIN = 2 * cm

    # KBLI table column proportions (relative to usable width)
    _KBLI_COL_WEIGHTS = (0.15, 0.55, 0.30)

    def build(self, data: LkpmPackData) -> bytes:
        """
        Render a reportlab Platypus PDF from *data* and return raw bytes.

        Raises:
            ValueError: if data validation fails (see LkpmPackData.__post_init__).
        """
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN,
            title=f"LKPM {data.period}",
            author="Bali Zero — Zantara",
        )

        styles = getSampleStyleSheet()
        story = []

        # ── Title ─────────────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "lkpm_title",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=_BLUE_DARK,
            spaceAfter=4,
        )
        story.append(Paragraph(f"LKPM {data.period}", title_style))
        story.append(Spacer(1, 0.3 * cm))

        # ── Client header ─────────────────────────────────────────────────
        header_style = ParagraphStyle(
            "lkpm_header",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
        )
        label_style = ParagraphStyle(
            "lkpm_label",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=_BLUE_DARK,
            fontName="Helvetica-Bold",
        )

        usable_width = self.PAGE_WIDTH - 2 * self.MARGIN
        header_rows = [
            [
                Paragraph("Perusahaan:", label_style),
                Paragraph(data.client_name, header_style),
            ],
            [
                Paragraph("NIB:", label_style),
                Paragraph(data.pt_nib or "—", header_style),
            ],
            [
                Paragraph("Periode:", label_style),
                Paragraph(data.period, header_style),
            ],
            [
                Paragraph("Assignee:", label_style),
                Paragraph(data.assignee or "—", header_style),
            ],
            [
                Paragraph("Dibuat:", label_style),
                Paragraph(
                    data.generated_at.strftime("%Y-%m-%d %H:%M UTC"), header_style
                ),
            ],
        ]
        header_table = Table(
            header_rows,
            colWidths=[usable_width * 0.22, usable_width * 0.78],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _GREY),
                    ("BOX", (0, 0), (-1, -1), 0.5, _BLUE_DARK),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 0.5 * cm))

        # ── Realization summary ───────────────────────────────────────────
        section_style = ParagraphStyle(
            "lkpm_section",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=_BLUE_DARK,
            spaceAfter=4,
        )
        story.append(Paragraph("Realisasi Investasi (IDR)", section_style))
        body_style = ParagraphStyle(
            "lkpm_body",
            parent=styles["Normal"],
            fontSize=10,
        )
        formatted = f"Rp {data.realization_idr:,}".replace(",", ".")
        story.append(Paragraph(formatted, body_style))
        story.append(Spacer(1, 0.5 * cm))

        # ── KBLI table ────────────────────────────────────────────────────
        story.append(Paragraph("Daftar KBLI", section_style))

        col_widths = [usable_width * w for w in self._KBLI_COL_WEIGHTS]
        th_style = ParagraphStyle(
            "kbli_th",
            parent=styles["Normal"],
            fontSize=9,
            fontName="Helvetica-Bold",
            textColor=colors.white,
        )
        td_style = ParagraphStyle(
            "kbli_td",
            parent=styles["Normal"],
            fontSize=9,
        )

        kbli_data: list[list[Any]] = [
            [
                Paragraph("Kode KBLI", th_style),
                Paragraph("Kegiatan Usaha", th_style),
                Paragraph("Status OSS", th_style),
            ]
        ]

        if data.kbli_rows:
            for row in data.kbli_rows:
                kbli_data.append(
                    [
                        Paragraph(str(row.get("kbli_code", "—")), td_style),
                        Paragraph(str(row.get("kegiatan_usaha_desc", "—")), td_style),
                        Paragraph(str(row.get("oss_status", "—")), td_style),
                    ]
                )
        else:
            no_rows_style = ParagraphStyle(
                "kbli_empty",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.grey,
                fontName="Helvetica-Oblique",
            )
            kbli_data.append(
                [
                    Paragraph("—", td_style),
                    Paragraph("Tidak ada baris KBLI tersedia.", no_rows_style),
                    Paragraph("—", td_style),
                ]
            )

        kbli_table = Table(kbli_data, colWidths=col_widths, repeatRows=1)
        row_count = len(kbli_data)
        kbli_table.setStyle(
            TableStyle(
                [
                    # Header
                    ("BACKGROUND", (0, 0), (-1, 0), _BLUE_DARK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    # Alternating rows
                    ("ROWBACKGROUNDS", (0, 1), (-1, row_count - 1), [colors.white, _BLUE_LIGHT]),
                    # Grid
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                    ("BOX", (0, 0), (-1, -1), 0.8, _BLUE_DARK),
                    # Padding
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(kbli_table)
        story.append(Spacer(1, 0.5 * cm))

        # ── Footer note ───────────────────────────────────────────────────
        footer_style = ParagraphStyle(
            "lkpm_footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.grey,
            fontName="Helvetica-Oblique",
        )
        story.append(
            Paragraph(
                "Dokumen ini digenerate secara otomatis oleh Bali Zero — Zantara. "
                "Salin nilai dari laporan ini ke formulir OSS. "
                "Semua nilai dalam Rupiah (IDR).",
                footer_style,
            )
        )

        doc.build(story)
        pdf_bytes = buf.getvalue()
        logger.debug(
            "LkpmPdfBuilder: built PDF for %s / %s — %d bytes",
            data.client_name,
            data.period,
            len(pdf_bytes),
        )
        return pdf_bytes


__all__ = ["LkpmPackData", "LkpmPdfBuilder"]
