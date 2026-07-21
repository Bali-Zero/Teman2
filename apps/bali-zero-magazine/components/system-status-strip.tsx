import type { SourceStatusView } from "@/lib/server/magazine-read-model";

type SystemStatusStripProps = Readonly<{
  systems: readonly SourceStatusView[];
  unavailable?: boolean;
}>;

function statusLabel(health: SourceStatusView["health"]): string {
  return `${health.slice(0, 1).toUpperCase()}${health.slice(1)}`;
}

export function SystemStatusStrip({
  systems,
  unavailable = false,
}: SystemStatusStripProps) {
  return (
    <aside className="system-status" aria-labelledby="system-status-title">
      <div>
        <p className="section-label">Observatory health</p>
        <h2 id="system-status-title">Source systems</h2>
      </div>
      {systems.length > 0 ? (
        <ul>
          {systems.map((system) => (
            <li key={system.name}>
              <strong>{system.name}</strong>
              <span className={`system-health system-health--${system.health}`}>
                {statusLabel(system.health)}
              </span>
              {system.verifiedAt ? (
                <time dateTime={system.verifiedAt}>
                  Checked{" "}
                  {new Date(system.verifiedAt).toLocaleTimeString("en-GB", {
                    hour: "2-digit",
                    minute: "2-digit",
                    timeZone: "Asia/Makassar",
                  })}{" "}
                  WITA
                </time>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="status-unavailable">
          {unavailable
            ? "Source status is temporarily unavailable."
            : "No source status has been published yet."}
        </p>
      )}
    </aside>
  );
}
