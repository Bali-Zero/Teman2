# Client Portal UI - React Components

React/TypeScript components for displaying Tax & Visa data in client-facing portals.

## 📦 Components

### Tax Dashboard Components

- `TaxObligationsList` - Display list of tax obligations
- `TaxSummaryCard` - Summary card with metrics (upcoming, critical, overdue)
- `TaxObligationCard` - Individual tax obligation detail card

### Visa Dashboard Components

- `VisaStatusCard` - Active visa status card
- `VisaHistoryList` - Visa history timeline
- `VisaSummaryCard` - Summary card with expiry warnings

### Shared Components

- `TimelineEvent` - Timeline event display
- `StatusBadge` - Status indicator badge
- `UrgencyIndicator` - Visual urgency indicator

## 🚀 Installation

### Option 1: Copy Components Directly

Copy the components from `/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/portal-ui-components/` into your Next.js/React project.

### Option 2: Use in Existing Project

If using in `apps/zantara-media/dashboard`:

```bash
cd apps/zantara-media/dashboard
# Components are already compatible with your existing UI system
```

## 📋 Usage Examples

### Tax Dashboard

```tsx
import { TaxSummaryCard, TaxObligationsList } from "@/components/portal/tax";

export default function TaxDashboard() {
  return (
    <div className="space-y-6">
      <TaxSummaryCard clientId={123} />
      <TaxObligationsList clientId={123} />
    </div>
  );
}
```

### Visa Dashboard

```tsx
import { VisaStatusCard, VisaHistoryList } from "@/components/portal/visa";

export default function VisaDashboard() {
  return (
    <div className="space-y-6">
      <VisaStatusCard clientId={123} />
      <VisaHistoryList clientId={123} />
    </div>
  );
}
```

### Combined Portal Home

```tsx
import { TaxSummaryCard, TaxObligationsList } from "@/components/portal/tax";
import { VisaStatusCard, VisaSummaryCard } from "@/components/portal/visa";
import { TimelineEventsList } from "@/components/portal/timeline";

export default function PortalHome() {
  const clientId = 123; // From auth context

  return (
    <DashboardLayout title="My Portal">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <TaxSummaryCard clientId={clientId} />
        <VisaSummaryCard clientId={clientId} />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <VisaStatusCard clientId={clientId} />
          <TaxObligationsList clientId={clientId} limit={5} />
        </div>

        <TimelineEventsList clientId={clientId} />
      </div>
    </DashboardLayout>
  );
}
```

## 🎨 Component API

### TaxSummaryCard

```tsx
interface TaxSummaryCardProps {
  clientId: number;
  apiUrl?: string; // Default: process.env.NEXT_PUBLIC_API_URL
}
```

**Features:**

- Shows total obligations, total amount, upcoming/critical/overdue counts
- Auto-refreshes every 5 minutes
- Loading skeleton
- Error handling

---

### TaxObligationsList

```tsx
interface TaxObligationsListProps {
  clientId: number;
  limit?: number; // Default: all
  status?: string[]; // Filter by status
  apiUrl?: string;
}
```

**Features:**

- Paginated list of obligations
- Color-coded urgency (red for critical, yellow for warning, green for safe)
- Status badges (pending, paid, filed, overdue)
- Amount formatting (Rp)
- Due date display with relative time

---

### VisaStatusCard

```tsx
interface VisaStatusCardProps {
  clientId: number;
  apiUrl?: string;
}
```

**Features:**

- Shows active visa details
- Expiry countdown
- Status indicator (active, expiring_soon, expired)
- Sponsor information
- Renewal CTA button

---

### VisaHistoryList

```tsx
interface VisaHistoryListProps {
  clientId: number;
  limit?: number;
  apiUrl?: string;
}
```

**Features:**

- Timeline of all visas
- Status progression
- Date ranges
- Document links (if available)

---

### TimelineEventsList

```tsx
interface TimelineEventsListProps {
  clientId: number;
  limit?: number;
  eventTypes?: string[]; // Filter by type
  apiUrl?: string;
}
```

**Features:**

- Chronological timeline
- Event type icons (practice_created, reminder, status_change, etc.)
- Color-coded by importance
- Client-visible only

## 🔐 Authentication

All components use JWT authentication via Authorization header:

