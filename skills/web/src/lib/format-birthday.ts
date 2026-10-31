/** 从生日字符串估算年龄 (周岁); 无法解析返回 null. `asOf` 为计算基准日 (默认今天). */
export function ageFromBirthday(
  birthday: string | null | undefined,
  asOf: Date = new Date(),
): number | null {
  if (!birthday) return null;
  const trimmed = birthday.trim();
  if (!trimmed) return null;
  const match = /^(\d{4})(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?/.exec(trimmed);
  if (!match) return null;
  const year = Number(match[1]);
  const month = match[2] ? Number(match[2]) : 1;
  const day = match[3] ? Number(match[3]) : 1;
  if (!Number.isFinite(year) || year < 1900 || year > asOf.getFullYear() + 1) return null;
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;

  let age = asOf.getFullYear() - year;
  const hadBirthday =
    asOf.getMonth() + 1 > month || (asOf.getMonth() + 1 === month && asOf.getDate() >= day);
  if (!hadBirthday) age -= 1;
  return age >= 0 && age < 150 ? age : null;
}

export function parseDateLike(value: string | null | undefined): Date | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const match = /^(\d{4})(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?/.exec(trimmed);
  if (!match) return null;
  const year = Number(match[1]);
  const month = match[2] ? Number(match[2]) : 1;
  const day = match[3] ? Number(match[3]) : 1;
  if (!Number.isFinite(year) || month < 1 || month > 12 || day < 1 || day > 31) return null;
  const d = new Date(year, month - 1, day);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function ageAtRelease(
  birthday: string | null | undefined,
  release: string | null | undefined,
): number | null {
  const asOf = parseDateLike(release);
  if (!asOf) return null;
  return ageFromBirthday(birthday, asOf);
}

/** 生日展示: `1991-01-01(34岁)`; 无年龄或无法算年龄则原样. */
export function formatBirthdayWithAge(
  birthday: string | null | undefined,
  ageSuffix: (age: number) => string,
  asOf: Date = new Date(),
): string | null {
  if (!birthday?.trim()) return null;
  const age = ageFromBirthday(birthday, asOf);
  if (age == null) return birthday.trim();
  return `${birthday.trim()}${ageSuffix(age)}`;
}
