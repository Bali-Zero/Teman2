"use client";

import { useState } from "react";
import { RiskBadge } from "./RiskBadge";
import type {
  KBLICode,
  KBLIGoldContent,
  KBLILicenseByScale,
  KBLIPmaInfo,
} from "@/lib/kbli-types";
import ReactMarkdown from "react-markdown";

// =============================================================================
// Types
// =============================================================================

interface LicensingSectionProps {
  kbli: KBLICode;
  gold: KBLIGoldContent | null;
}

// =============================================================================
// Helpers
// =============================================================================

const RISK_EN: Record<string, string> = {
  Rendah: "Low",
  "Menengah Rendah": "Medium-Low",
  "Menengah Tinggi": "Medium-High",
  Tinggi: "High",
};

function riskEn(id: string): string {
  return RISK_EN[id] ?? id;
}

/** Section type determines visual treatment */
type SectionType = "obligations" | "authority" | "pma" | "note" | "default";

function detectSectionType(title: string): SectionType {
  const t = title.toLowerCase();
  if (
    t.includes("obligation") ||
    t.includes("key obligation") ||
    t.includes("before you start")
  )
    return "obligations";
  if (t.includes("authority")) return "authority";
  if (t === "pma" || t.includes("pma status") || t.includes("foreign"))
    return "pma";
  if (t.includes("note") || t.includes("important")) return "note";
  return "default";
}

/** Rename obscure section titles to reader-friendly versions */
function humanizeTitle(title: string): string {
  const t = title.toLowerCase();
  if (t === "key obligations" || t === "key obligation")
    return "Before You Start";
  if (t === "authority chain") return "Who Approves What";
  return title;
}

/** Parse whatYouNeed markdown into structured sections */
function parseWhatYouNeed(markdown: string) {
  let alert: string | null = null;
  let source: string | null = null;

  // Extract alert block
  const alertPatterns = [
    /\n\*\*⚠️[^*]*\*\*[\s\S]*?(?=\n\*\*Source Regulation|\n\*\*Note on GR|$)/,
    /\n\*\*⚠️[^*]*\*\*:[\s\S]*?(?=\n\*\*Source|$)/,
  ];
  let rest = markdown;
  for (const pattern of alertPatterns) {
    const match = rest.match(pattern);
    if (match) {
      alert = match[0].trim();
      rest = rest.replace(match[0], "").trim();
      break;
    }
  }

  // Extract source regulation
  const srcPattern = /\*\*Source Regulation:\*\*[^\n]*/;
  const srcMatch = rest.match(srcPattern);
  if (srcMatch) {
    source = srcMatch[0]
      .replace(/\*\*/g, "")
      .replace("Source Regulation:", "")
      .trim();
    rest = rest.replace(srcMatch[0], "").trim();
  }

  // Parse `rest` into individual sections by splitting on bold headers
  const sections: { title: string; body: string }[] = [];
  const lines = rest.split("\n");
  let currentTitle = "";
  let currentBody: string[] = [];

  for (const line of lines) {
    const headerMatch = line.match(/^\*\*([^*]+?):\*\*\s*(.*)/);
    if (headerMatch) {
      if (currentTitle || currentBody.length > 0) {
        sections.push({
          title: currentTitle,
          body: currentBody.join("\n").trim(),
        });
      }
      currentTitle = headerMatch[1].trim();
      currentBody = headerMatch[2] ? [headerMatch[2]] : [];
    } else {
      currentBody.push(line);
    }
  }
  if (currentTitle || currentBody.length > 0) {
    sections.push({ title: currentTitle, body: currentBody.join("\n").trim() });
  }

  return { sections, alert, source };
}

// =============================================================================
// Section color config
// =============================================================================

const SECTION_STYLES: Record<
  SectionType,
  {
    accentColor: string;
    iconBg: string;
    iconColor: string;
    topBorder: string;
  }
