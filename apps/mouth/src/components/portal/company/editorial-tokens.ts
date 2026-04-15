import type React from "react";

// ── GLASS CARD STYLES ──────────────────────────────────────────────────
export const crystalCard: React.CSSProperties = {
  background:
    "linear-gradient(to bottom right, rgba(255,255,255,0.02), rgba(255,255,255,0.005))",
  backdropFilter: "blur(24px)",
  WebkitBackdropFilter: "blur(24px)",
  borderRadius: "var(--kbli-radius-lg)",
  border: "1px solid var(--kbli-border)",
  boxShadow:
    "inset 0 1px 0 0 var(--glass-highlight), inset 0 0 0 1px var(--glass-rim), 0 10px 20px -5px rgba(0,0,0,0.3)",
};

export const glassCard: React.CSSProperties = {
  background: "var(--kbli-bg-card)",
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  border: "1px solid var(--kbli-border)",
  boxShadow: "inset 0 1px 0 0 var(--glass-highlight), var(--kbli-shadow-card)",
};

// ── ROLE COLORS ────────────────────────────────────────────────────────
export function getRoleColor(role: string) {
  const r = (role || "").toLowerCase();
  const isDirector = r.includes("director") || r.includes("direktur");
  const isCommissioner = r.includes("commissioner") || r.includes("komisaris");

  if (isDirector)
    return {
      accent: "var(--kbli-accent)",
      bg: "var(--kbli-accent-subtle)",
      border: "var(--kbli-accent-muted)",
    };
  if (isCommissioner)
    return {
      accent: "var(--kbli-accent2)",
      bg: "var(--kbli-zantara-bg)",
      border: "rgba(139,156,247,0.2)",
    };
  return {
    accent: "var(--kbli-text-secondary)",
    bg: "rgba(255,255,255,0.04)",
    border: "var(--kbli-border)",
  };
}

// ── FORMATTING ─────────────────────────────────────────────────────────
export function formatCapital(shares?: number, nominal?: number) {
  if (!shares) return null;
  const nom = nominal || 1000000;
  const total = shares * nom;
  if (total >= 1e12)
    return `Rp ${(total / 1e12).toFixed(total % 1e12 === 0 ? 0 : 1)}T`;
  if (total >= 1e9)
    return `Rp ${(total / 1e9).toFixed(total % 1e9 === 0 ? 0 : 1)}B`;
  if (total >= 1e6) return `Rp ${(total / 1e6).toFixed(0)}M`;
  return `Rp ${total.toLocaleString()}`;
}

export function formatCapitalFull(shares?: number, nominal?: number) {
  if (!shares) return null;
  const nom = nominal || 1000000;
  const total = shares * nom;
  return `Rp ${total.toLocaleString("id-ID")}`;
}

export function getInitials(name: string) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export function computeAge(dateStr?: string) {
  if (!dateStr) return null;
  const founded = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - founded.getTime();
  const years = Math.floor(diffMs / (1000 * 60 * 60 * 24 * 365.25));
  const months = Math.floor(
    (diffMs % (1000 * 60 * 60 * 24 * 365.25)) / (1000 * 60 * 60 * 24 * 30.44),
  );
  return { years, months, label: `${years}y ${months}m` };
}

// ── COMPANY TYPE LABELS ────────────────────────────────────────────────
export const companyTypeSubtitles: Record<string, string> = {
  "PT PMA": "Penanaman Modal Asing",
  PMA: "Penanaman Modal Asing",
  "PT Perorangan": "Perseroan Perorangan",
  CV: "Commanditaire Vennootschap",
};
