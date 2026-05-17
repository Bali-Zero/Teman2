/**
 * HomeTile — small card with label + big number + meta line.
 *
 * MVP is read-only: tiles do NOT trigger actions. Optional `href` reserved
 * for future iteration (out of MVP scope per spec).
 */

interface HomeTileProps {
  label: string;
  value: React.ReactNode;
  suffix?: React.ReactNode;
  meta?: React.ReactNode;
  status?: "healthy" | "amber" | "red";
}

export default function HomeTile({
  label,
  value,
  suffix,
  meta,
  status,
}: HomeTileProps) {
  return (
    <div className="cockpit-tile" data-status={status ?? "neutral"}>
      <div className="cockpit-tile-label">{label}</div>
      <div className="cockpit-tile-number">
        {value}
        {suffix ? <span className="suffix">{suffix}</span> : null}
      </div>
      {meta ? (
        <div className="cockpit-tile-meta">
          {status ? <span className={`cockpit-dot ${status}`} /> : null}
          {meta}
        </div>
      ) : null}
    </div>
  );
}
