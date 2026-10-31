const FOCUS_OFFSET_PX = 8;
const PANE_MIN_PX = 160;
const PANE_BOTTOM_GAP_PX = 8;

function ancestorScrollers(el: HTMLElement): HTMLElement[] {
  const out: HTMLElement[] = [];
  let cur = el.parentElement;
  while (cur != null) {
    const { overflowY } = getComputedStyle(cur);
    if (overflowY === "auto" || overflowY === "scroll") out.push(cur);
    cur = cur.parentElement;
  }
  return out;
}

function scrollRowToFocus(row: HTMLElement, scroller: HTMLElement, behavior: ScrollBehavior): void {
  const scrollerRect = scroller.getBoundingClientRect();
  const rowRect = row.getBoundingClientRect();
  const top = rowRect.top - scrollerRect.top + scroller.scrollTop - FOCUS_OFFSET_PX;
  scroller.scrollTo({ top: Math.max(0, top), behavior });
}

/** 按最近滚动容器剩余高度给展开面板封顶; focus 时沿祖先滚动容器把该行送到顶部附近. */
export function bindExpandedPane(
  row: HTMLElement,
  pane: HTMLElement,
  opts: { focus: boolean },
): () => void {
  const scrollers = ancestorScrollers(row);
  const nearest = scrollers[0] ?? document.documentElement;

  function sizePane() {
    const available =
      nearest.clientHeight -
      row.getBoundingClientRect().height -
      FOCUS_OFFSET_PX -
      PANE_BOTTOM_GAP_PX;
    pane.style.maxHeight = `${Math.max(PANE_MIN_PX, available)}px`;
  }

  function focusRow() {
    // 内层先瞬时对齐, 再让最外层平滑滚动; 否则点开子节点时根行仍钉在视口顶.
    for (let i = 0; i < scrollers.length; i += 1) {
      const scroller = scrollers[i];
      if (scroller == null) continue;
      const last = i === scrollers.length - 1;
      scrollRowToFocus(row, scroller, last ? "smooth" : "auto");
    }
  }

  sizePane();
  if (opts.focus) focusRow();
  const ro = new ResizeObserver(sizePane);
  ro.observe(nearest);
  return () => {
    ro.disconnect();
    pane.style.maxHeight = "";
  };
}
