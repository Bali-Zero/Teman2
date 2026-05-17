/**
 * PinGate — full-page PIN modal that wraps children until auth succeeds.
 *
 * Calls POST /api/cockpit/auth (bcrypt verify server-side) which sets an
 * httpOnly cookie. The middleware on the server side handles ALL cookie
 * validation — this component just probes server state with GET to know
 * whether to show the modal or pass through.
 *
 * Read-only outcome: shows modal OR renders children. No destructive
 * action; failed PIN attempts feed the lib/cockpit-auth in-memory rate
 * limit.
 */
"use client";

import { useEffect, useState } from "react";

interface PinGateProps {
  children: React.ReactNode;
}

type GateState = "checking" | "locked" | "unlocked";

export default function PinGate({ children }: PinGateProps) {
  const [state, setState] = useState<GateState>("checking");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/cockpit/auth", { method: "GET", credentials: "include" })
      .then((r) => r.json())
      .then((j) => {
        if (cancelled) return;
        setState(j?.authenticated ? "unlocked" : "locked");
      })
      .catch(() => {
        if (cancelled) return;
        setState("locked");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting || !pin) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch("/api/cockpit/auth", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
      });
      if (res.status === 200) {
        setState("unlocked");
        setPin("");
      } else if (res.status === 429) {
        setError("Too many failed attempts — locked out for 5 minutes.");
      } else if (res.status === 401) {
        setError("Wrong PIN.");
      } else {
        setError(`Auth error (${res.status}).`);
      }
    } catch {
      setError("Network error — is the dev server still running?");
    } finally {
      setSubmitting(false);
    }
  }

  if (state === "unlocked") return <>{children}</>;

  if (state === "checking") {
    return (
      <div className="cockpit-pin-overlay">
        <div className="cockpit-pin-card">
          <h1>ZANTARA</h1>
          <p className="sub">Verifying session...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="cockpit-pin-overlay">
      <form className="cockpit-pin-card" onSubmit={onSubmit}>
        <h1>ZANTARA</h1>
        <p className="sub">Localhost-only command center. Enter PIN.</p>
        <div className="field">
          <label htmlFor="cockpit-pin">PIN</label>
          <input
            id="cockpit-pin"
            className="cockpit-input"
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            autoFocus
            autoComplete="off"
            inputMode="numeric"
            disabled={submitting}
          />
        </div>
        <div className="cockpit-pin-error">{error}</div>
        <button
          type="submit"
          className="cockpit-btn primary"
          disabled={submitting || !pin}
          style={{ width: "100%", justifyContent: "center" }}
        >
          {submitting ? "Verifying..." : "Unlock"}
        </button>
      </form>
    </div>
  );
}
