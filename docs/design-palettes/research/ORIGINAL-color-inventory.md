# Bali Zero — inventario colore dalle sorgenti reali

> Letto dai file `apps/mouth/src/**`, non inventato.
> Ogni colore qui ha un file source. Usare come fonte unica di verità per il draft Palette D.

## 1. Process Kanban (`components/process/kanban-colors.ts`)

La grammatica colore **più sofisticata** nel codice. 7 variabili coordinate per ogni stato, 3 intensità distinte (bg 3.5% / border 8% / badge 12%), **gradient pair** sempre stessa famiglia.

| Stato | gradientStart → End | tintBg | tintBorder | badgeBg | textColor | dotColor |
|---|---|---|---|---|---|---|
| `inquiry` | `#6b7280 → #9ca3af` | `rgba(156,163,175,.035)` | `rgba(156,163,175,.08)` | `rgba(156,163,175,.12)` | `#9ca3af` | gray-400 |
| `waiting_documents` | `#fb923c → #f97316` | `rgba(251,146,60,.035)` | `rgba(251,146,60,.08)` | `rgba(251,146,60,.12)` | `#fb923c` | orange-400 |
| `sending_invoice` | `#facc15 → #eab308` | `rgba(250,204,21,.03)` | `rgba(250,204,21,.07)` | `rgba(250,204,21,.12)` | `#facc15` | yellow-400 |
| `on_process` | `#3b82f6 → #2563eb` | `rgba(59,130,246,.035)` | `rgba(59,130,246,.08)` | `rgba(59,130,246,.12)` | `#3b82f6` | blue-500 |
| `completed` | `#22c55e → #16a34a` | `rgba(34,197,94,.04)` | `rgba(34,197,94,.09)` | `rgba(34,197,94,.12)` | `#22c55e` | green-500 |

**Pattern di rendering**: `backgroundColor: tintBg` sulla colonna + `borderTop 2px linear-gradient(start→end)` stripe + badge count `{background: badgeBg, color: textColor}` + dot sottostante `{backgroundColor: dotColor}`.

**Differenze di intensità sottili ma intenzionali**: inquiry bg 3.5% / completed bg 4% / sending_invoice bg 3%. Le più "calme" (inquiry) sono 0.5% più trasparenti delle più "positive" (completed).

## 2. Portal StatusBadge (`components/portal/StatusBadge.tsx`)

4 gruppi semantici, 4 hex piatti, intensità fissa `rgba 12%` bg.

| Gruppo | Hex | bg | Stati coperti |
|---|---|---|---|
| Green (success) | `#34d399` | `rgba(16,185,129,.12)` | active, compliant, verified, completed, approved, submitted, filed |
| Amber (warning) | `#fbbf24` | `rgba(245,158,11,.12)` | pending, processing, attention, warning, expiring, received, draft |
| Blue (info) | `#60a5fa` | `rgba(59,130,246,.12)` | uploaded |
| Red (error) | `#f87171` | `rgba(239,68,68,.12)` | expired, overdue, rejected, cancelled |

**Nota**: Portal usa `#34d399` verde brighter mentre kanban usa `#22c55e`. Diversi contesti, stesso significato.

## 3. Portal ProcessStepper (`components/portal/ProcessStepper.tsx`)

Timeline verticale con 3 stati:
- `completed` → circle verde `rgba(16,185,129,.15)` + check icon `#34d399` + line verticale `rgba(16,185,129,.3)`
- `current` → circle blu `rgba(59,130,246,.15)` + spinner icon `#60a5fa` + `animate-pulse` sul circle
- `pending` → circle white `rgba(255,255,255,.05)` + Circle icon grigio

**Text color**:
- current → `text-blue-400`
- completed → `text-[var(--bz-text-1)]`
- pending → `text-[var(--bz-text-3)]`

## 4. Service Pricing (`components/services/ServicePricing.tsx`)

