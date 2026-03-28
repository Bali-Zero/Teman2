import Link from 'next/link';
import type { KBLISection } from '@/lib/kbli-types';
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
} from 'lucide-react';

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

  // Size tier based on code count relative to max
  function getSizeTier(count: number): 'xl' | 'lg' | 'md' | 'sm' {
    const ratio = count / maxCount;
    if (ratio >= 0.6) return 'xl';
    if (ratio >= 0.3) return 'lg';
    if (ratio >= 0.1) return 'md';
    return 'sm';
  }

  const remainder = sections.length % 4;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {sections.map((s, i) => {
        const tier = getSizeTier(s.codeCount);
        const isLastOrphan = remainder === 1 && i === sections.length - 1;

        // Bar fill width
        const barPct = Math.max(8, Math.round((s.codeCount / maxCount) * 100));

        // Accent intensity based on tier
        const accentOpacity =
          tier === 'xl'
            ? 'opacity-100'
            : tier === 'lg'
              ? 'opacity-80'
              : tier === 'md'
                ? 'opacity-60'
                : 'opacity-40';

        // Icon size
        const iconSize =
          tier === 'xl'
            ? 'text-3xl'
            : tier === 'lg'
              ? 'text-2xl'
              : tier === 'md'
                ? 'text-xl'
                : 'text-lg';

        // Name size
        const nameSize =
          tier === 'xl'
            ? 'text-sm font-bold'
            : tier === 'lg'
              ? 'text-sm font-semibold'
              : 'text-xs font-medium';

        return (
          <Link
            key={s.id}
            href={`/kbli/sectors/${s.id}`}
            aria-label={`${s.nameEn} — Section ${s.id}, ${s.codeCount} ${s.codeCount === 1 ? 'code' : 'codes'}`}
            className={`group relative rounded-2xl border border-[#3f3f46] bg-[#27272a] p-4.5
                       transition-all duration-500 hover:border-transparent hover:shadow-[0_8px_32px_rgba(212,132,90,0.2)] hover:-translate-y-1
                       animate-fade-in-up holographic-card flex flex-col
                       ${isLastOrphan ? 'col-span-2 sm:col-span-1' : ''}`}
            style={{ animationDelay: `${i * 60}ms` }}
          >
            {/* Icon & Section Code */}
            <div className="flex items-start justify-between mb-2">
              <div
                className={`inline-flex items-center justify-center rounded-xl bg-white/5 border border-white/10 shadow-[inset_0_0_20px_rgba(255,255,255,0.05)] text-zinc-400 group-hover:text-[#d4845a] group-hover:bg-[#d4845a]/20 group-hover:border-[#d4845a]/50 group-hover:shadow-[0_0_30px_rgba(212,132,90,0.3)] transition-all duration-500 ${iconSize === 'text-2xl' || iconSize === 'text-3xl' ? 'h-12 w-12' : 'h-10 w-10'}`}
              >
                <div
                  aria-hidden="true"
                  className={`drop-shadow-md group-hover:scale-110 transition-transform duration-500 flex items-center justify-center ${iconSize === 'text-2xl' || iconSize === 'text-3xl' ? 'scale-125' : 'scale-100'}`}
                >
                  {SECTOR_ICONS[s.id] || <HelpCircle strokeWidth={1.5} />}
                </div>
              </div>
              <div className="text-[10px] font-bold tracking-wider uppercase text-[#d4845a] opacity-80 group-hover:opacity-100 transition-opacity">
                Section {s.id}
              </div>
            </div>

            {/* Sector Name */}
            <div className="text-sm font-bold leading-snug text-white transition-colors group-hover:text-[#d4845a] flex-grow drop-shadow-sm mt-1">
              {s.nameEn}
            </div>

            {/* Code count + visual bar */}
            <div className="mt-5">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[11px] font-medium text-zinc-400 group-hover:text-zinc-300 transition-colors">
                  {s.codeCount} {s.codeCount === 1 ? 'code' : 'codes'}
                </span>
                {tier === 'xl' && (
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#d4845a] animate-pulse">
                    Large
                  </span>
                )}
              </div>

              {/* Dynamic Progress Bar */}
              <div className="relative h-1 w-full overflow-hidden rounded-full bg-[#3f3f46] shadow-inner">
                {/* Glowing Track */}
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-[#d4845a] via-[#a855f7] to-[#3b82f6] opacity-60 group-hover:opacity-100 transition-opacity"
                  style={{
                    width: `${barPct}%`,
                    animation: 'progress-grow 1.2s ease-out forwards',
                  }}
                />
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-white opacity-0 blur-[2px] group-hover:opacity-60 transition-opacity mix-blend-overlay"
                  style={{ width: `${barPct}%` }}
                />
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
