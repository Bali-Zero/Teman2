/**
 * Type Safety Monitor
 * Continuous monitoring and reporting for type safety metrics
 */

import { logger } from "@/lib/logger";
import type { Metadata } from "@/lib/types/common";
import { typeSafetyMetrics } from "@/lib/metrics/type-safety-metrics";
import { logTypeSafety } from "./type-safety-logger";

/**
 * Scan codebase for `any` usage
 * This is a simplified version - in production, use a proper AST parser
 */
export async function scanAnyUsage(): Promise<{
  total: number;
  byFile: Array<{ file: string; count: number }>;
  critical: number;
  nonCritical: number;
}> {
  // In a real implementation, this would use TypeScript compiler API
  // or a tool like eslint-plugin-typescript
  // For now, return current metrics
  const metrics = typeSafetyMetrics.getMetrics();

  return {
    total: metrics.totalAnyCount,
    byFile: [],
    critical: metrics.criticalAnyCount,
    nonCritical: metrics.nonCriticalAnyCount,
  };
}

/**
 * Monitor type safety metrics over time
 */
export class TypeSafetyMonitor {
  private checkInterval: NodeJS.Timeout | null = null;
  private lastMetrics: ReturnType<typeof typeSafetyMetrics.getMetrics> | null =
    null;

  /**
   * Start monitoring type safety metrics
   */
  start(intervalMs: number = 24 * 60 * 60 * 1000): void {
    // Check daily by default
    if (this.checkInterval) {
      this.stop();
    }

    this.checkInterval = setInterval(() => {
      this.checkMetrics();
    }, intervalMs);

    // Initial check
    this.checkMetrics();
  }

  /**
   * Stop monitoring
   */
  stop(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }

  /**
   * Check metrics and log changes
   */
  private checkMetrics(): void {
    const currentMetrics = typeSafetyMetrics.getMetrics();

    if (this.lastMetrics) {
      const anyDelta =
        currentMetrics.totalAnyCount - this.lastMetrics.totalAnyCount;
      const progressDelta =
        currentMetrics.migrationProgress - this.lastMetrics.migrationProgress;

      if (anyDelta !== 0 || progressDelta !== 0) {
        logger.info("Type safety metrics changed", {
          component: "TypeSafetyMonitor",
          action: "metrics_change",
          metadata: {
            anyDelta,
            progressDelta,
            current: currentMetrics as unknown as Metadata,
            previous: this.lastMetrics as unknown as Metadata,
          } as Metadata,
        });

        // Alert if `any` count increased
        if (anyDelta > 0) {
          logger.warn("Type safety regression detected", {
            component: "TypeSafetyMonitor",
            action: "regression_detected",
            metadata: {
              anyIncrease: anyDelta,
              currentTotal: currentMetrics.totalAnyCount,
            },
          });
        }
      }
    }

    this.lastMetrics = currentMetrics;
  }

  /**
   * Generate type safety report
   */
  generateReport(): {
    metrics: ReturnType<typeof typeSafetyMetrics.getMetrics>;
    recommendations: string[];
  } {
    const metrics = typeSafetyMetrics.getMetrics();
    const recommendations: string[] = [];

    if (metrics.totalAnyCount > 10) {
      recommendations.push(
        `Consider reducing ${metrics.totalAnyCount - 10} more 'any' types`,
      );
    }

    if (metrics.criticalAnyCount > 0) {
      recommendations.push(
        `Remove ${metrics.criticalAnyCount} 'any' types from critical code paths`,
      );
    }

    if (metrics.migrationProgress < 90) {
      recommendations.push(
        `Continue migration: ${metrics.migrationProgress.toFixed(1)}% complete`,
      );
    }

    if (metrics.typeGuardsCount < 5) {
      recommendations.push("Add more type guards for runtime type safety");
    }

    return {
      metrics,
      recommendations,
    };
  }
}

export const typeSafetyMonitor = new TypeSafetyMonitor();
