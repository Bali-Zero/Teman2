export function StatusChip({
  label,
  variant = "green",
  icon,
}: {
  label: string;
  variant?: "green" | "accent" | "cool" | "amber";
  icon?: React.ReactNode;
}) {
  const styles: Record<string, string> = {
    green:
      "bg-[var(--kbli-pma-open-bg)] text-[var(--kbli-pma-open)] border-transparent",
    accent:
      "bg-[var(--kbli-accent-subtle)] text-[var(--kbli-accent)] border-transparent",
    cool: "bg-[var(--kbli-zantara-bg)] text-[var(--kbli-accent2)] border-transparent",
    amber:
      "bg-[rgba(232,168,73,0.1)] text-[var(--kbli-amber)] border-transparent",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-[var(--kbli-radius-sm)] text-[10px] font-semibold uppercase tracking-[0.04em] ${styles[variant]}`}
    >
      {icon}
      {label}
    </span>
  );
}
