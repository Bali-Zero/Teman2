import type { KBLIProvenance } from "@/lib/kbli-types";
import { RiskBadge } from "./RiskBadge";

// =============================================================================
// TRACK-P — "Regulatory Divergence" section
// Product form of the internal discrepancy findings (kbli-navigator corner §5:
// "we show the divergence with citations"). Renders ONLY on codes a collision
// cure has touched: the honest-gap `_data_note` (which carries the verbatim,
// image-verified locators) plus the detached PP28 rows preserved under
// `per_skala_disputed_*`, framed as the KBLI-2020 meaning of the digits — not
// as licensing for this activity.
// =============================================================================

interface KBLIDivergenceProps {
  code: string;
  provenance: KBLIProvenance;
}

/** `perizinan` is a string on legacy rows, an array elsewhere. */
function licenseLabel(perizinan: string | string[] | undefined): string {
  if (!perizinan) return "—";
  if (Array.isArray(perizinan))
    return perizinan.length > 0 ? perizinan.join(", ") : "—";
  return perizinan;
}

export function KBLIDivergence({ code, provenance }: KBLIDivergenceProps) {
  const { dataNote, disputed } = provenance;
  if (!dataNote && !disputed) return null;

  // Citations are derived from structured markers only — the cure class is
  // NOT uniform (digit collisions, wrong-pointer transplants, unlocatable
  // sources), so no chip is asserted unless its marker backs it. The exact
  // locators (lampiran, page, render id, sha) live verbatim in the note.
  const citations: string[] = [
    "BPS Peraturan 7/2025 (KBLI 2025 classification)",
  ];
  if (disputed?.key.includes("pp28")) {
    citations.push("PP 28/2025 (risk-based licensing annexes)");
  }
  if (provenance.licensing.noOssScope) {
    citations.push(
      "OSS RBA ruang-lingkup — no KBLI-2025 scope retrievable via the OSS API (404)",
    );
  }

  return (
    <section className="mt-12">
      <div className="mb-5 flex items-center gap-3">
        <div
          className="h-8 w-1 rounded-full"
          style={{
            background:
              "linear-gradient(to bottom, var(--kbli-amber), var(--kbli-accent))",
          }}
        />
        <div>
          <h2 className="text-sm font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]">
            Regulatory Divergence
          </h2>
          <p className="text-xs text-[var(--foreground-muted)]">
            The licensing previously shown for {code} was removed because its
            source could not be verified as applying to this activity. Here is
            what the sources actually say — with citations.
          </p>
        </div>
      </div>

      {/* The documented note — written by the cure compiler, citations verbatim */}
      {dataNote && (
        <div
          className="rounded-xl border px-5 py-4"
          style={{
            background: "rgba(232, 168, 73, 0.05)",
            borderColor: "rgba(232, 168, 73, 0.25)",
          }}
        >
          <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--kbli-amber)]">
            Correction note — verbatim, with source locators
          </p>
          <p className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
            {dataNote}
          </p>
        </div>
      )}

      {/* The detached PP28 rows — audit trail, explicitly NOT this activity */}
      {disputed && disputed.rows.length > 0 && (
        <details className="group mt-4 overflow-hidden rounded-xl border border-[var(--border)]">
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
            <span>
              The detached licensing rows (source unverified for this activity)
            </span>
            <span className="ml-auto rounded-full border border-[var(--border)] px-2 py-0.5 text-[10px] font-medium">
              {disputed.rows.length}{" "}
              {disputed.rows.length === 1 ? "row" : "rows"}
            </span>
          </summary>
          <div
            className="space-y-3 p-5"
            style={{ background: "var(--kbli-bg-surface)" }}
          >
            <p className="text-xs leading-relaxed text-[var(--foreground-muted)]">
              These rows were previously shown on this page and have been
              detached — the correction note above documents, with source
              locators, why their source could not be kept for the activity this
              page describes. They are preserved here as the audit trail of the
              divergence.
            </p>
            {disputed.rows.map((row, i) => (
              <div
                key={i}
                className="rounded-lg border border-[var(--border)] px-4 py-3"
                style={{ background: "var(--kbli-bg-elevated)" }}
              >
                <div className="flex flex-wrap items-center gap-2.5">
                  {Array.isArray(row.skala_usaha) &&
                    row.skala_usaha.length > 0 && (
                      <span className="text-xs font-semibold text-[var(--foreground)]">
                        {row.skala_usaha.join(", ")}
                      </span>
                    )}
                  {row.kategori_risiko && (
                    <RiskBadge category={row.kategori_risiko} size="sm" />
                  )}
                  <span className="text-xs text-[var(--foreground-muted)]">
                    {licenseLabel(row.perizinan)}
                  </span>
                  {row.kewenangan && (
                    <span className="ml-auto text-[11px] text-[var(--foreground-muted)]">
                      Authority: {row.kewenangan}
                    </span>
                  )}
                </div>
                {row.scope_uraian && (
                  <p className="mt-1.5 text-[11px] italic text-[var(--foreground-muted)]">
                    Source-row scope: {row.scope_uraian}
                  </p>
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Citations */}
      <div className="mt-4 flex flex-wrap gap-2">
        {citations.map((c) => (
          <span
            key={c}
            className="rounded-full border border-[var(--kbli-border)] px-3 py-1 text-[11px] text-[var(--foreground-muted)]"
            style={{ background: "var(--kbli-bg-elevated)" }}
          >
            {c}
          </span>
        ))}
      </div>
    </section>
  );
}
