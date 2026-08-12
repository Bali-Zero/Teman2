import type { KBLITransition } from "@/lib/kbli-types";

interface KBLITransitionSourcesProps {
  transition: KBLITransition;
}

function PlainCodeList({ codes }: { codes: string[] }) {
  return (
    <>
      {codes.map((code, index) => (
        <span key={`${code}-${index}`}>
          <span className="font-mono font-bold text-[var(--foreground-secondary)]">
            {code}
          </span>
          {index < codes.length - 1 && ", "}
        </span>
      ))}
    </>
  );
}

/**
 * Vintage-safe transition disclosure.
 *
 * BPS is the only ancestry source and is always rendered first, including an
 * explicit gap. PP 28 stays visible only in its legitimate role: the source of
 * licensing rows. Every KBLI-2020 identifier is plain text because
 * `/kbli/<code>` denotes a KBLI-2025 entity.
 */
export function KBLITransitionSources({
  transition,
}: KBLITransitionSourcesProps) {
  const bpsCodes = transition.bpsCrosswalk?.codes ?? [];
  const pp28Codes = transition.pp28LicensingSourceCodes;

  return (
    <section aria-label="KBLI 2020 to 2025 transition sources">
      <div
        className="flex items-start gap-3 rounded-xl p-4"
        style={{
          background: "var(--kbli-bg-elevated)",
          border: "1px solid var(--kbli-border)",
        }}
        data-testid="bps-transition-source"
      >
        <span
          className="mt-0.5 inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-xs font-bold"
          style={{
            background: "rgba(139, 156, 247, 0.1)",
            color: "var(--kbli-accent2)",
            border: "1px solid rgba(139, 156, 247, 0.2)",
          }}
        >
          {bpsCodes.length > 0
            ? "Authoritative BPS crosswalk"
            : "BPS crosswalk gap"}
        </span>
        <div className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
          {bpsCodes.length > 0 ? (
            <>
              <span>Official BPS 2020 → 2025 crosswalk ancestors: </span>
              <PlainCodeList codes={bpsCodes} />
              <p className="mt-2 text-[11px] text-[var(--foreground-muted)]">
                Source: the BPS 2020↔2025 conversion table, mechanically
                extracted and acceptance-gate verified. It shows which 2020
                codes map to this 2025 code —{" "}
                <strong>provenance only, not a licensing claim</strong>: the
                regulatory regime of these predecessor codes has not been
                adjudicated as transferring.
              </p>
            </>
          ) : (
            <p>
              No official BPS 2020 → 2025 crosswalk ancestor is recorded for
              this code. This is an ancestry data gap, not evidence that no KBLI
              2020 predecessor existed.
            </p>
          )}
        </div>
      </div>

      {pp28Codes.length > 0 && (
        <div
          className="mt-3 flex items-start gap-3 rounded-xl p-4"
          style={{
            background: "var(--kbli-bg-elevated)",
            border:
              "1px solid color-mix(in srgb, var(--kbli-border) 75%, transparent)",
          }}
          data-testid="pp28-transition-source"
        >
          <span
            className="mt-0.5 inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-xs font-bold text-[var(--foreground-muted)]"
            style={{ border: "1px solid var(--kbli-border)" }}
          >
            PP 28/2025 licensing source
          </span>
          <div className="text-sm leading-relaxed text-[var(--foreground-secondary)]">
            <span>
              PP 28/2025 licensing-source codes (KBLI 2020 numbering):{" "}
            </span>
            <PlainCodeList codes={pp28Codes} />
            <p className="mt-2 text-[11px] text-[var(--foreground-muted)]">
              These codes identify the PP 28/2025 regulatory rows used as
              licensing sources for this page. They are not the official BPS
              2020 → 2025 crosswalk and do not establish predecessor ancestry.
            </p>
            {transition.mappingNote && (
              <p className="mt-2 text-[11px] text-[var(--foreground-muted)]">
                Legacy PP28 source-matching note: {transition.mappingNote}
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
