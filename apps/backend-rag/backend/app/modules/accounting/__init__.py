"""Accounting module — cash-control workflow for Asya (the agency accountant).

Adds bank-statement reconciliation, a single flat money-log (weekly_cashout,
mirroring Asya's real Google Sheet), and an immutable reconciliation audit trail
on top of the existing invoice/practice machinery. Single-entry, cash-basis,
IDR-native (USD per-line with explicit FX). See migration 232_accounting_asya.sql
and research/operations/2026-06-25-accounting-asya-architecture.md.
"""
