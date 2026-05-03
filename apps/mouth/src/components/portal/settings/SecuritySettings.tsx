"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

/**
 * Security tab — placeholder-heavy by design.
 *
 * Only the "revoke all other sessions" action hits a real endpoint
 * (`POST /api/auth/revoke-all`, exists today). Password change and 2FA
 * are intentionally rendered as informational panels because the BE does
 * not expose `/me/password` or `/me/2fa` endpoints yet (see Task 4.2
 * audit). When those endpoints ship, replace the Panel placeholders
 * with real forms — do NOT fake the flow in the meantime.
 */
export function SecuritySettings() {
  const [revoking, setRevoking] = useState(false);
  const [result, setResult] = useState<"" | "ok" | "error">("");

  const revokeAll = async () => {
    setRevoking(true);
    setResult("");
    try {
      await api.post("/api/auth/revoke-all", {});
      setResult("ok");
    } catch (err) {
      logger.error(
        "SecuritySettings: revoke-all failed",
        {
          component: "SecuritySettings",
          action: "revoke_all_failure",
        },
        err as Error,
      );
      setResult("error");
    } finally {
      setRevoking(false);
    }
  };

  return (
    <section className="space-y-8 max-w-lg">
      <Panel
        title="Password"
        subtitle="Password change via this portal is not yet available. Contact team@balizero.com to reset your PIN."
      />
      <Panel
        title="Two-factor authentication"
        subtitle="2FA is coming soon. Your account is currently secured by email + PIN."
      />
      <div>
        <h3 className="text-sm uppercase tracking-[2px] text-[#c9a96e]/50 mb-2">
          Active sessions
        </h3>
        <p className="text-sm text-[#c9a96e]/70 mb-3">
          If you suspect unauthorized access, log out all other devices now.
        </p>
        <button
          type="button"
          onClick={revokeAll}
          disabled={revoking}
          className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline disabled:opacity-50"
        >
          {revoking ? "Logging out…" : "Log out all other sessions"}
        </button>
        {result === "ok" && (
          <p role="status" className="text-xs text-[#4a9c5c] mt-2">
            All other sessions revoked.
          </p>
        )}
        {result === "error" && (
          <p role="alert" className="text-xs text-[#c94a4a] mt-2">
            Unable to revoke sessions. Try again.
          </p>
        )}
      </div>
    </section>
  );
}

function Panel({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h3 className="text-sm uppercase tracking-[2px] text-[#c9a96e]/50 mb-1">
        {title}
      </h3>
      <p className="text-sm text-[#c9a96e]/70">{subtitle}</p>
    </div>
  );
}
