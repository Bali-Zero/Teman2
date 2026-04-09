export function formatRupiah(value: number): string {
  if (value === 0) return 'Rp 0';
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000_000) return `Rp ${(value / 1e12).toFixed(1)}T`;
  if (abs >= 1_000_000_000) return `Rp ${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1_000_000) return `Rp ${(value / 1e6).toFixed(0)}M`;
  return `Rp ${value.toLocaleString('id-ID')}`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

export function formatDelta(pct: number): string {
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(0)}%`;
}
