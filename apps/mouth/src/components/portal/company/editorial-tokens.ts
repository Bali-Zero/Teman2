import type React from "react";

// ── GLASS CARD STYLES ──────────────────────────────────────────────────
// WS3 slice 9 (GARUDA Day Edition, 2026-07-24): surfaces now read the themed
// --kbli-bg-card (operative-light re-arms it to card white via globals.css)
// instead of the dark-only white-alpha gradient; shadows use the Day
// concept's soft navy panel shadow (0 14px 34px rgba(22,33,58,.07) —
// near-invisible on dark) instead of the muddy rgba(0,0,0,.3) drop. Role
// accents read the semantic --state-* / --bz-copper tokens (AA on paper;
// state primitives reproduce the old neon hues on dark). Shared with the
// workspace CompanyTab, so both themes stay correct from one definition.
export const crystalCard: React.CSSProperties = {
  background: "var(--kbli-bg-card)",
  backdropFilter: "blur(24px)",
  WebkitBackdropFilter: "blur(24px)",
  borderRadius: "var(--kbli-radius-lg)",
  border: "1px solid var(--kbli-border)",
  boxShadow:
    "inset 0 1px 0 0 var(--glass-highlight), 0 14px 34px rgba(22, 33, 58, 0.07)",
};

export const glassCard: React.CSSProperties = {
  background: "var(--kbli-bg-card)",
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  border: "1px solid var(--kbli-border)",
  boxShadow:
    "inset 0 1px 0 0 var(--glass-highlight), 0 14px 34px rgba(22, 33, 58, 0.07)",
};

// ── ROLE COLORS ────────────────────────────────────────────────────────
// `accent` = decorative bars / large numerals (≥3:1 floor); `text` = the AA
// small-text step for initials on tinted wells (copper at 12%-style tints
// fails AA for small text on both themes — slice-6 finding — so the small
// step reads --bz-copper-text).
export function getRoleColor(role: string) {
  const r = (role || "").toLowerCase();
  const isDirector = r.includes("director") || r.includes("direktur");
  const isCommissioner = r.includes("commissioner") || r.includes("komisaris");

  if (isDirector)
    return {
      accent: "var(--bz-copper)",
      text: "var(--bz-copper-text, var(--bz-copper))",
      bg: "color-mix(in srgb, var(--bz-copper) 10%, transparent)",
      border: "color-mix(in srgb, var(--bz-copper) 25%, transparent)",
    };
  if (isCommissioner)
    return {
      accent: "var(--state-info)",
      text: "var(--state-info)",
      bg: "color-mix(in srgb, var(--state-info) 10%, transparent)",
      border: "color-mix(in srgb, var(--state-info) 25%, transparent)",
    };
  return {
    accent: "var(--kbli-text-secondary)",
    text: "var(--kbli-text-secondary)",
    bg: "var(--glass-rim)",
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