**Logica pacchetti visa** (unica nel codice che mapping nome → colore):
- **KITAS / KITAP / Working / Freelance / Spouse / Dependent / Retirement / Investor KITAS** → **ORANGE**
  - `bg-orange-500/20 border-orange-500/40 hover:border-orange-400`
  - badge: `bg-orange-500`
- **Visit visa (C, D series) → BLUE**
  - `bg-sky-500/20 border-sky-500/40 hover:border-sky-400`
  - badge: `bg-sky-500`

**Altro pattern**:
- **Popular tier** → bordo `#2251ff` royal blue + bg `#2251ff/10`
- **Non-popular** → `bg-[#0a2540]` deep navy + bordo white 10%
- **Check icon prezzi** → `#22c55e` verde
- **Price contact** → `#2251ff` royal blue
- **WhatsApp CTA** → `#25D366` brand
- **Page background** → `#051C2C` darkest navy
- **Card background** → `#0a2540` mid navy

**Importante**: questa pagina NON è ancora in Palette D. È in Warm Depth / Navy. Il rebrand è pendente.

## 5. Dashboard Category Colors (`app/(workspace)/dashboard/page.tsx` L28-36)

La **fonte unica** dei miei `--hue-*` tokens, con valori esatti dal codice:

```ts
const CATEGORY_COLOR: Record<string, string> = {
  visas: '#4a8ec4',
  business: '#5cb88a',
  taxes: '#b89a40',         // ← NON #d4a853 (io avevo preso il token vecchio)
  property: '#9880d8',
  living: '#d4845a',         // ← copper, rebrand Palette D lo sostituirà con rosso
  emerging_trends: '#4ab8c4',
};
```

## 6. Dashboard Practice STATUS_CONFIG (`app/(workspace)/dashboard/page.tsx` L119-125)

Il mapping stato → colore nelle pipeline rows del dashboard:

| Stato | Label | dot hex |
|---|---|---|
| `inquiry` | Inquiry | `#9ca3af` grey |
| `quotation` | Quotation | `#b89a40` gold |
| `in_progress` | In Progress | `#4a8ec4` blu |
| `documents` | Documents | `#b89a40` gold |
| `completed` | Completed | `#5cb88a` green |

Qui usa il set **muted** (4a8ec4 vs kanban 3b82f6). Perché? Dashboard è ambient (vuoi vedere tanti record), kanban è decision-time (vuoi contrasto). **Context-aware palette**.

## 7. KBLI Risk Badges (`components/kbli/RiskBadge.tsx`)

```ts
parseRisk:
  tinggi           → "High"        → #ef4444 (red-500)
  menengah-tinggi  → "Medium-High" → #f59e0b (amber-500)
  menengah-rendah  → "Medium-Low"  → #3b82f6 (blue-500)
  rendah           → "Low"         → #22c55e (green-500)
```

**Rendering**: `color` + `borderColor: color + '33'` (20% opacity) + `backgroundColor: color + '15'` (8%) + dot 1.5px pieno.

## 8. KBLI PMA Badges (`components/kbli/PMABadge.tsx`)

CSS vars (definite in `apps/kbli-navigator/styles/kbli-theme.css`):
- `--kbli-pma-open` + `--kbli-pma-open-bg`
- `--kbli-pma-restricted` + `--kbli-pma-restricted-bg`
- `--kbli-pma-closed` + `--kbli-pma-closed-bg`

Con emoji ✅ / ⚠️ / 🚫 / ❓.

## 9. Service Pages Navy Palette (legacy, da sostituire)

Usata da `/services/[slug]`, `/services/visa`, ecc. Valori esatti:
- Page bg: `#051C2C`
- Card bg: `#0a2540`
- Accent popular: `#2251ff`
- Check icon: `#22c55e`

Questa palette va retirata quando il rebrand Palette D arriva alla pagina servizi. Nel draft la manteniamo **solo come fallback storico** e la sostituiamo con il sistema di seguito.

---

## SINTESI: Bali Zero ha 3 sistemi colore contestuali che coesistono

