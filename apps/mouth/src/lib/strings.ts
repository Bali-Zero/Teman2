/**
 * Operator UI chrome strings — kita workspace.
 *
 * ONE UI language for operator-facing chrome: ENGLISH
 * (kita UI/UX audit 2026-06-11, finding P1.3 — mixed EN/IT microcopy).
 *
 * Keep operator-facing literals that risk language drift here so the whole
 * surface stays greppable from a single file. This is NOT an i18n framework:
 * client-facing pages (blog / portal / marketing) use `@/i18n` and stay
 * multilingual by design — do not move their copy here.
 */
export const STRINGS = {
  common: {
    loading: "Loading…",
    loadingMap: "Loading map…",
    errorPrefix: "Error",
    noData: "No data available.",
  },
  articleComposer: {
    titlePlaceholder: "e.g. New KITAS Rules...",
    contentPlaceholder: "Paste raw content...",
  },
  dashboard: {
    collectedSub: (amount: string) => `${amount} collected`,
    outstandingSub: "to collect",
    clientsLabel: "Clients",
    clientsSub: "registered",
    casesLabel: "Cases",
    casesSub: (active: number, critical: number) =>
      `${active} active · ${critical} critical`,
    invoicesLabel: "Invoices",
    invoicesPendingSub: "pending",
    invoicesPaidSub: "all paid",
  },
  funnel: {
    totalSessionsLabel: "Total sessions",
    conversionsLabel: "Conversions",
    conversionRateLabel: "Conversion rate",
    chartTitle: "Sessions vs conversions per funnel",
  },
  oracle: {
    header: "🔮 Ask the Oracle",
    promptSummarizeProfile: "Summarize the full profile",
    promptVisaStatus: "Visa status and deadlines",
    promptTaxLkpm: "Tax and LKPM situation",
    promptMissingDocs: "Missing or expiring documents",
    inputPlaceholder: "Ask a question about this client…",
    sendTitle: "Send question",
    consulting: "Consulting the Oracle…",
    requestError: "Request failed",
    sourcesLabel: "Sources",
  },
} as const;
