"""
backend.app.deps — Decomposed dependency injection modules.

This package splits the monolithic dependencies.py into focused sub-modules.
The original dependencies.py re-exports everything from here for backward compatibility.

Sub-modules:
- auth:        JWT auth, user extraction, RBAC guards
- database:    asyncpg pool access (strict + graceful)
- services:    Service locators (Search, AI, Router, Memory, Cache, Retriever, Channel)
- orchestrator: AgenticRAGOrchestrator lazy singleton
- crm_access:   CRM RBAC guards and user filters
"""
