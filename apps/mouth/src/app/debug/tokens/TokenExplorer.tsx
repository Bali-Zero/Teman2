"use client";

import { useTheme, type Funnel, type Theme } from "@balizero/core/components/ThemeProvider";
import { BZLogo } from "@balizero/core/components/BZLogo";

const COLOR_PRIMITIVES = [
  { name: "--color-red-500", funnel: "Visa" },
  { name: "--color-gold-500", funnel: "KBLI" },
  { name: "--color-cyan-500", funnel: "Tax" },
  { name: "--color-green-500", funnel: "Property" },
  { name: "--color-purple-500", funnel: "Zantara" },
  { name: "--color-black", funnel: null },
  { name: "--color-neutral-500", funnel: null },
  { name: "--color-neutral-0", funnel: null },
];

const SEMANTIC_TOKENS = [
  "--surface-base",
  "--surface-raised",
  "--surface-overlay",
  "--text-primary",
  "--text-secondary",
  "--text-tertiary",
  "--accent-funnel",
  "--accent-funnel-text",
  "--accent-zantara",
  "--border-default",
  "--border-strong",
  "--nav-bg",
  "--footer-bg",
];

const FUNNELS: Exclude<Funnel, null>[] = ["visa", "kbli", "tax", "property"];
const THEMES: Theme[] = ["dark", "light", "editorial"];

