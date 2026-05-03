'use client';

import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip,
} from 'recharts';
import type { OfficialDetail } from '@/lib/types';
import { formatRupiah } from '@/lib/format';

interface AssetECGProps {
  detail: OfficialDetail;
}

export function AssetECG({ detail }: AssetECGProps) {
  const chartData = useMemo(() => {
    return detail.lhkpn_years.map((year) => {
      const assets = detail.assets_by_year[year];
      return {
        tahun: year,
        total: assets?.total ?? 0,
        property: assets?.properties.reduce((s, p) => s + p.nilai, 0) ?? 0,
        vehicle: assets?.vehicles.reduce((s, v) => s + v.nilai, 0) ?? 0,
        cash: assets?.cash ?? 0,
      };
    });
  }, [detail]);

  return (
    <div>
      <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
        ASSET ECG
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis
            dataKey="tahun"
            tick={{ fill: '#4a5568', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
          />
          <YAxis
            tickFormatter={(v: number) => `${(v / 1e9).toFixed(1)}B`}
            tick={{ fill: '#4a5568', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            width={50}
          />
          <Tooltip
            contentStyle={{
              background: 'rgba(20, 28, 43, 0.9)',
              border: '1px solid rgba(212, 132, 90, 0.2)',
              borderRadius: 6,
              fontSize: 11,
              fontFamily: 'JetBrains Mono',
            }}
            formatter={(value: number) => formatRupiah(value)}
          />
          <Line type="monotone" dataKey="total" stroke="#d4845a" strokeWidth={2}
            dot={{ r: 4, fill: '#d4845a', strokeWidth: 0 }}
            activeDot={{ r: 6, fill: '#d4845a', stroke: '#1d273b', strokeWidth: 2 }}
          />
          <Line type="monotone" dataKey="property" stroke="#8b9cf7" strokeWidth={1} dot={false} />
          <Line type="monotone" dataKey="vehicle" stroke="#e8a849" strokeWidth={1} dot={false} />
          <Line type="monotone" dataKey="cash" stroke="#5ec490" strokeWidth={1} dot={false} />
        </LineChart>
      </ResponsiveContainer>

      <div className="flex gap-4 mt-2">
        <LegendItem color="#d4845a" label="Total Harta" />
        <LegendItem color="#8b9cf7" label="Tanah/Bangunan" />
        <LegendItem color="#e8a849" label="Kendaraan" />
        <LegendItem color="#5ec490" label="Kas" />
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-3 h-0.5" style={{ background: color }} />
      <span className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)]">{label}</span>
    </div>
  );
}
