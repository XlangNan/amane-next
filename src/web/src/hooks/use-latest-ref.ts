import { useEffect, useRef, type RefObject } from "react";

/** Ref that tracks the latest `value` after paint. Safe for event / observer callbacks. */
export function useLatestRef<T>(value: T): RefObject<T> {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  });
  return ref;
}
