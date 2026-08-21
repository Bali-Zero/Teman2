import { AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";
import type { ScanSwitchState } from "@/lib/api/secondhome/secondhome.types";

/**
 * Honest Day-90 scanner arming-state badge — verbatim from
 * `resolve_scan_switch` (e33_guarantee_scanner.py) via GET /api/e33/summary.
 *
 * Hard constraint (spec): NEVER imply monitoring is active when it is not.
 * `unprovisioned` reads as an alarming red state on purpose — the scanner
 * kill switch does not exist yet in `system_settings` (see /secondhome
 * skill §4bis), so nothing is watching Day-90 deadlines automatically.
 */
export function ScannerBadge({ state }: { state: ScanSwitchState }) {
  if (state === "enabled") {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border"
        style={{
          background:
            "color-mix(in srgb, var(--state-success) 15%, transparent)",
          borderColor:
            "color-mix(in srgb, var(--state-success) 35%, transparent)",
          color: "var(--state-success)",
        }}
      >
        <CheckCircle2 className="w-3.5 h-3.5" />
        Day-90 scanner active
      </span>
    );
  }

  if (state === "disabled") {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border"
        style={{
          background:
            "color-mix(in srgb, var(--state-warning) 15%, transparent)",
          borderColor:
            "color-mix(in srgb, var(--state-warning) 35%, transparent)",
          color: "var(--state-warning)",
        }}
      >
        <AlertTriangle className="w-3.5 h-3.5" />
        Day-90 scanner disabled
      </span>
    );
  }

  // unprovisioned
  return (
    <span
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border"
      style={{
        background: "color-mix(in srgb, var(--state-danger) 15%, transparent)",
        borderColor: "color-mix(in srgb, var(--state-danger) 35%, transparent)",
        color: "var(--state-danger)",
      }}
      title="No system_settings row exists for the Day-90 guarantee scanner — nothing is watching deadlines automatically."
    >
      <ShieldAlert className="w-3.5 h-3.5" />
      Day-90 scanner NOT ARMED — monitoring is manual
    </span>
  );
}
