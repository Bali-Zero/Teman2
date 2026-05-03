# 🚀 Frontend Performance Guide

**Last Updated:** 2026-01-13  
**Status:** Active Best Practices

---

## 📋 Overview

Questo documento descrive le best practices e ottimizzazioni di performance implementate nel frontend Nuzantara (`apps/mouth`).

---

## 🎯 Performance Targets

| Metrica                | Target  | Attuale  | Status               |
| ---------------------- | ------- | -------- | -------------------- |
| **INP**                | < 200ms | < 500ms  | ✅ Needs Improvement |
| **LCP**                | < 2.5s  | ~1.2s    | ✅ Good              |
| **CLS**                | < 0.1   | ~0.05    | ✅ Good              |
| **Memory (200 items)** | < 20MB  | ~10-15MB | ✅ Good              |
| **Scroll FPS**         | 60fps   | 60fps    | ✅ Good              |

---

## ✅ Ottimizzazioni Implementate

### 1. Virtualizzazione Liste

**Quando usare:** Liste con >20-30 items

**Implementazione:**

- **ClientKanban:** Virtualizzazione per colonne >20 items
- **Client Grid:** Virtualizzazione per liste >30 items
- **Chat Messages:** Virtualizzazione per >20 messaggi

**Thresholds:**

```typescript
// ClientKanban
const VIRTUALIZATION_THRESHOLD = 20; // items per colonna
const ESTIMATED_CARD_HEIGHT = 180;

// Client Grid
const VIRTUALIZATION_THRESHOLD = 30; // items totali
const ESTIMATED_CARD_HEIGHT = 200;
```

