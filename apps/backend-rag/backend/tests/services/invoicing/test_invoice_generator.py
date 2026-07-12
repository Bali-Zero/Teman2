import re

import pytest

from backend.services.invoicing.invoice_generator import _REPORTLAB_AVAILABLE, InvoiceGenerator


def test_generate_invoice_number_uses_current_month_and_padded_practice_id() -> None:
    generator = InvoiceGenerator()

    invoice_number = generator.generate_invoice_number(42)

    assert re.fullmatch(r"INV-\d{6}-00042", invoice_number)


@pytest.mark.skipif(not _REPORTLAB_AVAILABLE, reason="reportlab not installed")
def test_generate_returns_non_empty_pdf_bytes_with_discount() -> None:
    generator = InvoiceGenerator()

    pdf_bytes = generator.generate(
        practice_id=42,
        client_name="Example Client",
        client_email="client@example.com",
        client_phone="+628123456789",
        client_address="Jl. Sunset Road 1, Bali",
        practice_type="KITAS",
        practice_description="KITAS renewal package",
        quoted_price=5_000_000,
        notes="Payment reference: INV test.",
        discount_amount=500_000,
        discount_reason="Repeat client",
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1_000
