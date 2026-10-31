/** 发行日 → 年月 (YYYY-MM); 仅有年份时返回 YYYY; 无法解析则原样返回. */
export function formatReleaseYearMonth(release: string | null | undefined): string | null {
  if (!release) return null;
  const trimmed = release.trim();
  if (!trimmed) return null;
  const match = /^(\d{4})(?:[-/.](\d{1,2}))?/.exec(trimmed);
  if (!match) return trimmed;
  const year = match[1];
  const month = match[2];
  if (!month) return year;
  return `${year}-${month.padStart(2, "0")}`;
}
