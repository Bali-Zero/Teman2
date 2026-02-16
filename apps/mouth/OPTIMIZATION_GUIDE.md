# Frontend Optimization Guide

## 📦 Optimization Components

### React.memo Components

Use these for frequently rendered lists to prevent unnecessary re-renders:

```tsx
import { MemoCard, MemoListItem, MemoBadge } from "@/components/optimization";

// In a list - prevents all items from re-rendering
{
  items.map((item) => (
    <MemoListItem
      key={item.id}
      id={item.id}
      title={item.title}
      onClick={handleClick}
    />
  ));
}
```

### Lazy Loading

Load heavy components only when needed:

```tsx
import { LazyChart, LazyPage } from '@/components/optimization';

// Charts are loaded only when rendered
<LazyChart type="bar" data={chartData} height="400px" />

// Wrap page components
<LazyPage>
  <SomeHeavyPageComponent />
</LazyPage>
```

### Image Optimization

Use OptimizedImage for all images:

```tsx
import { OptimizedImage, ResponsiveImage, OptimizedAvatar } from '@/components/optimization';

// Basic optimized image
<OptimizedImage
  src="/photo.jpg"
  alt="Description"
  width={800}
  height={600}
  priority={false} // Set true for above-fold images
/>

// Responsive with aspect ratio
<ResponsiveImage
  src="/banner.jpg"
  alt="Banner"
  aspectRatio="16/9"
  maxWidth={1200}
/>

// User avatar
<OptimizedAvatar
  src={user.avatar}
  alt={user.name}
  size="md"
/>
```

### Accessibility

Built-in accessible components:

```tsx
import { SkipLink, FormField, AccessibleButton } from '@/components/optimization';

// Skip navigation for keyboard users
<SkipLink href="#main-content">Skip to main content</SkipLink>

// Accessible form field with error handling
<FormField
  id="email"
  label="Email Address"
  error={errors.email}
  hint="We'll never share your email"
  required
>
  <input type="email" className="input" />
</FormField>

// Button with loading state announced to screen readers
<AccessibleButton
  isLoading={isSubmitting}
  loadingText="Saving changes..."
  onClick={handleSave}
>
  Save
</AccessibleButton>
```

### API Caching

Automatic caching for API calls:

```tsx
import { useCachedQuery, fetchWithCache } from "@/components/optimization";

// In components - automatic caching
const { data, error, isLoading, refetch } = useCachedQuery({
  key: "user-profile",
  fetcher: () => fetch("/api/user").then((r) => r.json()),
  ttl: 60000, // 1 minute cache
});

// Direct usage
const data = await fetchWithCache({
  key: "settings",
  fetcher: () => fetchSettings(),
  ttl: 300000, // 5 minutes
  staleWhileRevalidate: true,
});
```

## 🚀 Performance Tips

### 1. Use React.memo for List Items

Always wrap list items with React.memo to prevent cascade re-renders.

### 2. Lazy Load Heavy Components

Charts, editors, and complex UIs should be lazy loaded.

### 3. Optimize Images

- Use WebP/AVIF formats
- Provide width/height to prevent CLS
- Use `priority` for above-fold images
- Lazy load below-fold images

### 4. Cache API Responses

Use `useCachedQuery` for data that doesn't change frequently.

### 5. Code Splitting

The app uses Next.js automatic code splitting. For manual splitting:

```tsx
const HeavyComponent = React.lazy(() => import("./HeavyComponent"));
```

## 📊 Monitoring

### Bundle Analysis

```bash
ANALYZE=true npm run build
```

### Cache Metrics

```bash
# In browser console
__API_CACHE__.getStats()
```

## 🔧 Next.js Optimizations

The following optimizations are configured in `next.config.ts`:

- `swcMinify: true` - Faster minification
- `optimizePackageImports` - Tree shaking for heavy packages
- Image optimization with AVIF/WebP
- Standalone output for Docker

## ♿ Accessibility Checklist

- [ ] All images have alt text
- [ ] Forms have proper labels
- [ ] Color contrast meets WCAG 2.1 AA
- [ ] Keyboard navigation works
- [ ] Focus indicators are visible
- [ ] Skip links are present
- [ ] ARIA labels where needed

## 📈 Performance Targets

- First Contentful Paint: < 1.8s
- Largest Contentful Paint: < 2.5s
- Time to Interactive: < 3.8s
- Cumulative Layout Shift: < 0.1
