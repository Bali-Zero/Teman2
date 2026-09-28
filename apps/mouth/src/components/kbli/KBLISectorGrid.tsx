import Link from "next/link";
import type { KBLISection } from "@/lib/kbli-types";
import {
  Tractor,
  Pickaxe,
  Factory,
  Zap,
  Droplets,
  HardHat,
  Store,
  Truck,
  Utensils,
  Wifi,
  Landmark,
  Building2,
  Microscope,
  Briefcase,
  ShieldCheck,
  GraduationCap,
  Stethoscope,
  Palette,
  Wrench,
  Home,
  Globe2,
  HelpCircle,
} from "lucide-react";

const SECTOR_ICONS: Record<string, React.ReactNode> = {
  A: <Tractor strokeWidth={1.5} />,
  B: <Pickaxe strokeWidth={1.5} />,
  C: <Factory strokeWidth={1.5} />,
  D: <Zap strokeWidth={1.5} />,
  E: <Droplets strokeWidth={1.5} />,
  F: <HardHat strokeWidth={1.5} />,
  G: <Store strokeWidth={1.5} />,
  H: <Truck strokeWidth={1.5} />,
  I: <Utensils strokeWidth={1.5} />,
  J: <Wifi strokeWidth={1.5} />,
  K: <Landmark strokeWidth={1.5} />,
  L: <Building2 strokeWidth={1.5} />,
  M: <Microscope strokeWidth={1.5} />,
  N: <Briefcase strokeWidth={1.5} />,
  O: <ShieldCheck strokeWidth={1.5} />,
  P: <GraduationCap strokeWidth={1.5} />,
  Q: <Stethoscope strokeWidth={1.5} />,
  R: <Palette strokeWidth={1.5} />,
  S: <Wrench strokeWidth={1.5} />,
  T: <Home strokeWidth={1.5} />,
  U: <Globe2 strokeWidth={1.5} />,
};
export function KBLISectorGrid({ sections }: { sections: KBLISection[] }) {
  const maxCount = Math.max(...sections.map((s) => s.codeCount));

  // Specimen cards on paper (BRIEF-v2 §3.4): the section letter and the count
  // set as figures, the bar measured against the largest section in the one
  // structure ink the dial uses (council v2: a single-ink instrument).
  return (
    <div
      data-kbli-sector-grid=""
      className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--kbli-radius-lg)] border border-[var(--kbli-border)] bg-[var(--kbli-border)] sm:grid-cols-3 lg:grid-cols-4"
    >
      {sections.map((s) => {
        const barPct = Math.max(4, Math.round((s.codeCount / maxCount) * 100));

        return (
          <Link
            key={s.id}
            href={`/kbli/sectors/${s.id}`}
            className="group relative flex min-h-[132px] flex-col bg-[var(--kbli-bg-surface)] p-4 no-underline transition-colors hover:bg-[var(--kbli-bg-card-hover)] focus-visible:z-10 focus-visible:outline-[3px] focus-visible:outline-offset-[-3px] focus-visible:outline-[var(--kbli-accent)]"
          >
            <div className="flex items-start justify-between">
              <span className="kbli-figure text-[26px] leading-none text-[var(--kbli-text-primary)]">
                {s.id}
              </span>
              <span
                aria-hidden="true"
                className="flex h-6 w-6 items-center justify-center text-[var(--kbli-text-secondary)] [&>svg]:h-5 [&>svg]:w-5"
              >
                {SECTOR_ICONS[s.id] || <HelpCircle strokeWidth={1.5} />}
              </span>
            </div>

            <div className="mt-3 flex-grow text-[13.5px] font-semibold leading-snug text-[var(--kbli-text-primary)] group-hover:text-[var(--kbli-accent)]">
              {s.nameEn}
            </div>

            <div className="mt-3">
              <div className="kbli-figure mb-1 text-[15px] text-[var(--kbli-text-primary)]">
                {s.codeCount} {s.codeCount === 1 ? "code" : "codes"}
              </div>
              <div
                aria-hidden="true"
                className="relative h-[3px] w-full bg-[var(--kbli-bg-secondary)]"
              >
                <div
                  className="absolute inset-y-0 left-0"
                  style={{
                    width: `${barPct}%`,
                    background: "var(--r19-structure, #233D52)",
                  }}
                />
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
