import { useState, type Dispatch, type SetStateAction } from "react";

/**
 * Local state that re-initializes when `resetKey` changes.
 * Adjustment happens during render (React-allowed), not in an effect.
 */
export function useResettingState<T>(
  factory: () => T,
  resetKey: unknown,
): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState(factory);
  const [prevKey, setPrevKey] = useState(resetKey);
  if (prevKey !== resetKey) {
    setPrevKey(resetKey);
    setState(factory());
  }
  return [state, setState];
}
