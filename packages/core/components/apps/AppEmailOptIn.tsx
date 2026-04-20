"use client";

import { useState, type FC } from "react";

export interface AppEmailOptInProps {
  /** "visa_clock" | "visa_match" | etc. */
  app: string;
  /** Context hash (e.g. visa_checks.hash). */
  resultHash: string;
  /** What the user will receive — 1 sentence. */
  promise: string;
  /** Extra payload to pass to the backend on subscribe. */
  payload?: Record<string, unknown>;
  /** API base — default same-origin. */
  apiBase?: string;
  /** Explicit subscribe endpoint override (defaults to /api/visa/<app>/email). */
  endpoint?: string;
  /** Called after successful subscribe. */
  onSubscribed?: (email: string) => void;
}

/** Optional email opt-in shown below the result. No default-checked
 * tricks — user types email + clicks. */
export const AppEmailOptIn: FC<AppEmailOptInProps> = ({
  app,
  resultHash,
  promise,
  payload,
  apiBase = "",
  endpoint,
  onSubscribed,
}) => {
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const url =
    endpoint ?? `${apiBase}/api/visa/${app.replace("visa_", "")}/email`;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.includes("@")) {
      setError("That email doesn't look valid.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          app,
          result_hash: resultHash,
          payload: payload ?? {},
        }),
      });
      if (!res.ok) throw new Error(`subscribe failed ${res.status}`);
      setDone(true);
      onSubscribed?.(email);
    } catch {
      setError("Could not subscribe. Please try again.");
    } finally {
      setPending(false);
    }
  };

  if (done) {
    return (
      <p
        style={{
          margin: 0,
          padding: "var(--space-3)",
          borderRadius: 8,
          background: "var(--surface-raised)",
          fontSize: "var(--text-sm)",
          color: "var(--color-text-muted)",
        }}
      >
        Check your inbox — first note comes soon. Unsubscribe link in every
        email.
      </p>
    );
  }

  return (
    <form
      onSubmit={submit}
      style={{
        display: "grid",
        gap: "var(--space-2)",
        padding: "var(--space-3)",
        background: "var(--surface-raised)",
        borderRadius: 8,
      }}
    >
      <label
        htmlFor={`optin-${app}-${resultHash}`}
        style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}
      >
        {promise}
      </label>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <input
          id={`optin-${app}-${resultHash}`}
          type="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{
            flex: 1,
            padding: "var(--space-2) var(--space-3)",
            borderRadius: 6,
            border: "1px solid var(--color-border-subtle)",
            fontSize: "var(--text-md)",
          }}
        />
        <button
          type="submit"
          disabled={pending}
          style={{
            padding: "var(--space-2) var(--space-4)",
            borderRadius: 6,
            border: "none",
            background: "var(--accent-funnel)",
            color: "#fff",
            fontWeight: 600,
            cursor: pending ? "wait" : "pointer",
          }}
        >
          {pending ? "…" : "Email me"}
        </button>
      </div>
      {error ? (
        <p
          role="alert"
          style={{
            margin: 0,
            color: "var(--color-error)",
            fontSize: "var(--text-sm)",
          }}
        >
          {error}
        </p>
      ) : null}
    </form>
  );
};
