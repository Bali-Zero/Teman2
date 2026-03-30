const IDR_FORMATTER = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const USD_FORMATTER = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatIDR(amount: number): string {
  return IDR_FORMATTER.format(amount);
}

export function formatUSD(amount: number): string {
  return USD_FORMATTER.format(amount);
}

export function formatCurrency(
  amount: number,
  currency: string = "IDR",
): string {
  if (currency === "USD") return formatUSD(amount);
  return formatIDR(amount);
}
