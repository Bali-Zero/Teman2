import { ThemeScope } from "@balizero/core/components/ThemeProvider";

// Phase 2 migration (design §8 step 4):
//   - data-funnel="kbli" → all descendants read --accent-funnel = gold (--color-gold-500)
//   - Montserrat dropped → Inter inherited via --font-sans loaded in root layout
//   - Legacy --kbli-accent / --kbli-red / --kbli-ink remapped to DS tokens in
//     kbli-theme.css; consumer pages keep existing inline reads, colors shift
//     to gold automatically.
export default function KBLILayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ThemeScope
      funnel="kbli"
      className="relative z-[1] mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8"
    >
      {children}
    </ThemeScope>
  );
}