> = {
  obligations: {
    accentColor: "var(--kbli-accent)",
    iconBg: "rgba(212, 132, 90, 0.1)",
    iconColor: "var(--kbli-accent)",
    topBorder: "var(--kbli-accent)",
  },
  authority: {
    accentColor: "var(--kbli-accent2)",
    iconBg: "rgba(139, 156, 247, 0.1)",
    iconColor: "var(--kbli-accent2)",
    topBorder: "var(--kbli-accent2)",
  },
  pma: {
    accentColor: "var(--kbli-pma-open)",
    iconBg: "rgba(94, 196, 144, 0.1)",
    iconColor: "var(--kbli-pma-open)",
    topBorder: "var(--kbli-pma-open)",
  },
  note: {
    accentColor: "var(--kbli-amber)",
    iconBg: "rgba(232, 168, 73, 0.1)",
    iconColor: "var(--kbli-amber)",
    topBorder: "var(--kbli-amber)",
  },
  default: {
    accentColor: "var(--kbli-accent)",
    iconBg: "rgba(212, 132, 90, 0.08)",
    iconColor: "var(--kbli-accent)",
    topBorder: "var(--kbli-border)",
  },
};

// =============================================================================
// Sub-components
// =============================================================================

/** Key Facts at a Glance — horizontal stats grid */
function KeyFacts({
  licensing,
  pma,
}: {
  licensing: KBLILicenseByScale[];
  pma: KBLIPmaInfo;
}) {
  const primary = licensing[0];
  if (!primary) return null;

  const facts: { label: string; value: string; accent?: string }[] = [
    {
      label: "Risk Level",
      value: `${riskEn(primary.riskCategory)} (${primary.riskCategory})`,
    },
    {
      label: "License Type",
      value: primary.licenseType,
    },
    {
      label: "Processing",
      value: primary.timeframe || "Not specified",
      accent: primary.timeframe?.toLowerCase().includes("otomatis")
        ? "var(--kbli-pma-open)"
        : undefined,
    },
    {
      label: "Foreign Ownership",
      value:
        pma.status === "open"
          ? "100% Open"
          : pma.status === "restricted"
            ? `Max ${pma.maxForeign}%`
            : "Closed (0%)",
      accent:
        pma.status === "open"
          ? "var(--kbli-pma-open)"
          : pma.status === "restricted"
            ? "var(--kbli-pma-restricted)"
            : "var(--kbli-pma-closed)",
    },
    {
      label: "Authority",
      value: "BKPM / OSS",
    },
  ];

  return (
    <div
      className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-[var(--border)] sm:grid-cols-3 lg:grid-cols-5"
      style={{ background: "var(--kbli-border)" }}
    >
      {facts.map((f) => (
        <div
          key={f.label}
          className="flex flex-col gap-1.5 px-4 py-3.5"
          style={{ background: "var(--kbli-bg-elevated)" }}
        >
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--foreground-muted)]">
            {f.label}
          </span>
          <span
            className="text-sm font-semibold"
            style={{ color: f.accent ?? "var(--foreground)" }}
          >
            {f.value}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Tier Tabs for multi-scale licensing */
function TierTabs({
  tiers,
  activeTier,
  onSelect,
}: {
  tiers: KBLILicenseByScale[];
  activeTier: number;
  onSelect: (i: number) => void;
}) {
  if (tiers.length <= 1) return null;

  return (
    <div
      className="flex gap-1 rounded-lg p-1"
      style={{ background: "rgba(255,255,255,0.04)" }}
    >
      {tiers.map((tier, i) => (
        <button
          key={i}
          onClick={() => onSelect(i)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
            activeTier === i
              ? "bg-[var(--kbli-bg-surface)] text-[var(--foreground)] shadow-sm"
              : "text-[var(--foreground-muted)] hover:text-[var(--foreground-secondary)]"
          }`}
        >
          {tier.scales.join(" + ")}
        </button>
      ))}
    </div>
  );
}

/** Tier Detail — collapsible raw PP28 data */
function TierDetail({ tier }: { tier: KBLILicenseByScale }) {
  return (
    <div className="space-y-3">
      {tier.requirements.length > 0 && (
        <details className="group rounded-lg border border-[var(--border)] overflow-hidden">
          <summary
            className="flex cursor-pointer items-center gap-3 px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-[var(--foreground-muted)] transition-colors hover:text-[var(--foreground-secondary)]"
            style={{ background: "var(--kbli-bg-elevated)" }}
          >
            <span>Requirements (Indonesian)</span>
            <span className="ml-auto rounded-full border border-[var(--border)] px-2 py-0.5 text-[10px] font-medium">
              {tier.requirements.length}
            </span>
          </summary>
          <div
            className="space-y-2 p-4"
            style={{ background: "var(--kbli-bg-surface)" }}
          >
            {tier.requirements.map((req, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-lg border border-[var(--border)] px-3.5 py-2.5"
                style={{ background: "var(--kbli-bg-elevated)" }}
              >
                <span
                  className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded text-[10px] font-bold"
                  style={{
                    background: "rgba(212, 132, 90, 0.1)",
                    color: "var(--kbli-accent)",
                  }}
                >
                  {i + 1}
                </span>
                <span className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
                  {req}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}

      {tier.obligations.length > 0 && (
        <details className="group rounded-lg border border-[var(--border)] overflow-hidden">
          <summary
            className="flex cursor-pointer items-center gap-3 px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-[var(--foreground-muted)] transition-colors hover:text-[var(--foreground-secondary)]"
            style={{ background: "var(--kbli-bg-elevated)" }}
          >
            <span>Post-License Obligations</span>
            <span className="ml-auto rounded-full border border-[var(--border)] px-2 py-0.5 text-[10px] font-medium">
              {tier.obligations.length}
            </span>
          </summary>
          <div
            className="space-y-1.5 p-4"
            style={{ background: "var(--kbli-bg-surface)" }}
          >
            {tier.obligations.map((obl, i) => (
              <div
                key={i}
                className="flex items-start gap-2.5 rounded-lg px-3 py-2"
                style={{
                  background: "var(--kbli-bg-elevated)",
                  border: "1px solid var(--kbli-border)",
                }}
              >
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--kbli-accent)]/40" />
                <div>
                  <span className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
                    {obl}
                  </span>
                  {/* English translation for common Indonesian obligations */}
                  {obl.toLowerCase().includes("sertifikat laik sehat") && (
                    <p className="mt-0.5 text-xs text-[var(--foreground-muted)]">
                      → Obtain Health Feasibility Certificate from Dinas
                      Kesehatan
                    </p>
                  )}
                  {obl.toLowerCase().includes("laporan kegiatan") && (
                    <p className="mt-0.5 text-xs text-[var(--foreground-muted)]">
                      → Submit periodic business activity reports to regulator
                    </p>
                  )}
                  {obl.toLowerCase().includes("standar") &&
                    obl.toLowerCase().includes("menerapkan") && (
                      <p className="mt-0.5 text-xs text-[var(--foreground-muted)]">
                        → Submit documentation of standard implementation
                        compliance
                      </p>
                    )}
                  {obl.toLowerCase().includes("penerapan standar") &&
                    !obl.toLowerCase().includes("menerapkan") && (
                      <p className="mt-0.5 text-xs text-[var(--foreground-muted)]">
                        → Provide evidence of business standard compliance
                        documents
                      </p>
                    )}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

/** Regulatory Alert — high-impact callout */
function RegulatoryAlert({ markdown }: { markdown: string }) {
  // Split multi-warning alerts into separate visual blocks
  const warnings = markdown.split(/\n(?=\*\*\d+\.\s)/).filter((w) => w.trim());
  const isMultiWarning = warnings.length > 1;

  return (
    <div
      className="relative overflow-hidden rounded-xl border px-6 py-5"
      style={{
        background:
          "linear-gradient(135deg, rgba(232, 113, 108, 0.08), rgba(232, 168, 73, 0.04), rgba(232, 113, 108, 0.03) 80%)",
        borderColor: "rgba(232, 113, 108, 0.25)",
      }}
    >
      {/* Glow orb */}
      <div
        className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(232,113,108,0.1) 0%, transparent 70%)",
        }}
      />
      {/* Second glow for emphasis */}
      <div
        className="pointer-events-none absolute -bottom-12 -left-12 h-32 w-32 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(232,113,108,0.06) 0%, transparent 70%)",
        }}
      />

      <div className="relative">
        <div className="mb-4 flex items-center gap-2.5">
          <span
            className="flex h-7 w-7 items-center justify-center rounded-lg text-base"
            style={{
              background: "rgba(232, 113, 108, 0.15)",
              border: "1px solid rgba(232, 113, 108, 0.25)",
            }}
          >
            ⚠
          </span>
          <span
            className="text-xs font-bold uppercase tracking-[0.15em]"
            style={{ color: "var(--kbli-pma-closed)" }}
          >
            Regulatory Alert
          </span>
        </div>

        {isMultiWarning ? (
          <div className="space-y-3">
            {warnings.map((warning, i) => (
              <div
                key={i}
                className="rounded-lg px-4 py-3 kbli-prose"
                style={{
                  background: "rgba(232, 113, 108, 0.04)",
                  border: "1px solid rgba(232, 113, 108, 0.1)",
                }}
              >
                <ReactMarkdown>{warning.trim()}</ReactMarkdown>
              </div>
            ))}
          </div>
        ) : (
          <div className="kbli-prose">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

/** Authority flow — visual horizontal pipeline instead of bullets */
function AuthorityFlow({ body }: { body: string }) {
  // Parse "**Level:** description" patterns from the markdown
  const items: { level: string; description: string }[] = [];
  const lines = body.split("\n").filter((l) => l.trim());
  for (const line of lines) {
    const match = line.match(/[-*]\s*\*\*([^*]+?):\*\*\s*(.*)/);
    if (match) {
      items.push({ level: match[1].trim(), description: match[2].trim() });
    }
  }

  if (items.length === 0) {
    // Fallback to prose if we can't parse
    return (
      <div className="kbli-prose">
        <ReactMarkdown>{body}</ReactMarkdown>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0 sm:flex-row sm:items-stretch sm:gap-0">
      {items.map((item, i) => (
        <div key={i} className="flex items-stretch sm:flex-1">
          <div
            className="flex flex-1 flex-col gap-1 rounded-lg px-4 py-3"
            style={{ background: "var(--kbli-bg-surface)" }}
          >
            <span
              className="text-[10px] font-bold uppercase tracking-[0.15em]"
              style={{ color: "var(--kbli-accent2)" }}
            >
              {item.level}
            </span>
            <span className="text-xs leading-relaxed text-[var(--foreground-secondary)]">
              {item.description}
            </span>
          </div>
          {i < items.length - 1 && (
            <div className="flex items-center justify-center px-1.5 text-[var(--foreground-muted)] sm:px-2">
              <span className="hidden text-lg sm:block">→</span>
              <span className="block text-lg sm:hidden">↓</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// Numbered Step List — colored boxes with gradient shades
// =============================================================================

/** Step colors — 7 shades cycling through amber→orange→teal palette */
const STEP_COLORS = [
  {
    bg: "rgba(212, 132, 90, 0.12)",
    border: "rgba(212, 132, 90, 0.25)",
    num: "var(--kbli-accent)",
  },
  {
    bg: "rgba(212, 132, 90, 0.08)",
    border: "rgba(212, 132, 90, 0.18)",
    num: "var(--kbli-accent)",
  },
  {
    bg: "rgba(139, 156, 247, 0.08)",
    border: "rgba(139, 156, 247, 0.18)",
    num: "var(--kbli-accent2)",
  },
  {
    bg: "rgba(139, 156, 247, 0.10)",
    border: "rgba(139, 156, 247, 0.22)",
    num: "var(--kbli-accent2)",
  },
  {
    bg: "rgba(94, 196, 144, 0.08)",
    border: "rgba(94, 196, 144, 0.18)",
    num: "var(--kbli-pma-open)",
  },
  {
    bg: "rgba(94, 196, 144, 0.10)",
    border: "rgba(94, 196, 144, 0.22)",
    num: "var(--kbli-pma-open)",
  },
  {
    bg: "rgba(232, 168, 73, 0.08)",
    border: "rgba(232, 168, 73, 0.20)",
    num: "var(--kbli-amber)",
  },
];

function StepList({ body }: { body: string }) {
  const lines = body.split("\n");
  const steps: { num: number; label: string; desc: string }[] = [];
  let otherContent: string[] = [];

  for (const line of lines) {
    // Match "1. **Label** — desc" or "1. **Label** (extra text) — desc"
    const stepMatch = line.match(/^(\d+)\.\s+\*\*([^*]+)\*\*\s*(.*)/);
    if (stepMatch) {
      const num = parseInt(stepMatch[1]);
      const label = stepMatch[2].trim();
      // Everything after **label** — split on em-dash to get parenthetical + desc
      const afterLabel = stepMatch[3].trim();
      const dashIdx = afterLabel.search(/[—–]/);
      const desc =
        dashIdx >= 0 ? afterLabel.slice(dashIdx + 1).trim() : afterLabel;
      const paren = dashIdx >= 0 ? afterLabel.slice(0, dashIdx).trim() : "";
      steps.push({ num, label: paren ? `${label} ${paren}` : label, desc });
    } else if (line.trim()) {
      otherContent.push(line);
    }
  }

  if (steps.length === 0) {
    return (
      <div className="kbli-prose">
        <ReactMarkdown>{body}</ReactMarkdown>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {steps.map((step, i) => {
        const color = STEP_COLORS[i % STEP_COLORS.length];
        return (
          <div
            key={step.num}
            className="flex items-start gap-3 rounded-xl px-4 py-3"
            style={{
              background: color.bg,
              border: `1px solid ${color.border}`,
            }}
          >
            <span
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-black mt-0.5"
              style={{ background: color.border, color: color.num }}
            >
              {step.num}
            </span>
            <div className="min-w-0">
              <span
                className="text-sm font-semibold"
                style={{ color: color.num }}
              >
                {step.label}
              </span>
              {step.desc && (
                <span className="ml-1.5 text-sm text-[var(--foreground-secondary)]">
                  — {step.desc}
                </span>
              )}
            </div>
          </div>
        );
      })}

      {/* Render any trailing non-step content */}
      {otherContent.length > 0 && (
        <div className="kbli-prose pt-1">
          <ReactMarkdown>{otherContent.join("\n")}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

/** Editorial content section with proper visual hierarchy */
function ContentSection({
  title,
  body,
  type,
}: {
  title: string;
  body: string;
  type: SectionType;
}) {
  if (!body.trim()) return null;

  const style = SECTION_STYLES[type];
  const displayTitle = humanizeTitle(title);

  // Detect step-by-step sections
  const isStepByStep =
    title.toLowerCase().includes("step") ||
    title.toLowerCase().includes("how to") ||
    /^\d+\.\s+\*\*/.test(body.trim());

  // PMA sections are usually one line — render inline, not as a card
  if (type === "pma") {
    return (
      <div
        className="flex items-start gap-3 rounded-lg px-4 py-3"
        style={{ background: "var(--kbli-bg-surface)" }}
      >
        <div
          className="mt-0.5 h-4 w-0.5 shrink-0 rounded-full"
          style={{ background: style.accentColor }}
        />
        <div>
          <span
            className="text-[10px] font-bold uppercase tracking-[0.15em]"
            style={{ color: style.accentColor }}
          >
            {displayTitle}
          </span>
          <div className="mt-1 text-sm text-[var(--foreground-secondary)]">
            <ReactMarkdown>{body}</ReactMarkdown>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Section header */}
      {displayTitle && (
        <div className="mb-3 flex items-center gap-2.5">
          <div
            className="h-5 w-0.5 rounded-full"
            style={{ background: style.accentColor }}
          />
          <h4
            className="text-xs font-bold uppercase tracking-[0.15em]"
            style={{ color: style.accentColor }}
          >
            {displayTitle}
          </h4>
        </div>
      )}

      {/* Authority chain gets special visual treatment */}
      {type === "authority" ? (
        <AuthorityFlow body={body} />
      ) : isStepByStep ? (
        <StepList body={body} />
      ) : (
        <div className="kbli-prose">
          <ReactMarkdown>{body}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function LicensingSection({ kbli, gold }: LicensingSectionProps) {
  const [activeTier, setActiveTier] = useState(0);

  const parsed = gold ? parseWhatYouNeed(gold.whatYouNeed) : null;
  const currentTier = kbli.licensing[activeTier] ?? kbli.licensing[0];

  return (
    <div className="space-y-8">
      {/* ── KEY FACTS AT A GLANCE ── */}
      <KeyFacts licensing={kbli.licensing} pma={kbli.pma} />

      {/* ── PP28 RAW DATA (collapsible) ── */}
      {currentTier && (
        <details className="group rounded-xl border border-[var(--border)] overflow-hidden">
          <summary
            className="flex cursor-pointer items-center gap-3 px-5 py-3.5 text-xs font-bold uppercase tracking-[0.12em] text-[var(--foreground-muted)] transition-colors hover:text-[var(--foreground-secondary)] [&::-webkit-details-marker]:hidden list-none"
            style={{ background: "var(--kbli-bg-elevated)" }}
          >
            <svg
              className="h-4 w-4 shrink-0 transition-transform duration-200 group-open:rotate-90"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <path d="M6 4l4 4-4 4" />
            </svg>
            <span>PP28/2025 Licensing Data</span>
            <span className="ml-auto rounded-full border border-[var(--border)] px-2 py-0.5 text-[10px] font-medium">
              {kbli.licensing.length}{" "}
              {kbli.licensing.length === 1 ? "scale" : "scales"}
            </span>
          </summary>
          <div
            className="space-y-4 p-5"
            style={{ background: "var(--kbli-bg-surface)" }}
          >
            {/* Tier tabs */}
            {kbli.licensing.length > 1 && (
              <div className="flex items-center gap-4">
                <span className="text-xs text-[var(--foreground-muted)]">
                  Business scale:
                </span>
                <TierTabs
                  tiers={kbli.licensing}
                  activeTier={activeTier}
                  onSelect={setActiveTier}
                />
              </div>
            )}

            {/* Tier header */}
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-semibold text-[var(--foreground)]">
                {currentTier.scales.join(", ")}
              </span>
              <RiskBadge category={currentTier.riskCategory} size="sm" />
              <span className="text-xs text-[var(--foreground-muted)]">
                {currentTier.licenseType}
              </span>
              {currentTier.timeframe && (
                <span
                  className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                  style={{
                    background: currentTier.timeframe
                      .toLowerCase()
                      .includes("otomatis")
                      ? "rgba(94, 196, 144, 0.08)"
                      : "rgba(232, 168, 73, 0.08)",
                    color: currentTier.timeframe
                      .toLowerCase()
                      .includes("otomatis")
                      ? "var(--kbli-pma-open)"
                      : "var(--kbli-pma-restricted)",
                  }}
                >
                  ⏱ {currentTier.timeframe}
                </span>
              )}
              {currentTier.fictivePositive && (
                <span
                  className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                  style={{
                    background: "rgba(94, 196, 144, 0.08)",
                    color: "var(--kbli-pma-open)",
                  }}
                >
                  Fiktif Positif
                </span>
              )}
            </div>
            <TierDetail tier={currentTier} />
          </div>
        </details>
      )}

      {/* ── EDITORIAL CONTENT SECTIONS ── */}
      {parsed && parsed.sections.length > 0 && (
        <div className="space-y-6">
          {parsed.sections.map((sec, i) => (
            <ContentSection
              key={i}
              title={sec.title}
              body={sec.body}
              type={detectSectionType(sec.title)}
            />
          ))}
        </div>
      )}

      {/* ── REGULATORY ALERT ── */}
      {parsed?.alert && <RegulatoryAlert markdown={parsed.alert} />}

      {/* ── SOURCE REGULATION ── */}
      {parsed?.source && (
        <details className="rounded-xl border border-[var(--border)] overflow-hidden">
          <summary
            className="cursor-pointer px-4 py-2.5 text-xs font-medium text-[var(--foreground-muted)] transition-colors hover:text-[var(--foreground-secondary)]"
            style={{ background: "var(--kbli-bg-elevated)" }}
          >
            Source Regulations
          </summary>
          <div
            className="px-4 py-2.5 text-xs text-[var(--foreground-secondary)]"
            style={{ background: "var(--kbli-bg-surface)" }}
          >
            {parsed.source}
          </div>
        </details>
      )}
    </div>
  );
}
