"use client";
import { useCallback, useState } from "react";
import { CockpitSessionProvider } from "@/lib/cockpit-session-context";

interface LoginResponse {
  token: string;
  expires_in: number;
}

export const AUTHENTICATION_UNAVAILABLE_MESSAGE = "authentication unavailable";

function isLoginResponse(value: unknown): value is LoginResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Partial<LoginResponse>;
  return (
    typeof response.token === "string" &&
    response.token.length > 0 &&
    typeof response.expires_in === "number" &&
    Number.isInteger(response.expires_in) &&
    response.expires_in > 0
  );
}

export function cockpitLoginFailureMessage(status: number): string {
  if (status === 401) return "invalid passphrase";
  if (status === 403) {
    return "origin/host blocked: use http://localhost:3100";
  }
  if (status === 429) return "rate-limited: try again in 5 minutes";
  return AUTHENTICATION_UNAVAILABLE_MESSAGE;
}

export function PinGate({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [passphrase, setPassphrase] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const relock = useCallback(() => setToken(null), []);

  if (token) {
    return (
      <CockpitSessionProvider token={token} relock={relock}>
        {children}
      </CockpitSessionProvider>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/cockpit/auth", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ passphrase }),
      });
      if (!r.ok) {
        setErr(cockpitLoginFailureMessage(r.status));
        return;
      }
      const response: unknown = await r.json();
      if (!isLoginResponse(response)) {
        setErr(AUTHENTICATION_UNAVAILABLE_MESSAGE);
        return;
      }
      setPassphrase("");
      setToken(response.token);
    } catch {
      setErr(AUTHENTICATION_UNAVAILABLE_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--bg-deep)",
      }}
    >
      <form
        onSubmit={submit}
        style={{
          background: "var(--bg-panel)",
          border: "1px solid var(--border)",
          padding: 32,
          minWidth: 320,
        }}
      >
        <div className="cockpit-widget-title">ZANTARA COCKPIT — PASSPHRASE</div>
        <input
          type="password"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          autoFocus
          minLength={16}
          maxLength={64}
          autoComplete="current-password"
          style={{
            display: "block",
            width: "100%",
            background: "var(--bg-deep)",
            border: "1px solid var(--border-active)",
            color: "var(--fg-primary)",
            padding: 8,
            fontFamily: "inherit",
            fontSize: 14,
            marginTop: 16,
          }}
        />
        {err && (
          <div style={{ color: "var(--fg-red)", fontSize: 11, marginTop: 8 }}>
            {err}
          </div>
        )}
        <button
          type="submit"
          disabled={busy || passphrase.length < 16}
          className="cockpit-action-button"
          style={{ marginTop: 16, width: "100%" }}
        >
          {busy ? "verifying..." : "unlock"}
        </button>
      </form>
    </div>
  );
}
