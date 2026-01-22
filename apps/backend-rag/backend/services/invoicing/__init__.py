"""
Invoice automation service for practice quotations.

Automatically generates and sends invoices when practice status changes to quotation_sent.
"""

from .invoice_generator import InvoiceGenerator
from .invoice_service import InvoiceAutomationService

__all__ = ["InvoiceGenerator", "InvoiceAutomationService"]
