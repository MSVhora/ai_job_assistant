export function formatUsd(usd: number): string {
  if (usd <= 0) return "$0";
  if (usd < 0.0001) return "<$0.0001";
  return `$${usd.toFixed(usd < 0.01 ? 4 : 2)}`;
}
