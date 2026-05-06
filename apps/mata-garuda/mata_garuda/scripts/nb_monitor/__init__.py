"""
NB Mitochondrial Value Monitor.

Daily cron that measures which NotebookLM notebooks produce value consumed
downstream by Nuzantara. Five metric collectors → tier classifier → SQLite
snapshot → optional Telegram alert + weekly markdown report.

Spec: docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md
Plan: docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md
"""
__version__ = "0.1.0"
