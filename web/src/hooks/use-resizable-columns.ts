import { useCallback, useRef, type MouseEvent as ReactMouseEvent } from "react";
import { useLatestRef } from "@/hooks/use-latest-ref";
import { useResettingState } from "@/hooks/use-resetting-state";

export type ColumnWidths<K extends string> = Partial<Record<K, number>>;

interface UseResizableColumnsOptions<K extends string> {
  defaults: Record<K, number>;
  /** 持久化的用户列宽; 缺省列采用 defaults (或调用方对 flex 列特殊处理). */
  stored?: ColumnWidths<K>;
  onChange?: (widths: ColumnWidths<K>) => void;
  minWidth?: number;
}

interface ResizeHandleProps {
  onMouseDown: (event: ReactMouseEvent) => void;
  onDoubleClick: () => void;
}

/**
 * 表头拖拽调列宽. 双击清除该列的用户覆盖 (回到默认/自适应).
 * 拖拽起点用 th 实测宽度, 便于 flex 列首次拖拽.
 */
export function useResizableColumns<K extends string>({
  defaults,
  stored,
  onChange,
  minWidth = 48,
}: UseResizableColumnsOptions<K>) {
  const [widths, setWidths] = useResettingState<ColumnWidths<K>>(() => ({ ...stored }), stored);
  const widthsRef = useLatestRef(widths);
  const onChangeRef = useLatestRef(onChange);
  const dragRef = useRef<{
    key: K;
    startX: number;
    startWidth: number;
  } | null>(null);

  /** 用户覆盖优先, 否则默认 px. 调用方对 flex 列可忽略默认, 不设置 w. */
  const effectiveWidth = useCallback(
    (key: K): number => widths[key] ?? defaults[key],
    [widths, defaults],
  );

  const hasCustomWidth = useCallback((key: K): boolean => widths[key] != null, [widths]);

  const resetColumn = useCallback(
    (key: K) => {
      const next = { ...widthsRef.current };
      delete next[key];
      widthsRef.current = next;
      setWidths(next);
      onChangeRef.current?.(next);
    },
    [onChangeRef, setWidths, widthsRef],
  );

  const getResizeHandleProps = useCallback(
    (key: K): ResizeHandleProps => ({
      onDoubleClick: () => resetColumn(key),
      onMouseDown: (event: ReactMouseEvent) => {
        event.preventDefault();
        event.stopPropagation();
        const th = (event.currentTarget as HTMLElement).closest("th");
        const measured = th?.getBoundingClientRect().width;
        dragRef.current = {
          key,
          startX: event.clientX,
          startWidth:
            measured && measured > 0 ? measured : (widthsRef.current[key] ?? defaults[key]),
        };

        const onMove = (ev: MouseEvent) => {
          const drag = dragRef.current;
          if (!drag) return;
          const delta = ev.clientX - drag.startX;
          const nextWidth = Math.max(minWidth, Math.round(drag.startWidth + delta));
          setWidths((prev) => ({ ...prev, [drag.key]: nextWidth }));
        };

        const onUp = (ev: MouseEvent) => {
          const drag = dragRef.current;
          dragRef.current = null;
          document.removeEventListener("mousemove", onMove);
          document.removeEventListener("mouseup", onUp);
          document.body.style.cursor = "";
          document.body.style.userSelect = "";
          if (!drag) return;
          const delta = ev.clientX - drag.startX;
          const nextWidth = Math.max(minWidth, Math.round(drag.startWidth + delta));
          const next = { ...widthsRef.current, [drag.key]: nextWidth };
          widthsRef.current = next;
          setWidths(next);
          onChangeRef.current?.(next);
        };

        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
      },
    }),
    [defaults, minWidth, onChangeRef, resetColumn, setWidths, widthsRef],
  );

  return { effectiveWidth, hasCustomWidth, getResizeHandleProps };
}
