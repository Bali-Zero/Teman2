/**
 * Type Safety Metrics
 * Tracks type safety improvements and `any` usage across the codebase
 */

import { logger } from "@/lib/logger";
import type { Metadata } from "@/lib/types/common";

export interface TypeSafetyMetrics {
  totalAnyCount: number;
  criticalAnyCount: number;
  nonCriticalAnyCount: number;
  typeGuardsCount: number;
  typedFilesCount: number;
  migrationProgress: number; // 0-100
  lastUpdated: string;
}

class TypeSafetyMetricsTracker {
  private metrics: TypeSafetyMetrics = {
    totalAnyCount: 0,
    criticalAnyCount: 0,
    nonCriticalAnyCount: 0,
    typeGuardsCount: 0,
    typedFilesCount: 0,
    migrationProgress: 0,
    lastUpdated: new Date().toISOString(),
  };

  /**
   * Track type safety improvement
   */
  trackImprovement(before: number, after: number, file: string): void {
    const reduction = before - after;
    const percentage = before > 0 ? (reduction / before) * 100 : 0;

    logger.info("Type safety improvement tracked", {
      component: "TypeSafetyMetrics",
      action: "track_improvement",
      metadata: {
        file,
        before,
        after,
        reduction,
        percentage: percentage.toFixed(2),
      },
    });

    this.updateMetrics();
  }

  /**
   * Track type guard creation
   */
  trackTypeGuard(name: string, file: string): void {
    this.metrics.typeGuardsCount++;
    logger.debug("Type guard created", {
      component: "TypeSafetyMetrics",
      action: "type_guard_created",
      metadata: { name, file },
    });
  }

  /**
   * Track file typing completion
   */
  trackFileTyped(file: string, anyRemoved: number): void {
    this.metrics.typedFilesCount++;
    this.metrics.totalAnyCount -= anyRemoved;
    logger.info("File typing completed", {
      component: "TypeSafetyMetrics",
      action: "file_typed",
      metadata: { file, anyRemoved },
    });
    this.updateMetrics();
  }

  /**
   * Get current metrics
   */
  getMetrics(): TypeSafetyMetrics {
    return { ...this.metrics };
  }

  /**
   * Update migration progress
   */
  private updateMetrics(): void {
    // Calculate progress based on files typed and any removed
    // This is a simplified calculation - adjust based on your migration plan
    const targetFiles = 10; // Adjust based on your migration plan
    const progress = Math.min(
      100,
      (this.metrics.typedFilesCount / targetFiles) * 100,
    );
    this.metrics.migrationProgress = progress;
    this.metrics.lastUpdated = new Date().toISOString();
  }

  /**
   * Log metrics summary
   */
  logSummary(): void {
    logger.info("Type safety metrics summary", {
      component: "TypeSafetyMetrics",
      action: "summary",
      metadata: this.metrics as unknown as Metadata,
    });
  }
}

export const typeSafetyMetrics = new TypeSafetyMetricsTracker();
