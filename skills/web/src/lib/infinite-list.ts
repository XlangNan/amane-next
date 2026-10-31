/** Offset/limit 列表的 infinite query 下一页参数. */
export function nextOffsetPageParam<T extends { items: readonly unknown[]; total: number }>(
  lastPage: T,
  allPages: T[],
): number | undefined {
  const loaded = allPages.reduce((sum, p) => sum + p.items.length, 0);
  return loaded < lastPage.total ? loaded : undefined;
}