| Sistema | Intensità bg | Uso | Fonte |
|---|---|---|---|
| **Kanban Process** | 3.5–4% ultra sottile | Colonne kanban grandi, "panorama" | `kanban-colors.ts` |
| **Status Badge** | 12% piatto | Badge isolati, stati atomici | `StatusBadge.tsx` |
| **Risk Badge** | 15% bg + 33% border | Label con border, alta leggibilità | `RiskBadge.tsx` |

**Regola universale**: un colore semantico **è sempre tripartito** — un hex pieno (text/dot/border) + un bg tenue (3.5–15%) + un border medio (8–33%). Mai un hex solo.

**Gradient**: quando serve intensità (stripe, button), coppia **stessa famiglia tonale** start→end (orange-400 → orange-500, blue-500 → blue-600). Mai cross-hue (niente blu→viola).

## Grammatica semantica (stati del business)

Una pratica Bali Zero attraversa sempre questi stati. Il colore è la sua temperatura:

```
inquiry         grey    "appena arrivato, non classificato"
waiting_docs    orange  "bloccato sul cliente, azione sua"
sending_invoice yellow  "soldi in movimento, stato transitorio"
on_process      blue    "attivo ufficiale, nostro carico"
completed       green   "chiuso positivamente, archiviato"
expired/rejected red    "fallito, azione correttiva"
```

**Usare questa scala per ogni elemento che rappresenti STATO**:
- Pipeline rows → colore dello stato pratica
- Portal status cards → colore del sub-sistema (Immigration blu/on_process, Company verde/completed, Tax verde/completed)
- Pricing packages → colore del "target stato" del cliente (Essential grey = entry-level, Standard blu = on_process = "actively buying", Premium verde = completed = "goal tier")
- Intel grid badges → colore della categoria (visas blue, property purple, tax yellow/amber, business green, living red-copper)

## Grammatica decorativa (categorie di contenuto)

Quando NON rappresenti stato ma categoria editoriale, usa il set **muted** del dashboard:

```
visas            #4a8ec4  blue muted
business         #5cb88a  green muted
taxes            #b89a40  gold muted    ← NOT #d4a853
property         #9880d8  violet muted
living           #d4845a  copper        ← to be replaced by signal red in Palette D
emerging_trends  #4ab8c4  teal muted
```

Quando rappresenti stato, usa il set **bright** del kanban (`#3b82f6`, `#22c55e`, `#fb923c`, `#facc15`, `#9ca3af`).

---

## Azioni sul draft

1. **Rimpiazzare i miei `--hue-*`** con il set muted autentico (`#b89a40` non `#d4a853`).
2. **Aggiungere un set `--state-*`** per gli stati (grey/orange/yellow/blue/green bright).
3. **Applicare pipeline row coloring** al dashboard draft usando la logica kanban: ogni row ha `backgroundColor: tintBg` corrispondente al suo stato + borderLeft 2px con dotColor (non più solo una text pill colorata).
4. **Timeline portal** → riprodurre il ProcessStepper: circle verde completed / circle blu current + pulse / circle grigio pending con linea verticale condizionale.
5. **Pricing cards** → Essential grigio / Standard blu/on_process / Premium verde/completed (seguendo la grammatica stati come tier progression).
6. **Service cards home (marketing)** → Visa blu / PT PMA verde / Tax oro / Property viola (prendendo dal dashboard CATEGORY_COLOR invece del mio set arbitrario).
7. **Intel grid badges** → categoria con il muted set ufficiale.
8. **Portal status cards** → Immigration on_process blue (kanban #3b82f6) / Company completed green (#22c55e) / Tax completed green. Cambiare dagli hue generici.
9. **KBLI Risk Badge** → quando mostrerai PMA/Risk nelle kbli sector card, usa il formato `color + border/33 + bg/15 + dot`.
10. **Status badge atomici** → usare il set 12% piatto del Portal per badge isolati (es. "Urgent" label in dashboard).

Ogni scelta sopra è **tracciabile a un file del repo**, non inventata.
