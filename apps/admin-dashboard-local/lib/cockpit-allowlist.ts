/**
 * Hardcoded allowlist of 35 agentic cron labels (LLM-using).
 * Source: ~/.claude/agents/*.md + agent-library/01-inventory.md.
 * Why hardcoded: panel finding 4-LLM — no dynamic discovery for security.
 */
export const AGENTIC_CRON_ALLOWLIST: readonly string[] = Object.freeze([
  "com.balizero.regulatory-watcher",
  "com.balizero.intel.nightly",
  "com.balizero.intel-lake-router.5min",
  "com.balizero.intel-lake-nb-pusher.15min",
  "com.balizero.intel-lake.outbox-drain.minute",
  "com.balizero.intel-lake.shadow-validate.6h",
  "com.balizero.intel-radar-daily-digest",
  "com.balizero.intel-dedup-gateway",
  "com.balizero.wr2.draft-generator",
  "com.balizero.wr2.fact-checker",
  "com.balizero.wr2.fact-extractor",
  "com.balizero.wr2.image-generator",
  "com.balizero.wr2.canva-renderer",
  "com.balizero.wr2.canva-apply",
  "com.balizero.wr2.canva-gc.weekly",
  "com.balizero.wr2.connector",
  "com.balizero.wr2.dossier-compiler",
  "com.balizero.wr2.measurer",
  "com.balizero.wr2.daily-metrics",
  "com.balizero.wr2.sla-worker",
  "com.balizero.wr2.trend-hunter",
  "com.balizero.wr2.voyager.weekly",
  "com.balizero.wr2.reflexion.weekly",
  "com.balizero.wr2.external-bench.monthly",
  "com.balizero.wr2.ig-metrics-analyst.weekly",
  "com.balizero.wr2.hardening",
  "com.balizero.wr2.queue-server",
  "com.balizero.bali-intel-scraper.daily",
  "com.balizero.competitor-monitor.monthly",
  "com.balizero.email-template-builder",
  "com.balizero.yield-optimizer.weekly",
  "com.matagaruda.bridge.adaptive",
  "com.matagaruda.gap.consumer",
  "com.matagaruda.invalidation-sweep",
  "com.balizero.meta-dispatcher",
]) as readonly string[];

export function isAgenticCronLabel(label: string | null | undefined): boolean {
  if (!label || typeof label !== "string") return false;
  return (AGENTIC_CRON_ALLOWLIST as readonly string[]).includes(label);
}
