import type { KBLICode, KBLIProvenance } from "@/lib/kbli-types";

// =============================================================================
// TRACK-P — "Sources & Verification" panel
// One row per fact layer rendered on the page: what the source is, which KBLI
// vintage it speaks, and whether it is verified / pending / detached. The
// honesty contract (kbli-navigator corner §0): a declared gap is acceptable, a
// plausible-but-wrong assertion is not — so no row ever claims more than its
// structured marker supports.
// =============================================================================

interface KBLIProvenancePanelProps {
  kbli: KBLICode;
  /** Dataset sidecar date (kbli-dataset-version.json) — NOT file mtime */
  lastModified: Date;
}

/** Human-readable labels for the raw assembly markers (fallback: raw value). */
const ASSEMBLY_LABELS: Record<string, string> = {
  "BPS_7_2025 + PP28_2025": "BPS Peraturan 7/2025 + PP 28/2025",
  PP28_2025_ONLY: "PP 28/2025 (not in the BPS 7/2025 index)",
  BPS_7_2025_ONLY: "BPS Peraturan 7/2025 (no PP 28/2025 rows)",
};

type Verdict = "verified" | "pending" | "gap";

const VERDICT_STYLE: Record<Verdict, { label: string; color: string }> = {
  verified: { label: "Verified", color: "var(--kbli-pma-open)" },
  pending: { label: "Audit pending", color: "var(--kbli-pma-restricted)" },
  gap: { label: "Declared gap", color: "var(--foreground-muted)" },
};

interface SourceRow {
  layer: string;
  source: string;
  vintage: string;
  verdict: Verdict;
  detail?: string;
  locator?: string | null;
}

function buildRows(kbli: KBLICode, prov: KBLIProvenance): SourceRow[] {
  const rows: SourceRow[] = [];

  rows.push({
    layer: "Activity definition",
    source:
      ASSEMBLY_LABELS[prov.definition.assembly ?? ""] ??
      prov.definition.assembly ??
      "—",
    vintage: "KBLI 2025",
    verdict: "verified",
    detail: "Title and scope as defined by the KBLI-2025 classification.",
    locator: prov.definition.locator,
  });

  if (prov.licensing.status === "oss_native") {
    rows.push({
      layer: "Risk & licensing",
      source: "OSS RBA risk scope (ruang lingkup)",
      vintage: "KBLI 2025",
      verdict: "verified",
      detail:
        "Risk category and licensing rows are KBLI-2025-native from the OSS Risk-Based Approach catalog.",
      locator: prov.licensing.locator,
    });
  } else if (prov.licensing.status === "pending_crosswalk") {
    // Two honest readings of the no-scope set, discriminated by whether rows
    // are actually served (114 carry PP28-via-2020 rows; 101 have none —
    // special/sectoral regime). Wording per corner rule F12: a 404 attests
    // retrievability via the OSS API, never regulatory absence.
    const hasRows = kbli.licensing.length > 0;
    rows.push({
      layer: "Risk & licensing",
      source: hasRows
        ? "PP 28/2025 rows via KBLI-2020 numbering"
        : "No OSS-RBA rows retrievable — special / sectoral regime",
      vintage: hasRows ? "KBLI 2020" : "—",
      verdict: hasRows ? "pending" : "gap",
      detail: hasRows
        ? "No KBLI-2025 risk scope was retrievable from the OSS API for this code (ruang-lingkup 404). The rows shown were recorded under the KBLI-2020 numbering and await per-code crosswalk adjudication."
        : "No KBLI-2025 risk scope was retrievable from the OSS API for this code (ruang-lingkup 404), and no licensing rows are served on this page. Activities in this group are typically licensed under a special or sectoral regime — on the crosswalk watchlist: if OSS publishes a scope, the code is re-adjudicated.",
    });
  } else if (prov.licensing.status === "unverified_source") {
    rows.push({
      layer: "Risk & licensing",
      source: "No recognised source marker — audit required",
      vintage: "—",
      verdict: "pending",
      detail:
        "This code's licensing rows carry no recognised provenance marker (absent or unknown), so their source and vintage cannot be stated. Treat them as unaudited until the crosswalk program classifies them.",
    });
  } else {
    // Neutral by design: the causes behind a detach VARY per code (digit
    // collision, wrong-pointer transplant, unlocatable source) — the
    // correction note in the Divergence section carries the specifics, this
    // row never flattens them into one cause (Codex gate F2).
    rows.push({
      layer: "Risk & licensing",
      source: "Detached — source could not be verified",
      vintage: "—",
      verdict: "gap",
      detail:
        "The previously-served rows were removed because their source could not be verified as applying to this activity. See Regulatory Divergence above for the documented correction note.",
    });
  }

  rows.push({
    layer: "Foreign ownership (PMA)",
    source: prov.pma.source ?? "Perpres 10/2021, 49/2021",
    vintage: "KBLI 2020",
    verdict: "pending",
    detail:
      "The investment-list annexes predate KBLI 2025; the per-code crosswalk audit of this layer is in progress. The value shown is the annex text, disclosed with its vintage.",
  });

  if (kbli.baliL4) {
    const m = kbli.baliL4.moratorium;
    const isNonClassifiable = kbli.baliL4.status === "NON_CLASSIFICABILE";
    rows.push({
      layer: "Bali status",
      source: m?.rule
        ? `${m.rule}${m.effective ? ` (effective ${m.effective})` : ""}`
        : "Bali moratorium overlay (Gubernur letter B.27.000/642)",
      vintage: "2026 overlay",
      verdict: isNonClassifiable ? "gap" : "pending",
      detail: isNonClassifiable
        ? "Not classifiable until the true risk tier is re-derived — the tier this verdict depended on was detached."
        : `Conservative posture derived from the risk tier · confidence ${kbli.baliL4.confidence}.`,
    });
  }

  return rows;
}

