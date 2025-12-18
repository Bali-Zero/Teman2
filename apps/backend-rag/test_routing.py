#!/usr/bin/env python3
"""Test routing logic"""
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/backend')

from backend.services.query_router import QueryRouter

router = QueryRouter()
query = 'Chi è il fondatore di Bali Zero?'
result = router.route(query)
print(f'Query: {query}')
print(f'Routed to: {result}')
print(f'Lowercased: {query.lower()}')
print(f'fondatore in query: {"fondatore" in query.lower()}')

# Check if fondatore is in TEAM_KEYWORDS
print(f'\nTEAM_KEYWORDS has fondatore: {"fondatore" in router.TEAM_KEYWORDS}')
print(f'TEAM_KEYWORDS: {router.TEAM_KEYWORDS[:20]}')  # First 20 keywords
