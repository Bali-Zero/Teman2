"""
PDF Invoice Generator using ReportLab.

Generates professional invoices for practice quotations with company branding.
Template updated: 2026-03-02 — PT BAYU BALI NOL layout.
"""

import io
from datetime import datetime, timedelta, timezone

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False
    colors = None  # type: ignore[assignment]
    A4 = (595.27, 841.89)  # type: ignore[assignment]

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)


class InvoiceGenerator:
    """Generates professional PDF invoices for practices."""

    # ── Company Info ────────────────────────────────────────────────────────
    COMPANY_NAME = "PT BAYU BALI NOL"
    COMPANY_TAX_ID = "NPWP: 1000000001239938"
    COMPANY_EMAIL = "asya@balizero.com"
    COMPANY_PHONE = "+62 881038467246"

    # ── Bank Details ────────────────────────────────────────────────────────
    BANK_ACCOUNT_NAME = "PT BAYU BALI NOL"
    BANK_ACCOUNT_NUMBER = "800198149700"
    BANK_NAME = "CIMB NIAGA"
    BANK_BRANCH = "JL MELATI NO 29, DANGIN PURI KANGIN, DENPASAR, BALI, 80236"
    BANK_SWIFT = "BNIAIDJA"

    # ── Invoice Settings ────────────────────────────────────────────────────
    PAYMENT_TERMS_DAYS = 7
    CURRENCY = "IDR"

    # ── Brand Colors (lazy — None when reportlab not installed) ─────────────
    COLOR_ACCENT = colors.HexColor("#1a1a2e") if _REPORTLAB_AVAILABLE else None
    COLOR_LIGHT = colors.HexColor("#f4f6f9") if _REPORTLAB_AVAILABLE else None
    COLOR_BORDER = colors.HexColor("#dee2e6") if _REPORTLAB_AVAILABLE else None
    COLOR_TEXT = colors.HexColor("#212529") if _REPORTLAB_AVAILABLE else None
    COLOR_MUTED = colors.HexColor("#6c757d") if _REPORTLAB_AVAILABLE else None
    COLOR_WHITE = colors.white if _REPORTLAB_AVAILABLE else None

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="InvoiceTitle",
                parent=self.styles["Heading1"],
                fontSize=28,
                fontName="Helvetica-Bold",
                textColor=self.COLOR_TEXT,
                spaceAfter=4,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="CompanyName",
                parent=self.styles["Normal"],
                fontSize=13,
                fontName="Helvetica-Bold",
                textColor=self.COLOR_TEXT,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="CompanyInfo",
                parent=self.styles["Normal"],
                fontSize=9,
                textColor=self.COLOR_MUTED,
                spaceAfter=2,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionLabel",
                parent=self.styles["Normal"],
                fontSize=8,
                fontName="Helvetica-Bold",
                textColor=self.COLOR_MUTED,
                spaceAfter=4,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="ClientName",
                parent=self.styles["Normal"],
                fontSize=11,
                fontName="Helvetica-Bold",
                textColor=self.COLOR_TEXT,
                spaceAfter=2,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="ClientDetail",
                parent=self.styles["Normal"],
                fontSize=9,
                textColor=self.COLOR_MUTED,
                spaceAfter=1,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Footer",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=self.COLOR_MUTED,
                alignment=1,
            )
        )

    def generate_invoice_number(self, practice_id: int) -> str:
        """Generate invoice number: INV-YYYYMM-XXXXX."""
        date_str = datetime.now(tz=timezone.utc).strftime("%Y%m")
        return f"INV-{date_str}-{practice_id:05d}"

    def generate(
        self,
        practice_id: int,
        client_name: str,
        client_email: str | None,
        client_phone: str | None,
        client_address: str | None,
        practice_type: str,
        practice_description: str | None,
        quoted_price: float,
        notes: str | None = None,
    ) -> bytes:
        """Generate invoice PDF as bytes."""
        logger.info(f"Generating invoice for practice {practice_id}")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        invoice_number = self.generate_invoice_number(practice_id)
        issue_date = datetime.now(tz=timezone.utc)
        due_date = issue_date + timedelta(days=self.PAYMENT_TERMS_DAYS)

        elements = []

        # ── HEADER: Company (left) + INVOICE title (right) ──────────────────
        header_data = [
            [
                Paragraph(f"<b>{self.COMPANY_NAME}</b>", self.styles["CompanyName"]),
                Paragraph("INVOICE", self.styles["InvoiceTitle"]),
            ]
        ]
        header_table = Table(header_data, colWidths=[10 * cm, 7 * cm])
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(header_table)

        # Company sub-info
        elements.append(
            Paragraph(f"{self.COMPANY_EMAIL} | {self.COMPANY_PHONE}", self.styles["CompanyInfo"])
        )
        elements.append(Paragraph(self.COMPANY_TAX_ID, self.styles["CompanyInfo"]))
        elements.append(Spacer(1, 0.4 * cm))

        # ── Divider ──────────────────────────────────────────────────────────
        divider = Table([[""]], colWidths=[17 * cm])
        divider.setStyle(
            TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -1), 1.5, self.COLOR_ACCENT),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(divider)
        elements.append(Spacer(1, 0.5 * cm))

        # Invoice number line
        elements.append(Paragraph(f"<b>{invoice_number}</b>", self.styles["CompanyInfo"]))
        elements.append(Spacer(1, 0.5 * cm))

        # ── BILL TO (left) + INVOICE DETAILS (right) ─────────────────────────
        # Build bill-to block
        bill_lines = []
        bill_lines.append(Paragraph("BILL TO", self.styles["SectionLabel"]))
        bill_lines.append(Paragraph(client_name, self.styles["ClientName"]))
        if client_email:
            bill_lines.append(Paragraph(client_email, self.styles["ClientDetail"]))
        if client_phone:
            bill_lines.append(Paragraph(client_phone, self.styles["ClientDetail"]))
        if client_address:
            bill_lines.append(Paragraph(client_address, self.styles["ClientDetail"]))

        # Build invoice details block
        detail_rows = [
            ["Issue Date:", issue_date.strftime("%d %B %Y")],
            ["Due Date:", due_date.strftime("%d %B %Y")],
            ["Practice ID:", f"#{practice_id}"],
            ["Payment Terms:", f"{self.PAYMENT_TERMS_DAYS} days"],
        ]
        detail_table = Table(detail_rows, colWidths=[3.5 * cm, 4 * cm])
        detail_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                    ("FONT", (1, 0), (1, -1), "Helvetica", 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), self.COLOR_TEXT),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        two_col_data = [[bill_lines, detail_table]]
        two_col = Table(two_col_data, colWidths=[9 * cm, 8 * cm])
        two_col.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(two_col)
        elements.append(Spacer(1, 0.8 * cm))

        # ── SERVICE TABLE ─────────────────────────────────────────────────────
        service_description = practice_description or practice_type

        svc_data = [
            ["DESCRIPTION", "QTY", "UNIT PRICE", "TOTAL"],
            [
                service_description,
                "1",
                f"{self.CURRENCY} {quoted_price:,.0f}",
                f"{self.CURRENCY} {quoted_price:,.0f}",
            ],
        ]
        svc_table = Table(svc_data, colWidths=[9 * cm, 2 * cm, 3 * cm, 3 * cm])
        svc_table.setStyle(
            TableStyle(
                [
                    # Header
                    ("BACKGROUND", (0, 0), (-1, 0), self.COLOR_ACCENT),
                    ("TEXTCOLOR", (0, 0), (-1, 0), self.COLOR_WHITE),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    # Data rows
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                    ("TEXTCOLOR", (0, 1), (-1, -1), self.COLOR_TEXT),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("BACKGROUND", (0, 1), (-1, -1), self.COLOR_LIGHT),
                    ("TOPPADDING", (0, 1), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    # Border
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, self.COLOR_BORDER),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.5, self.COLOR_BORDER),
                    ("BOX", (0, 0), (-1, -1), 0.5, self.COLOR_BORDER),
                ]
            )
        )
        elements.append(svc_table)
        elements.append(Spacer(1, 0.3 * cm))

        # ── TOTALS ────────────────────────────────────────────────────────────
        totals_data = [
            ["Subtotal:", f"{self.CURRENCY} {quoted_price:,.0f}"],
            ["Tax (0%):", f"{self.CURRENCY} 0"],
        ]
        total_row = [
            Paragraph(
                "<b>TOTAL DUE:</b>",
                ParagraphStyle(
                    "TotalLabel",
                    parent=self.styles["Normal"],
                    fontSize=11,
                    fontName="Helvetica-Bold",
                    textColor=self.COLOR_WHITE,
                    alignment=2,
                ),
            ),
            Paragraph(
                f"<b>{self.CURRENCY} {quoted_price:,.0f}</b>",
                ParagraphStyle(
                    "TotalAmt",
                    parent=self.styles["Normal"],
                    fontSize=11,
                    fontName="Helvetica-Bold",
                    textColor=self.COLOR_WHITE,
                    alignment=2,
                ),
            ),
        ]

        totals_table = Table(
            totals_data + [total_row],
            colWidths=[13 * cm, 4 * cm],
            hAlign="RIGHT",
        )
        totals_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (0, -2), "Helvetica", 9),
                    ("FONT", (1, 0), (1, -2), "Helvetica", 9),
                    ("TEXTCOLOR", (0, 0), (-1, -2), self.COLOR_MUTED),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -2), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -2), 3),
                    # Total row
                    ("BACKGROUND", (0, -1), (-1, -1), self.COLOR_ACCENT),
                    ("TOPPADDING", (0, -1), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                    ("LEFTPADDING", (0, -1), (-1, -1), 10),
                    ("RIGHTPADDING", (0, -1), (-1, -1), 10),
                ]
            )
        )
        elements.append(totals_table)
        elements.append(Spacer(1, 0.8 * cm))

        # ── PAYMENT INFORMATION ───────────────────────────────────────────────
        elements.append(
            Paragraph(
                "PAYMENT INFORMATION",
                ParagraphStyle(
                    "PaySection",
                    parent=self.styles["Normal"],
                    fontSize=10,
                    fontName="Helvetica-Bold",
                    textColor=self.COLOR_TEXT,
                    spaceAfter=6,
                ),
            )
        )

        pay_data = [
            ["Account Name:", self.BANK_ACCOUNT_NAME],
            ["Account Number:", self.BANK_ACCOUNT_NUMBER],
            ["Bank Name:", self.BANK_NAME],
            ["Bank Branch:", self.BANK_BRANCH],
            ["Swift Code:", self.BANK_SWIFT],
        ]
        pay_table = Table(pay_data, colWidths=[4 * cm, 13 * cm])
        pay_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                    ("FONT", (1, 0), (1, -1), "Helvetica", 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), self.COLOR_TEXT),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("BACKGROUND", (0, 0), (-1, -1), self.COLOR_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, self.COLOR_BORDER),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.5, self.COLOR_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(pay_table)
        elements.append(Spacer(1, 0.5 * cm))

        # Payment note
        payment_note = (
            f"Payment is due within {self.PAYMENT_TERMS_DAYS} days from the invoice date. "
            f"Please transfer to our company bank account and send proof of payment to "
            f"<b>{self.COMPANY_EMAIL}</b>"
        )
        if notes:
            payment_note += f"<br/><br/><i>{notes}</i>"
        elements.append(
            Paragraph(
                payment_note,
                ParagraphStyle(
                    "PayNote",
                    parent=self.styles["Normal"],
                    fontSize=9,
                    textColor=self.COLOR_TEXT,
                ),
            )
        )

        # ── FOOTER ────────────────────────────────────────────────────────────
        elements.append(Spacer(1, 1 * cm))
        footer_divider = Table([[""]], colWidths=[17 * cm])
        footer_divider.setStyle(
            TableStyle(
                [
                    ("LINEABOVE", (0, 0), (-1, -1), 0.5, self.COLOR_BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(footer_divider)
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(
            Paragraph(
                f"This invoice was automatically generated by Zantara CRM System | "
                f"For any questions, please contact {self.COMPANY_EMAIL}<br/>"
                f"{self.COMPANY_NAME} | Bali, Indonesia",
                self.styles["Footer"],
            )
        )

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"Invoice generated for practice {practice_id}, size: {len(pdf_bytes)} bytes")
        return pdf_bytes
