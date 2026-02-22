"""
Invoice automation service for practice quotations.

Automatically generates and sends invoices when practice status changes to sending_invoice.
"""

from .invoice_generator import InvoiceGenerator
from .invoice_service import InvoiceAutomationService

__all__ = ["InvoiceGenerator", "InvoiceAutomationService"]
