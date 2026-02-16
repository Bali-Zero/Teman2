#!/usr/bin/env tsx
/**
 * Type Safety Check Script
 * Scans codebase for `any` usage and generates report
 *
 * Usage: npm run type-safety:check
 */

import { execSync } from "child_process";
import { readFileSync, readdirSync } from "fs";
import { join } from "path";

interface AnyUsage {
  file: string;
  line: number;
  content: string;
  isTest: boolean;
}

/**
 * Scan file for `any` usage
 */
function scanFile(filePath: string): AnyUsage[] {
  const content = readFileSync(filePath, "utf-8");
  const lines = content.split("\n");
  const usages: AnyUsage[] = [];

  lines.forEach((line, index) => {
    // Match `: any` or `as any` patterns
    const anyPattern = /:\s*any\b|as\s+any\b/g;
    const matches = line.match(anyPattern);

    if (matches) {
      const isTest =
        filePath.includes(".test.") ||
        filePath.includes(".spec.") ||
        filePath.includes("__tests__");
      usages.push({
        file: filePath,
        line: index + 1,
        content: line.trim(),
        isTest,
      });
    }
  });

  return usages;
}

/**
 * Recursively scan directory
 */
function scanDirectory(
  dir: string,
  extensions: string[] = [".ts", ".tsx"],
): AnyUsage[] {
  const usages: AnyUsage[] = [];

  try {
    const entries = readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = join(dir, entry.name);

      // Skip node_modules, .next, etc.
      if (entry.name.startsWith(".") || entry.name === "node_modules") {
        continue;
      }

      if (entry.isDirectory()) {
        usages.push(...scanDirectory(fullPath, extensions));
      } else if (
        entry.isFile() &&
        extensions.some((ext) => entry.name.endsWith(ext))
      ) {
        usages.push(...scanFile(fullPath));
      }
    }
  } catch (error) {
    // Skip directories we can't read
  }

  return usages;
}

/**
 * Generate report
 */
function generateReport(usages: AnyUsage[]): void {
  const productionUsages = usages.filter((u) => !u.isTest);
  const testUsages = usages.filter((u) => u.isTest);

  const byFile = new Map<string, number>();
  productionUsages.forEach((u) => {
    byFile.set(u.file, (byFile.get(u.file) || 0) + 1);
  });

  const topFiles = Array.from(byFile.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  console.log("\n📊 TYPE SAFETY REPORT\n");
  console.log(`Total 'any' usage: ${usages.length}`);
  console.log(`  Production: ${productionUsages.length}`);
  console.log(`  Tests: ${testUsages.length}`);
  console.log(`\nTop 10 files with 'any':`);
  topFiles.forEach(([file, count], index) => {
    console.log(`  ${index + 1}. ${file}: ${count}`);
  });

  console.log(
    `\n✅ Type Safety Score: ${Math.max(0, 100 - productionUsages.length * 2)}%`,
  );
}

/**
 * Main
 */
function main() {
  const srcDir = join(process.cwd(), "src");
  console.log("🔍 Scanning for `any` usage...");

  const usages = scanDirectory(srcDir);
  generateReport(usages);

  // Exit with error if too many `any` in production
  const productionCount = usages.filter((u) => !u.isTest).length;
  if (productionCount > 20) {
    console.log(
      `\n⚠️  Warning: ${productionCount} 'any' types found in production code`,
    );
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}
