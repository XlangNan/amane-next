import { useEffect, useState } from "react";

interface BatchedRenderProps<TKey extends string, T> {
  items: [TKey, T][];
  renderItem: (key: TKey, item: T) => React.ReactNode;
  batchSize?: number;
  delay?: number;
}

/**
 * Renders items in batches to avoid blocking the main thread on large forms.
 *
 * Initially renders `batchSize` items, then incrementally adds more
 * on each timeout tick until all items are visible.
 */
export function BatchedRender<TKey extends string, T>({
  items,
  renderItem,
  batchSize = 10,
  delay = 0,
}: BatchedRenderProps<TKey, T>) {
  const [visibleCount, setVisibleCount] = useState(batchSize);

  const visibleItems = items.slice(0, visibleCount);

  useEffect(() => {
    if (visibleCount >= items.length) return;

    const timer = setTimeout(() => {
      setVisibleCount((prev) => Math.min(prev + batchSize, items.length));
    }, delay);

    return () => clearTimeout(timer);
  }, [visibleCount, items.length, batchSize, delay]);

  return (
    <>
      {visibleItems.map(([key, item]) => (
        <span key={key}>{renderItem(key, item)}</span>
      ))}
    </>
  );
}
