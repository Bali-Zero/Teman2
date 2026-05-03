'use client';

import { formatRupiah } from '@/lib/format';
import type { PropertyItem, VehicleItem } from '@/lib/types';

export function PropertyCards({ properties }: { properties: PropertyItem[] }) {
  if (properties.length === 0) return null;
  return (
    <div>
      <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
        PROPERTIES · {properties.length}
      </div>
      <div className="space-y-2">
        {properties.map((p, i) => (
          <div key={i} className="p-3 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
            <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-primary)]">
              {p.lokasi || 'Lokasi tidak diketahui'}
            </div>
            <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-1">
              {p.luas_tanah_m2}m² tanah · {p.luas_bangunan_m2}m² bangunan
            </div>
            <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-copper)] mt-1">
              {formatRupiah(p.nilai)} · {p.sumber || '—'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function VehicleCards({ vehicles }: { vehicles: VehicleItem[] }) {
  if (vehicles.length === 0) return null;
  return (
    <div>
      <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
        VEHICLES · {vehicles.length}
      </div>
      <div className="space-y-2">
        {vehicles.map((v, i) => (
          <div key={i} className="p-3 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
            <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-primary)]">
              {v.jenis} — {v.merk_model}
            </div>
            <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-1">
              Tahun {v.tahun_perolehan}
            </div>
            <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-copper)] mt-1">
              {formatRupiah(v.nilai)} · {v.sumber || '—'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
