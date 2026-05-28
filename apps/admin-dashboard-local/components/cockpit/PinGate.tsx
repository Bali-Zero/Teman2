"use client";
import { useState, useEffect } from "react";

export function PinGate({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState(false);
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/cockpit/cron/list").then((r) => {
      if (r.ok) setAuthed(true);
    });
  }, []);

  if (authed) return <>{children}</>;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/cockpit/auth", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ pin }),
      });
      if (r.status === 429) {
        setErr("rate-limited: try again in 5 minutes");
        return;
      }
      if (!r.ok) {
        setErr("invalid PIN");
        return;
      }
      setAuthed(true);
    } catch (e: any) {
      setErr(e.message);
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
        <div className="cockpit-widget-title">ZANTARA COCKPIT — PIN</div>
        <input
          type="password"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          autoFocus
          maxLength={20}
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
          disabled={busy || !pin}
          className="cockpit-action-button"
          style={{ marginTop: 16, width: "100%" }}
        >
          {busy ? "verifying..." : "unlock"}
        </button>
      </form>
    </div>
  );
}
