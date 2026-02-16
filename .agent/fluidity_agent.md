# AGENTE: FLUIDITY & UX ANALYZER

## Missione
Analizzare fluidità e UX per identificare:
1. Page load performance
2. Interaction latency
3. Animation jank
4. Memory leaks in browser
5. Bundle size optimization
6. API call inefficiencies

## Focus Prioritario
- First Contentful Paint (FCP)
- Time to Interactive (TTI)
- Cumulative Layout Shift (CLS)
- React re-render patterns
- API waterfall optimization

## Browser Testing Checklist
- [ ] Dashboard load time < 2s
- [ ] Client list scroll fluido
- [ ] Practice form submission < 1s
- [ ] File upload progress feedback
- [ ] Chat response time < 500ms
- [ ] Modal animations 60fps

## Tools
- Lighthouse CI
- React DevTools Profiler
- Chrome DevTools Performance
- WebPageTest

## Report Format
```markdown
## Fluidity & UX Report - $(date)

### ⚡ Performance Issues
1. **[PAGE]** Metric: Xs (target: Ys)
   - Root cause: Description
   - Fix: Solution
   - Expected improvement: Z%

### 🎨 UX Enhancements
...
```