```tsx
// In your API client
const token = localStorage.getItem("portal_jwt");

fetch(`${API_URL}/api/portal/taxes`, {
  headers: {
    Authorization: `Bearer ${token}`,
  },
});
```

## 🎨 Styling

Components use CSS variables for theming (compatible with `zantara-media/dashboard` theme):

```css
:root {
  --foreground: #1a1a1a;
  --background: #ffffff;
  --accent: #0066cc;
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  --border: #e5e7eb;
}
```

## 📱 Responsive Design

All components are mobile-first and responsive:

- Mobile: Single column layout
- Tablet: 2-column grid
- Desktop: Multi-column with sidebar

## ♿ Accessibility

- Semantic HTML
- ARIA labels
- Keyboard navigation
- Screen reader support
- High contrast mode

## 🧪 Testing

```bash
# Unit tests
npm test components/portal

# E2E tests
npm run test:e2e portal-ui
```

## 📈 Performance

- **Lazy loading** for lists
- **Skeleton loaders** during fetch
- **Memoization** for expensive computations
- **Virtual scrolling** for large lists
- **SWR caching** for API calls

## 🔄 Data Refresh

- **Automatic**: Every 5 minutes via `useSWR`
- **Manual**: Pull-to-refresh on mobile
- **Real-time**: WebSocket support (optional)

## 🌐 Internationalization

Components support i18n via `next-intl`:

```tsx
import { useTranslations } from "next-intl";

const t = useTranslations("Portal");
<h2>{t("tax.title")}</h2>;
```

## 📊 Analytics

Track user interactions:

```tsx
// components/portal/analytics.ts
export const trackPortalView = (page: string) => {
  analytics.track("portal_view", { page });
};

export const trackCTAClick = (action: string) => {
  analytics.track("portal_cta", { action });
};
```

## 🚀 Deployment

### Standalone Portal App

```bash
# Create new Next.js app
npx create-next-app@latest portal-client
cd portal-client

# Copy components
cp -r ../backend-rag/portal-ui-components/* ./src/components/portal/

# Install dependencies
npm install swr date-fns lucide-react

# Configure API URL
echo "NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev" > .env.local

# Run
npm run dev
```

### Integration into Existing Dashboard

```bash
# In apps/zantara-media/dashboard
mkdir -p src/components/portal
cp -r ../../backend-rag/portal-ui-components/* ./src/components/portal/

# Add to navigation
# Edit src/components/layout/Sidebar.tsx
```

## 📚 File Structure

```
portal-ui-components/
├── tax/
│   ├── TaxSummaryCard.tsx
│   ├── TaxObligationsList.tsx
│   ├── TaxObligationCard.tsx
│   └── index.ts
├── visa/
│   ├── VisaStatusCard.tsx
│   ├── VisaHistoryList.tsx
│   ├── VisaSummaryCard.tsx
│   └── index.ts
├── timeline/
│   ├── TimelineEventsList.tsx
│   ├── TimelineEvent.tsx
│   └── index.ts
├── shared/
│   ├── StatusBadge.tsx
│   ├── UrgencyIndicator.tsx
│   ├── LoadingSkeleton.tsx
│   └── index.ts
├── hooks/
│   ├── usePortalAuth.ts
│   ├── useTaxData.ts
│   ├── useVisaData.ts
│   └── useTimelineData.ts
├── lib/
│   ├── api-client.ts
│   ├── formatters.ts
│   └── types.ts
└── README.md (this file)
```

## 🔧 Configuration

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
NEXT_PUBLIC_PORTAL_TITLE="Bali Zero Client Portal"
NEXT_PUBLIC_SUPPORT_EMAIL="support@balizero.com"
```

## 🐛 Troubleshooting

### CORS Issues

```bash
# Backend must allow portal origin
ALLOWED_ORIGINS=https://portal.balizero.com
```

### Authentication Errors

```bash
# Check JWT token validity
# Token must have 'client_id' claim
```

### Data Not Loading

```bash
# Verify API endpoints are accessible
curl -H "Authorization: Bearer $TOKEN" $API_URL/api/portal/taxes
```

## 📞 Support

- **Documentation**: `/docs/PORTAL_UI_GUIDE.md`
- **API Docs**: `$API_URL/docs`
- **Issues**: GitHub Issues
- **Email**: dev@balizero.com

## 📝 License

Proprietary - Bali Zero © 2026
