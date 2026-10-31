import { useState } from "react";

/**
 * Manages a local value that commits to the form field on blur/change.
 * Useful for numeric inputs where intermediate typing shouldn't update the form.
 */
export function useCommitOnChange<T>(initialValue: T, onCommit: (value: T) => void) {
  const [localValue, setLocalValue] = useState(initialValue);

  const commit = () => {
    if (localValue !== initialValue) {
      onCommit(localValue);
    }
  };

  return { localValue, setLocalValue, commit };
}
