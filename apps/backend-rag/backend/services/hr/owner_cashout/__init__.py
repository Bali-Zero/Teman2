"""Owner Weekly Cashout — private, owner-only HR feature.

Imports the WEEKLY CASHOUT google sheet into Postgres and exposes
aggregated + drill-down views via FastAPI, gated by require_owner.
"""
