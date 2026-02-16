# CRM Hooks & Components

## Overview

Ottimizzazione del CRM workspace con React Query, virtualizzazione e gestione errori.

## Hooks

### useCrmClients

Gestione lista clienti con caching e infinite scroll.

```typescript
const { clients, total, isLoading, loadMore, hasMore } = useCrmClients({
  status: "active",
  search: "john",
  limit: 50,
});
```

### useCrmClient

Singolo cliente con caching.

```typescript
const { data: client, isLoading } = useCrmClient(clientId);
```

### useCreateClient / useUpdateClient

Mutation per creazione/aggiornamento.

```typescript
const createMutation = useCreateClient();
const updateMutation = useUpdateClient(clientId);
```

### useCrmPractices

Lista pratiche con filtri.

```typescript
const { practices } = useCrmPractices({
  clientId: 123,
  status: "in_progress",
});
```

### useCrmSearch

Ricerca con debounce.

```typescript
const { results, isLoading, query, setQuery } = useCrmSearch({
  debounceMs: 300,
});
```

### useQuickSearch

Command palette per ricerca veloce.

```typescript
const { isOpen, open, close, results, selectedIndex } = useQuickSearch();
```

### useCrmNotifications

Notifiche basate su expiry alerts.

```typescript
const { notifications, unreadCount, markAsRead } = useCrmNotifications();
```

### useExpiryAlerts / useUpcomingRenewals

Alert per documenti in scadenza.

```typescript
const { data: alerts } = useExpiryAlerts({ alertColor: "red" });
const { data: renewals } = useUpcomingRenewals(90);
```

### useDashboardStats

Statistiche dashboard.

```typescript
const { data: stats } = useDashboardStats();
```

## Components

### CRMErrorBoundary

Gestione errori per sezioni CRM.

```tsx
<CRMErrorBoundary section="Clients">
  <ClientsList />
</CRMErrorBoundary>
```

### QuickSearch

Command palette con Ctrl+K.

```tsx
<QuickSearchTrigger />
<QuickSearch open={isOpen} onOpenChange={setIsOpen} />
```

## Pagine Aggiornate

### /clients

- Virtualized list per grandi dataset
- useCrmClients con caching
- Debounced search
- CRMErrorBoundary

## Benefici

1. **Performance**: Virtualizzazione lista, caching React Query
2. **UX**: Ricerca debounced, command palette, skeleton loading
3. **Resilienza**: Error boundary per sezioni isolate
4. **Manutenibilità**: Hooks riutilizzabili, tipi TypeScript
