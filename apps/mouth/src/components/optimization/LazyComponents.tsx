/**
 * Lazy Loaded Components
 *
 * Use these for heavy components that don't need to be in the initial bundle.
 * Reduces initial load time by splitting code into separate chunks.
 */

import React, { Suspense } from 'react';

// Loading fallback component
const LoadingFallback = ({ height = '400px' }: { height?: string }) => (
  <div
    className="flex items-center justify-center bg-muted/20 rounded-lg animate-pulse"
    style={{ height }}
  >
    <div className="text-muted-foreground">Loading...</div>
  </div>
);

// Dynamic imports for heavy components
const DynamicChartComponents = {
  // Charts are heavy - lazy load them
  BarChart: React.lazy(() => import('@nivo/bar').then((m) => ({ default: m.ResponsiveBar }))),
  LineChart: React.lazy(() => import('@nivo/line').then((m) => ({ default: m.ResponsiveLine }))),
  PieChart: React.lazy(() => import('@nivo/pie').then((m) => ({ default: m.ResponsivePie }))),
};

interface LazyChartProps {
  type: 'bar' | 'line' | 'pie';
  data: any;
  height?: string;
}

/**
 * Lazy Loaded Chart Component
 * Loads chart library only when needed
 */
export function LazyChart({ type, data, height = '400px' }: LazyChartProps) {
  const ChartComponent =
    DynamicChartComponents[
      type === 'bar' ? 'BarChart' : type === 'line' ? 'LineChart' : 'PieChart'
    ];

  return (
    <Suspense fallback={<LoadingFallback height={height} />}>
      <div style={{ height }}>
        <ChartComponent data={data} />
      </div>
    </Suspense>
  );
}

// Placeholder for lazy loaded components
// Add your heavy components here as needed
const DynamicUIComponents = {
  // Example: RichTextEditor: React.lazy(() => import('@/components/ui/editor')),
};

// Add your lazy component wrappers here when needed

// Page-level lazy loading helper
interface LazyPageProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Lazy Page Wrapper
 * Wrap page components for automatic code splitting
 *
 * Usage:
 * const LazySettingsPage = React.lazy(() => import('./settings/page'));
 *
 * <LazyPage>
 *   <LazySettingsPage />
 * </LazyPage>
 */
export function LazyPage({ children, fallback }: LazyPageProps) {
  return (
    <Suspense
      fallback={
        fallback || (
          <div className="flex items-center justify-center min-h-[50vh]">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        )
      }
    >
      {children}
    </Suspense>
  );
}

// Export pre-configured lazy imports for common patterns
export const lazyImports = {
  // Intelligence features - heavy components
  IntelligenceCenter: React.lazy(() => import('@/app/(workspace)/intelligence/page')),
  NewsRoom: React.lazy(() => import('@/app/(workspace)/intelligence/news-room/page')),
  ArticleComposer: React.lazy(() => import('@/app/(workspace)/intelligence/article-composer/page')),

  // Settings - less frequently accessed
  Settings: React.lazy(() => import('@/app/(workspace)/settings/page')),

  // Client management
  ClientDetail: React.lazy(() => import('@/app/(workspace)/clients/[id]/page')),
  ClientNew: React.lazy(() => import('@/app/(workspace)/clients/new/page')),
};

// Preload helper for predictive loading
export const preloadComponent = <T extends React.ComponentType<any>>(
  factory: () => Promise<{ default: T }>
) => {
  const Component = React.lazy(factory);
  // Start loading immediately but don't block
  factory();
  return Component;
};