export function KBLIProvenancePanel({
  kbli,
  lastModified,
}: KBLIProvenancePanelProps) {
  const prov = kbli.provenance;
  if (!prov) return null;

  const rows = buildRows(kbli, prov);
  const dateStr = lastModified.toISOString().slice(0, 10);

  return (
    <section className="mt-12">
      <div className="mb-5 flex items-center gap-3">
        <div
          className="h-8 w-1 rounded-full"
          style={{
            background:
              "linear-gradient(to bottom, var(--kbli-accent2), var(--kbli-accent))",
          }}
        />
        <div>
          <h2 className="text-sm font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]">
            Sources &amp; Verification
          </h2>
          <p className="text-xs text-[var(--foreground-muted)]">
            Each data layer below traces to a government source with its KBLI
            vintage — or is declared as a gap. Nothing in these layers is
            silently filled in.
          </p>
        </div>
      </div>

      <div
        className="overflow-hidden rounded-xl border border-[var(--border)]"
        style={{ background: "var(--kbli-bg-elevated)" }}
      >
        {rows.map((row) => {
          const v = VERDICT_STYLE[row.verdict];
          return (
            <div
              key={row.layer}
              className="flex flex-col gap-1.5 border-b border-[var(--border)] px-5 py-4 last:border-b-0 sm:flex-row sm:items-start sm:gap-4"
            >
              <div className="sm:w-44 sm:shrink-0">
                <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
                  {row.layer}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-[var(--foreground)]">
                    {row.source}
                  </span>
                  <span
                    className="rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                    style={{
                      color: v.color,
                      borderColor: `color-mix(in srgb, ${v.color} 30%, transparent)`,
                      background: `color-mix(in srgb, ${v.color} 8%, transparent)`,
                    }}
                  >
                    {v.label}
                  </span>
                  <span className="rounded-full border border-[var(--kbli-border)] px-2 py-0.5 text-[10px] font-medium text-[var(--foreground-muted)]">
                    {row.vintage}
                  </span>
                </div>
                {row.detail && (
                  <p className="mt-1 text-xs leading-relaxed text-[var(--foreground-secondary)]">
                    {row.detail}
                  </p>
                )}
                {row.locator && (
                  <p className="mt-1 font-mono text-[10px] text-[var(--foreground-muted)]">
                    locator: {row.locator}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-[11px] text-[var(--foreground-muted)]">
        Dataset last updated {dateStr} · KBLI 2020 and KBLI 2025 reuse code
        numbers for different activities — cross-vintage rows are labeled, never
        merged silently.
      </p>
    </section>
  );
}
