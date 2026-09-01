"use client";

import { usePrimeNexus, type PrimeMode } from "@/contexts/PrimeNexusContext";
import { api } from "@/lib/api";

const MODES: {
  key: PrimeMode;
  label: string;
  icon: string;
  requiresAuth: boolean;
}[] = [
  { key: "invest", label: "Invest", icon: "💰", requiresAuth: false },
  { key: "crm", label: "CRM", icon: "👥", requiresAuth: true },
  { key: "intel", label: "Intel", icon: "📊", requiresAuth: true },
  { key: "temporal", label: "Tempo", icon: "📈", requiresAuth: true },
  { key: "portfolio", label: "Folio", icon: "💼", requiresAuth: true },
];

export function ModeSwitcher() {
  const { mode, setMode } = usePrimeNexus();

  return (
    <div className="flex items-center gap-1 bg-white/5 rounded-xl p-1 border border-white/10">
      {MODES.map((m) => (
        <button
          key={m.key}
          onClick={async () => {
            if (m.requiresAuth) {
              // `document.cookie` can never see `nz_access_token` — it is
              // httpOnly by design (SSO across .balizero.com subdomains), so
              // the old check here always read an empty string and ALWAYS
              // redirected: every visitor, cookie-only or not, who clicked
              // CRM/Intel/Tempo/Folio was bounced to /login. Ask the
              // server-aware probe instead (auth-gates-cookie-primary).
              const session = await api.hasSession();
              if (session === "anonymous") {
                window.location.href = "/login?redirect=/prime";
                return;
              }
              // "unknown"/"authenticated" both proceed: this only gates a UI
              // mode switch, not data — the domain panel behind each mode
              // still enforces its own 401 server-side.
            }
            setMode(m.key);
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            mode === m.key
              ? "bg-accent-warm text-white shadow-sm"
              : "text-slate-400 hover:text-white hover:bg-white/5"
          }`}
          title={m.requiresAuth ? `${m.label} — Requires admin login` : m.label}
        >
          <span className="mr-1">{m.icon}</span>
          {m.label}
        </button>
      ))}
    </div>
  );
}
