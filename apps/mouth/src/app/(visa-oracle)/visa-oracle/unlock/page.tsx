"use client";

/**
 * Internal unlock screen for the Bali Zero team: enter the PIN once, then use
 * `/visa-oracle` at full power (real engine decisions) while the backend is
 * still in SHADOW. The PIN is verified server-side by
 * `POST /api/visa-oracle-unlock`, which sets a signed HttpOnly cookie.
 *
 * Not linked from the public Oracle UI on purpose — the team reaches it by
 * URL. It is a soft gate, not authentication (see `_lib/internal-access.ts`).
 */
import { useState, type FormEvent } from "react";

type Status = "idle" | "checking" | "error" | "unconfigured" | "done";

const UNLOCK_URL = "/api/visa-oracle-unlock";

export default function VisaOracleUnlockPage() {
  const [pin, setPin] = useState("");
  const [status, setStatus] = useState<Status>("idle");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pin.trim().length === 0 || status === "checking") return;
    setStatus("checking");
    try {
      const response = await fetch(UNLOCK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        credentials: "same-origin",
        body: JSON.stringify({ pin }),
      });
      if (response.ok) {
        setStatus("done");
        setPin("");
        window.location.assign("/visa-oracle");
        return;
      }
      setStatus(response.status === 503 ? "unconfigured" : "error");
    } catch {
      setStatus("error");
    }
  }

  async function lock() {
    try {
      await fetch(UNLOCK_URL, {
        method: "DELETE",
        cache: "no-store",
        credentials: "same-origin",
      });
    } finally {
      window.location.assign("/visa-oracle");
    }
  }

  return (
    <div className="oracle-root" data-oracle-theme="light" data-funnel="visa">
      <div className="oracle-shell">
        <div className="oracle-question">
          <h1 className="oracle-headline" tabIndex={-1}>
            Internal access
          </h1>
          <p className="oracle-subhead">
            Bali Zero team only. Unlocking shows the real engine decision for
            testing — it is not an authoritative answer and is not cleared for a
            client.
          </p>
          <form onSubmit={submit}>
            <label className="oracle-question__hint" htmlFor="vo-pin">
              Access PIN
            </label>
            <input
              id="vo-pin"
              name="pin"
              type="password"
              inputMode="numeric"
              autoComplete="off"
              autoFocus
              value={pin}
              onChange={(event) => setPin(event.currentTarget.value)}
              aria-describedby="vo-pin-status"
              style={{
                display: "block",
                margin: "0.75rem 0",
                padding: "0.6rem 0.8rem",
                fontSize: "1.1rem",
                letterSpacing: "0.2em",
                maxWidth: "12rem",
              }}
            />
            <button
              type="submit"
              className="oracle-option-card"
              style={{ width: "fit-content" }}
              disabled={status === "checking" || pin.trim().length === 0}
            >
              {status === "checking" ? "Checking…" : "Unlock"}
            </button>
          </form>
          <p id="vo-pin-status" className="oracle-question__hint" role="status">
            {status === "error" && "That PIN was not accepted."}
            {status === "unconfigured" &&
              "Internal access is not configured on this deployment."}
            {status === "done" && "Unlocked — opening the Oracle…"}
          </p>
          <button
            type="button"
            className="oracle-question__back"
            onClick={lock}
            style={{ marginTop: "1.5rem" }}
          >
            Lock this browser again
          </button>
        </div>
      </div>
    </div>
  );
}
