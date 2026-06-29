"""Accounting services — cash-control business logic for Asya.

Data/logic separation (golden rule #7): this package holds business logic;
data access goes through asyncpg connections passed in by the router. No HTTP
concerns here.
"""
