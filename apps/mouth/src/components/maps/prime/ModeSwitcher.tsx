'use client';

import { usePrimeNexus, type PrimeMode } from '@/contexts/PrimeNexusContext';

const MODES: { key: PrimeMode; label: string; icon: string; requiresAuth: boolean }[] = [
  { key: 'invest', label: 'Invest', icon: '💰', requiresAuth: false },
  { key: 'crm', label: 'CRM', icon: '👥', requiresAuth: true },
  { key: 'intel', label: 'Intel', icon: '📊', requiresAuth: true },
];

export function ModeSwitcher() {
  const { mode, setMode } = usePrimeNexus();

  return (
    <div className="flex items-center gap-1 bg-white/5 rounded-xl p-1 border border-white/10">
      {MODES.map((m) => (
        <button
          key={m.key}
          onClick={() => {
            if (m.requiresAuth) {
              // Check nz_access_token cookie — redirect to login if absent
              const hasAuth = document.cookie.includes('nz_access_token=');
              if (!hasAuth) {
                window.location.href = '/login?redirect=/prime';
                return;
              }
            }
            setMode(m.key);
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            mode === m.key
              ? 'bg-[#d4845a] text-white shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-white/5'
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