export function TokenExplorer() {
  const { theme, setTheme, funnel, setFunnel } = useTheme();

  return (
    <main
      className="min-h-screen p-12 font-sans"
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        fontFamily: "var(--font-sans)",
      }}
    >
      {/* Header + controls */}
      <header className="flex items-center gap-6 mb-12 pb-6" style={{ borderBottom: "1px solid var(--border-default)" }}>
        <BZLogo variant="mark" size={56} />
        <h1 className="text-2xl font-bold tracking-tight">Token Explorer</h1>
        <span style={{ color: "var(--text-tertiary)" }} className="text-xs uppercase tracking-widest">
          @balizero/core · v0.1.0
        </span>

        <div className="ml-auto flex gap-3 items-center">
          <label className="text-xs uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>
            theme
          </label>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value as Theme)}
            className="px-3 py-1.5 rounded-md text-sm"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
            }}
          >
            {THEMES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>

          <label className="text-xs uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>
            funnel
          </label>
          <select
            value={funnel ?? ""}
            onChange={(e) => setFunnel((e.target.value || null) as Funnel)}
            className="px-3 py-1.5 rounded-md text-sm"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
            }}
          >
            <option value="">none</option>
            {FUNNELS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Color primitives */}
      <Section title="Color Primitives" hint="Layer 1 — raw values, never read directly by components">
        <div className="grid grid-cols-4 gap-4">
          {COLOR_PRIMITIVES.map((c) => (
            <div
              key={c.name}
              className="rounded-lg overflow-hidden"
              style={{ border: "1px solid var(--border-default)" }}
            >
              <div className="h-20" style={{ background: `var(${c.name})` }} />
              <div className="p-3" style={{ background: "var(--surface-raised)" }}>
                <code className="text-xs block font-mono">{c.name}</code>
                {c.funnel && (
                  <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--text-tertiary)" }}>
                    {c.funnel}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Semantic tokens */}
      <Section title="Semantic Tokens" hint="Layer 2 — intent-named, theme-overridable. What components actually read.">
        <div className="grid grid-cols-3 gap-3">
          {SEMANTIC_TOKENS.map((name) => (
            <div
              key={name}
              className="p-4 rounded-lg flex items-center gap-3"
              style={{ background: `var(${name})`, border: "1px solid var(--border-default)" }}
            >
              <div
                className="w-8 h-8 rounded"
                style={{ background: `var(${name})`, border: "1px solid var(--border-strong)" }}
              />
              <code className="text-xs font-mono">{name}</code>
            </div>
          ))}
        </div>
      </Section>

      {/* Per-funnel accent — leaf-scoped (the §10.4 demo) */}
      <Section
        title="Per-Funnel Accent — Leaf Scoping"
        hint="Each card on the left carries its own data-funnel attribute → fixed accent. The card on the right has none → reads the global funnel set by the dropdown above. Validates design §10.4."
      >
        <div className="grid grid-cols-5 gap-4">
          {FUNNELS.map((f) => (
            <FunnelDemoCard key={f} funnel={f} fixed />
          ))}
          <FunnelDemoCard funnel={funnel ?? "visa"} fixed={false} />
        </div>
      </Section>

      {/* Type scale */}
      <Section title="Typography" hint="--font-sans = Inter via next/font/google · 9-step size scale">
        <div className="space-y-3">
          {[
            { size: "--text-8xl", weight: 900, label: "8xl · 900" },
            { size: "--text-6xl", weight: 800, label: "6xl · 800" },
            { size: "--text-4xl", weight: 700, label: "4xl · 700" },
            { size: "--text-2xl", weight: 600, label: "2xl · 600" },
            { size: "--text-xl", weight: 500, label: "xl · 500" },
            { size: "--text-base", weight: 400, label: "base · 400" },
            { size: "--text-sm", weight: 400, label: "sm · 400" },
            { size: "--text-xs", weight: 300, label: "xs · 300" },
          ].map((t) => (
            <div key={t.label} className="flex items-baseline gap-6">
              <code
                className="text-xs font-mono w-24 shrink-0"
                style={{ color: "var(--text-tertiary)" }}
              >
                {t.label}
              </code>
              <span style={{ fontSize: `var(${t.size})`, fontWeight: t.weight }}>
                Bali Zero · The quick brown fox
              </span>
            </div>
          ))}
        </div>
      </Section>

      {/* Motion */}
      <Section title="Motion" hint="Resolves to 0s under prefers-reduced-motion (primitives.css)">
        <div className="space-y-2">
          {[
            { name: "--motion-duration-fast", ms: "150ms" },
            { name: "--motion-duration-standard", ms: "250ms" },
            { name: "--motion-duration-slow", ms: "400ms" },
            { name: "--motion-duration-shimmer", ms: "4000ms" },
          ].map((m) => (
            <div key={m.name} className="flex items-center gap-4">
              <code className="text-xs font-mono w-56" style={{ color: "var(--text-tertiary)" }}>
                {m.name}
              </code>
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                {m.ms}
              </span>
              <div
                className="h-2 rounded-full flex-1 max-w-md overflow-hidden"
                style={{ background: "var(--surface-raised)" }}
              >
                <div
                  className="h-full"
                  style={{
                    width: "60%",
                    background: "var(--accent-funnel)",
                    animation: `pulse ${m.ms} ease-in-out infinite alternate`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </Section>
    </main>
  );
}

function Section({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <h2 className="text-lg font-bold mb-1 tracking-tight">{title}</h2>
      <p className="text-xs mb-5" style={{ color: "var(--text-tertiary)" }}>
        {hint}
      </p>
      {children}
    </section>
  );
}

function FunnelDemoCard({
  funnel,
  fixed,
}: {
  funnel: Exclude<Funnel, null>;
  fixed: boolean;
}) {
  return (
    <article
      data-funnel={fixed ? funnel : undefined}
      className="rounded-xl p-6 transition-transform hover:-translate-y-1"
      style={{
        background: "var(--surface-raised)",
        border: fixed
          ? "1px solid var(--border-default)"
          : "2px dashed var(--accent-funnel)",
        boxShadow: "0 8px 32px color-mix(in srgb, var(--accent-funnel) 12%, transparent)",
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-2 h-2 rounded-full"
          style={{ background: "var(--accent-funnel)", boxShadow: "0 0 8px var(--accent-funnel)" }}
        />
        <span
          className="text-[10px] uppercase tracking-widest font-semibold"
          style={{ color: "var(--accent-funnel-text)" }}
        >
          {fixed ? funnel : "global"}
        </span>
      </div>
      <h3
        className="text-2xl font-extrabold tracking-tight mb-2"
        style={{ color: "var(--accent-funnel-text)" }}
      >
        {funnel.toUpperCase()}
      </h3>
      <p className="text-xs mb-4" style={{ color: "var(--text-secondary)" }}>
        {fixed ? `data-funnel="${funnel}" · leaf` : "no data-funnel · inherits global"}
      </p>
      <button
        className="px-4 py-2 rounded-md text-xs font-bold"
        style={{
          background: "var(--accent-funnel)",
          color: "var(--text-on-accent)",
          boxShadow: "0 4px 16px color-mix(in srgb, var(--accent-funnel) 35%, transparent)",
        }}
      >
        CTA →
      </button>
    </article>
  );
}
