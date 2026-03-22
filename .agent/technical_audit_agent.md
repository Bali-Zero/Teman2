# AGENTE: TECHNICAL AUDIT ANALYZER

## Missione

Analizzare approfonditamente la codebase per identificare:

1. Code smells e anti-patterns
2. Performance bottlenecks
3. Security vulnerabilities
4. Type safety issues
5. Test coverage gaps
6. Architectural inconsistencies

## Focus Prioritario

- Backend: 88 routers, 244 services
- Frontend: React Query patterns, hook optimization
- Database: Query efficiency, N+1 problems
- API: Response time optimization

## Output Richiesto

1. Lista prioritaria dei 10 problemi più critici
2. Soluzioni tecniche specifiche
3. Effort estimate per ogni fix
4. File/linee specifiche da modificare

## Comando Esecuzione

```bash
cd /Users/nuzantara/Desktop/nuzantara
# Analisi completa
find apps/backend-rag/backend -name "*.py" -type f | head -50 | xargs grep -l "TODO\|FIXME\|XXX" 2>/dev/null
grep -r "async def\|def " apps/backend-rag/backend/app/routers/*.py | wc -l
grep -r "useEffect\|useCallback\|useMemo" apps/mouth/src --include="*.tsx" | wc -l
```

## Report Format

```markdown
## Technical Audit Report - $(date)

### 🔴 Critical Issues (Fix ASAP)

1. **[CATEGORY]** Issue name
   - Location: `file:line`
   - Impact: Description
   - Fix: Specific solution
   - Effort: XS/S/M/L

### 🟡 Warnings (Fix this week)

...

### 🟢 Enhancements (Next sprint)

...
```
