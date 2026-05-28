export type StatusColor = "green" | "amber" | "red";

export function StatusDot({
  status,
  label,
}: {
  status: StatusColor;
  label?: string;
}) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center" }}>
      <span className={`status-dot ${status}`} aria-hidden />
      {label && <span style={{ marginLeft: 6 }}>{label}</span>}
    </span>
  );
}
