export function formatPrice(pricePerAre: number): string {
  if (!pricePerAre || pricePerAre === 0) return "—";
  const billions = pricePerAre / 1_000_000_000;
  if (billions >= 1) return `Rp ${billions.toFixed(1)}B / are`;
  const millions = pricePerAre / 1_000_000;
  return `Rp ${millions.toFixed(0)}M / are`;
}