**Esempio:**

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualizedList({ items }: { items: Item[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = items.length > THRESHOLD;

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_HEIGHT,
    overscan: 3,
  });

  if (!shouldVirtualize) {
    // Fallback per liste piccole
    return items.map(item => <ItemCard key={item.id} item={item} />);
  }

  const virtualItems = virtualizer.getVirtualItems();
  return (
    <div ref={parentRef} className="overflow-auto">
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualItems.map(virtualItem => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            <ItemCard item={items[virtualItem.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Benefici:**

- ✅ Riduzione memory usage del 70-80%
- ✅ Initial render più veloce dell'85-90%
- ✅ Scroll smooth (60fps) anche con 200+ items

---

### 2. Memoizzazione Componenti

**Quando usare:** Componenti renderizzati frequentemente con props che cambiano raramente

**Implementazione:**

#### A) React.memo con Default Comparison

```typescript
export const StatsCard = React.memo(function StatsCard({
  title,
  value,
  icon: Icon,
  // ...
}: StatsCardProps) {
  // Component implementation
});
```

#### B) React.memo con Custom Comparison

```typescript
export const ClientCard = React.memo(
  ({ client, isDragging }: ClientCardProps) => {
    // Component implementation
  },
  (prevProps, nextProps) => {
    // Custom comparison - solo re-render se dati critici cambiano
    return (
      prevProps.client.id === nextProps.client.id &&
      prevProps.client.last_sentiment === nextProps.client.last_sentiment &&
      prevProps.client.last_interaction_date ===
        nextProps.client.last_interaction_date &&
      prevProps.isDragging === nextProps.isDragging
    );
  },
);
```

**Best Practices:**

- ✅ Usa `React.memo` per componenti in liste
- ✅ Usa custom comparison solo quando necessario
- ✅ Confronta solo campi critici per performance
- ⚠️ NON memoizzare componenti con props che cambiano spesso

**Benefici:**

- ✅ Riduzione re-renders del 60-90%
- ✅ Miglioramento performance generale

---

### 3. useMemo per Valori Derivati

**Quando usare:** Calcoli costosi o valori derivati da props/state

**Implementazione:**

```typescript
function useDashboardData() {
  const { data } = useQuery({ ... });

  // Memoizza valori derivati
  const totalUnread = useMemo(
    () => stats.whatsappUnread + stats.emailUnread,
    [stats.whatsappUnread, stats.emailUnread]
  );

  const isHealthy = useMemo(
    () => systemStatus === 'healthy',
    [systemStatus]
  );

  return { totalUnread, isHealthy, ... };
}
```

**Best Practices:**

- ✅ Memoizza calcoli costosi
- ✅ Memoizza valori derivati usati in più posti
- ✅ Includi tutte le dipendenze nell'array
- ⚠️ NON memoizzare valori semplici (overhead > benefit)

---

### 4. Ottimizzazione Framer Motion

**Problema:** Troppi `motion.*` components possono causare INP issues

**Best Practices:**

- ✅ Usa CSS animations per transizioni semplici
- ✅ Limita animazioni simultanee a 5-10
- ✅ Usa `will-change` CSS invece di Framer Motion quando possibile
- ✅ Rimuovi `layoutId` se non necessario (causa calcoli costosi)
- ⚠️ Lazy-load componenti con molte animazioni

**Esempio:**

```typescript
// ❌ BAD - Troppi motion components
{items.map(item => (
  <motion.div key={item.id}>
    <motion.span>{item.name}</motion.span>
    <motion.p>{item.description}</motion.p>
  </motion.div>
))}

// ✅ GOOD - CSS animations per elementi semplici
{items.map(item => (
  <div key={item.id} className="animate-fade-in">
    <span>{item.name}</span>
    <p>{item.description}</p>
  </div>
))}
```

---

### 5. Lazy Loading Componenti Pesanti

**Quando usare:** Componenti con bundle size grande o inizializzazione costosa

**Implementazione:**

```typescript
import dynamic from "next/dynamic";

const ParticlesBackground = dynamic(
  () => import("@/components/ui/particles-background"),
  {
    ssr: false,
    loading: () => null,
  },
);
```

**Best Practices:**

- ✅ Lazy-load componenti non critici
- ✅ Usa `ssr: false` per componenti client-only
- ✅ Fornisci loading state appropriato

---

## 🚫 Anti-Patterns da Evitare

### 1. ❌ Renderizzare Tutti gli Items

```typescript
// ❌ BAD - Renderizza tutti i 200+ items
{clients.map(client => <ClientCard key={client.id} client={client} />)}

// ✅ GOOD - Virtualizza liste grandi
{shouldVirtualize ? (
  <VirtualizedList items={clients} />
) : (
  clients.map(client => <ClientCard key={client.id} client={client} />)
)}
```

### 2. ❌ Re-calcolare Valori Derivati ad Ogni Render

```typescript
// ❌ BAD - Ricalcola ad ogni render
const total = stats.a + stats.b;

// ✅ GOOD - Memoizza valore derivato
const total = useMemo(() => stats.a + stats.b, [stats.a, stats.b]);
```

### 3. ❌ Troppi Motion Components Simultanei

```typescript
// ❌ BAD - 45+ motion components simultanei
{items.map(item => (
  <motion.div>
    <motion.span>...</motion.span>
    <motion.p>...</motion.p>
    {/* ... molti altri motion components */}
  </motion.div>
))}

// ✅ GOOD - Limita animazioni simultanee
{items.slice(0, 10).map(item => (
  <motion.div>...</motion.div>
))}
```

### 4. ❌ layoutId Non Necessario

```typescript
// ❌ BAD - layoutId causa calcoli costosi con molti items
<motion.div layoutId={`item-${id}`}>...</motion.div>

// ✅ GOOD - Rimuovi se non necessario
<motion.div>...</motion.div>
```

---

## 📊 Monitoring Performance

### Web Vitals

**Setup:**

```typescript
import { initWebVitals } from "@/lib/web-vitals";

initWebVitals({
  enabled: true,
  debug: process.env.NODE_ENV === "development",
  sendToAnalytics: (metric) => {
    // Send to Sentry, GA, etc.
  },
});
```

**Metriche Monitorate:**

- **LCP** (Largest Contentful Paint)
- **CLS** (Cumulative Layout Shift)
- **INP** (Interaction to Next Paint) ⭐ Most important
- **TTFB** (Time to First Byte)

### Chrome DevTools

**Performance Tab:**

1. Apri DevTools → Performance
2. Click Record
3. Interagisci con la pagina
4. Stop e analizza INP

**Memory Tab:**

1. Apri DevTools → Memory
2. Heap snapshot prima
3. Esegui azioni
4. Heap snapshot dopo
5. Confronta memory usage

**React DevTools:**

1. Install React DevTools extension
2. Components tab → "Highlight updates"
3. Verifica che componenti memoizzati non re-renderizzino inutilmente

---

## 🔧 Configurazioni

### Virtualization Thresholds

```typescript
// apps/mouth/src/components/crm/ClientKanban.tsx
const VIRTUALIZATION_THRESHOLD = 20; // items per colonna
const ESTIMATED_CARD_HEIGHT = 180;

// apps/mouth/src/app/(workspace)/clients/page.tsx
const VIRTUALIZATION_THRESHOLD = 30; // items totali per grid
const ESTIMATED_CARD_HEIGHT = 200;
```

### React Query staleTime

```typescript
// Best practices per staleTime
useQuery({
  queryKey: ["dashboard"],
  staleTime: 30_000, // 30 secondi per dati real-time
  refetchInterval: 60_000, // Auto-refresh ogni minuto
});

useQuery({
  queryKey: ["clients"],
  staleTime: 60_000, // 1 minuto per dati che cambiano meno spesso
});
```

---

## 📚 Risorse

- [React Performance Optimization](https://react.dev/learn/render-and-commit)
- [@tanstack/react-virtual Docs](https://tanstack.com/virtual/latest)
- [Web Vitals](https://web.dev/vitals/)
- [Chrome DevTools Performance](https://developer.chrome.com/docs/devtools/performance/)

---

## ✅ Checklist per Nuovi Componenti

Prima di creare un nuovo componente che renderizza liste:

- [ ] Valuto se serve virtualizzazione (>20-30 items)?
- [ ] Uso `React.memo` se componente in lista?
- [ ] Memoizzo valori derivati con `useMemo`?
- [ ] Limito animazioni Framer Motion (<10 simultanee)?
- [ ] Lazy-load componenti pesanti?
- [ ] Testo performance con Chrome DevTools?

---

**Last Updated:** 2026-01-13  
**Maintained by:** Nuzantara Team
