/**
 * StatusChip — small editorial status pill for the company profile hero.
 *
 * WS3 slice 9 (GARUDA Day Edition, 2026-07-24): variants read the semantic
 * --state-* / copper tokens as a hairline border + bare state fg instead of
 * tinted fills on dark-theme hues. The chip sits directly on the paper page
 * (hero, not on a card): a 12% color-mix tint over paper sinks success/
 * warning fg to ~4.1:1 — below the 4.5:1 small-text floor — so the fill is
 * dropped (same pattern as the slice-6/7 copper KBLI chip). Bare fg on
 * paper: success 4.80 / warning 4.78 / info 5.94 / copper-text 5.05 :1.
 * The old --kbli-pma-open / --kbli-amber / --kbli-accent2 hues computed
 * 1.84-2.27:1 on paper. Dark parity: state primitives ARE the previous neon
 * hexes, so the dark look is unchanged.
 */
export function StatusChip({
  label,
  variant = "green",
  icon,
}: {
  label: string;
  variant?: "green" | "accent" | "cool" | "amber";
  icon?: React.ReactNode;
}) {
  const styles: Record<string, React.CSSProperties> = {
    green: {
      border:
        "1px solid color-mix(in srgb, var(--state-success) 35%, transparent)",
      color: "var(--state-success)",
    },
    accent: {
      border: "1px solid color-mix(in srgb, var(--bz-copper) 35%, transparent)",
      color: "var(--bz-copper-text, var(--tx-secondary))",
    },
    cool: {
      border:
        "1px solid color-mix(in srgb, var(--state-info) 35%, transparent)",
      color: "var(--state-info)",
    },
    amber: {
      border:
        "1px solid color-mix(in srgb, var(--state-warning) 35%, transparent)",
      color: "var(--state-warning)",
    },
  };

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-[var(--kbli-radius-sm)] text-[10px] font-semibold uppercase tracking-[0.04em]"
      style={styles[variant]}
    >
      {icon}
      {label}
    </span>
  );
}
