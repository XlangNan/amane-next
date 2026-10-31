import { useCallback, useState } from "react";

/**
 * 列表多选 - Meta / Actor / Catalog 表共用.
 * `toggleAll` / `isAllSelected` 接收当前页 id, 避免把 pageIds 列入 hook 依赖.
 */
export function useIdSelection() {
  const [selected, setSelected] = useState<Set<number>>(() => new Set());

  const toggleOne = useCallback((id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAll = useCallback((pageIds: readonly number[]) => {
    setSelected((prev) => {
      if (pageIds.length > 0 && pageIds.every((id) => prev.has(id))) {
        return new Set();
      }
      return new Set(pageIds);
    });
  }, []);

  const isAllSelected = useCallback(
    (pageIds: readonly number[]) => pageIds.length > 0 && pageIds.every((id) => selected.has(id)),
    [selected],
  );

  const clear = useCallback(() => setSelected(new Set()), []);

  const selectedIds = [...selected];

  return {
    selected,
    selectedIds,
    toggleOne,
    toggleAll,
    isAllSelected,
    clear,
    setSelected,
  };
}
