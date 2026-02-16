# Frontend Next.js — Regole (attiva su file in apps/mouth)

## Struttura

```
apps/mouth/src/
├── app/                    # Next.js App Router
│   ├── (blog)/             # articoli e blog
│   └── layout.tsx          # root layout
├── components/             # React components
├── content/articles/       # MDX (business/, immigration/, lifestyle/)
├── lib/blog/               # utilities blog
└── public/                 # static assets
```

## Pattern TypeScript

```typescript
interface DataResponse { id: string; name: string; }

async function fetchData(id: string): Promise<DataResponse | null> {
  try {
    const res = await fetch(`/api/${id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error('Fetch failed:', error);
    return null;
  }
}
```

## Regole

- Functional components TypeScript sempre
- Props interface sempre definita
- Tailwind CSS per styling
- `'use client'` solo se necessario (preferisci Server Components)
- MDX articles: frontmatter obbligatorio (title, description, date, category, slug)

## Comandi

```bash
cd apps/mouth
npm run dev    # :3000
npm run build
npm run lint
```
