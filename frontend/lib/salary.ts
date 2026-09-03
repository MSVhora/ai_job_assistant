export function salaryLine(
  min: number | null | undefined,
  max: number | null | undefined,
  currency: string | null | undefined,
): string | null {
  const salaryMin = min ?? null;
  const salaryMax = max ?? null;
  if (salaryMin === null && salaryMax === null) return null;
  const currencyPrefix = currency ? `${currency} ` : "";
  if (salaryMin !== null && salaryMax !== null && salaryMin !== salaryMax) {
    return `${currencyPrefix}${salaryMin.toLocaleString()} – ${salaryMax.toLocaleString()}`;
  }
  const value = (salaryMax ?? salaryMin) ?? 0;
  return `${currencyPrefix}${value.toLocaleString()}${salaryMin !== null && salaryMax === null ? "+" : ""}`;
}

export function scorePercent(score: number): string {
  return `${Math.round(score * 100)}%`;
}
