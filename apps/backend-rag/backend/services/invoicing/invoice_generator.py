"""
PDF Invoice Generator using ReportLab.

Generates professional invoices for practice quotations with company branding.
"""

import io
from datetime import datetime, timedelta
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas

from backend.core.logging_utils import get_logger

logger = get_logger(__name__)


class InvoiceGenerator:
    """Generates professional PDF invoices for practices."""

    # Company info (should come from config/env in production)
    COMPANY_NAME = "Zantara Indonesia"
    COMPANY_ADDRESS = "Jakarta, Indonesia"
    COMPANY_TAX_ID = "NPWP: XXX.XXX.XXX.X-XXX.XXX"
    COMPANY_EMAIL = "billing@zantara.com"
    COMPANY_PHONE = "+62 XXX XXXX XXXX"

    # Invoice settings
    PAYMENT_TERMS_DAYS = 7
    CURRENCY = "IDR"

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles for invoice."""
        self.styles.add(
            ParagraphStyle(
                name="InvoiceTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#1a1a1a"),
                spaceAfter=12,
                alignment=1,  # Center
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="CompanyInfo",
                parent=self.styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#666666"),
                alignment=2,  # Right
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="InvoiceLabel",
                parent=self.styles["Normal"],
                fontSize=10,
                textColor=colors.HexColor("#333333"),
                fontName="Helvetica-Bold",
            )
        )

    def generate_invoice_number(self, practice_id: int) -> str:
        """Generate unique invoice number based on practice ID and date."""
        date_str = datetime.now().strftime("%Y%m")
        return f"INV-{date_str}-{practice_id:05d}"

    def generate(
        self,
        practice_id: int,
        client_name: str,
        client_email: Optional[str],
        client_phone: Optional[str],
        client_address: Optional[str],
        practice_type: str,
        practice_description: Optional[str],
        quoted_price: float,
        notes: Optional[str] = None,
    ) -> bytes:
        """
        Generate invoice PDF as bytes.

        Args:
            practice_id: Practice ID
            client_name: Client full name
            client_email: Client email
            client_phone: Client phone
            client_address: Client address
            practice_type: Type of service (KITAS, VISA, etc.)
            practice_description: Description of service
            quoted_price: Price quoted to client
            notes: Optional notes/terms

        Returns:
            PDF bytes
        """
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

        # Invoice data
        invoice_number = self.generate_invoice_number(practice_id)
        issue_date = datetime.now()
        due_date = issue_date + timedelta(days=self.PAYMENT_TERMS_DAYS)

        # Build document elements
        elements = []

        # Header - Company info
        company_info = f"""
        <b>{self.COMPANY_NAME}</b><br/>
        {self.COMPANY_ADDRESS}<br/>
        {self.COMPANY_TAX_ID}<br/>
        {self.COMPANY_EMAIL} | {self.COMPANY_PHONE}
        """
        elements.append(Paragraph(company_info, self.styles["CompanyInfo"]))
        elements.append(Spacer(1, 1 * cm))

        # Invoice Title
        elements.append(Paragraph("INVOICE", self.styles["InvoiceTitle"]))
        elements.append(Spacer(1, 0.5 * cm))

        # Invoice details table
        invoice_details_data = [
            ["Invoice Number:", invoice_number],
            ["Issue Date:", issue_date.strftime("%d %B %Y")],
            ["Due Date:", due_date.strftime("%d %B %Y")],
            ["Practice ID:", f"#{practice_id}"],
        ]

        invoice_details_table = Table(
            invoice_details_data, colWidths=[4 * cm, 6 * cm], hAlign="LEFT"
        )
        invoice_details_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                    ("FONT", (1, 0), (1, -1), "Helvetica", 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#333333")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(invoice_details_table)
        elements.append(Spacer(1, 1 * cm))

        # Bill To section
        elements.append(Paragraph("<b>Bill To:</b>", self.styles["InvoiceLabel"]))
        elements.append(Spacer(1, 0.3 * cm))

        client_info = f"""
        <b>{client_name}</b><br/>
        {client_email or 'N/A'}<br/>
        {client_phone or 'N/A'}<br/>
        {client_address or 'N/A'}
        """
        elements.append(Paragraph(client_info, self.styles["Normal"]))
        elements.append(Spacer(1, 1 * cm))

        # Service details table
        elements.append(Paragraph("<b>Services:</b>", self.styles["InvoiceLabel"]))
        elements.append(Spacer(1, 0.3 * cm))

        service_description = practice_description or f"{practice_type} Processing Service"

        service_data = [
            ["Description", "Quantity", "Unit Price", "Total"],
            [service_description, "1", f"{self.CURRENCY} {quoted_price:,.0f}", f"{self.CURRENCY} {quoted_price:,.0f}"],
        ]

        service_table = Table(service_data, colWidths=[8 * cm, 2 * cm, 3 * cm, 3 * cm])
        service_table.setStyle(
            TableStyle(
                [
                    # Header row
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a90e2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    # Data rows
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # Grid
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    # Alternating row colors
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
                ]
            )
        )
        elements.append(service_table)
        elements.append(Spacer(1, 0.5 * cm))

        # Total section
        total_data = [
            ["Subtotal:", f"{self.CURRENCY} {quoted_price:,.0f}"],
            ["Tax (0%):", f"{self.CURRENCY} 0"],
            ["<b>Total Due:</b>", f"<b>{self.CURRENCY} {quoted_price:,.0f}</b>"],
        ]

        total_table = Table(total_data, colWidths=[13 * cm, 3 * cm], hAlign="RIGHT")
        total_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (0, -2), "Helvetica", 9),
                    ("FONT", (1, 0), (1, -2), "Helvetica", 9),
                    ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 11),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#4a90e2")),
                    ("LINEABOVE", (0, -1), (-1, -1), 2, colors.HexColor("#4a90e2")),
                ]
            )
        )
        elements.append(total_table)
        elements.append(Spacer(1, 1 * cm))

        # Payment terms
        elements.append(Paragraph("<b>Payment Terms:</b>", self.styles["InvoiceLabel"]))
        elements.append(Spacer(1, 0.3 * cm))

        payment_terms = f"""
        Payment is due within {self.PAYMENT_TERMS_DAYS} days from the invoice date.<br/>
        Please transfer to our company bank account and send proof of payment to {self.COMPANY_EMAIL}.<br/>
        <br/>
        <b>Bank Details:</b><br/>
        Bank: [Bank Name]<br/>
        Account Number: [Account Number]<br/>
        Account Name: {self.COMPANY_NAME}
        """
        elements.append(Paragraph(payment_terms, self.styles["Normal"]))

        if notes:
            elements.append(Spacer(1, 0.5 * cm))
            elements.append(Paragraph(f"<b>Notes:</b> {notes}", self.styles["Normal"]))

        # Footer
        elements.append(Spacer(1, 1.5 * cm))
        footer_text = f"""
        <i>This invoice was automatically generated by Zantara CRM System.<br/>
        For any questions, please contact {self.COMPANY_EMAIL}</i>
        """
        footer_style = ParagraphStyle(
            name="Footer",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#999999"),
            alignment=1,  # Center
        )
        elements.append(Paragraph(footer_text, footer_style))

        # Build PDF
        doc.build(elements)

        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(
            f"Invoice generated successfully for practice {practice_id}, size: {len(pdf_bytes)} bytes"
        )

        return pdf_bytes
