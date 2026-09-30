import { useCallback, useEffect, useState } from "react";
import {
  STORAGE_KEY,
  clearState,
  emptyState,
  loadState,
  saveState,
  type SystemState,
} from "./state";

function browserStorage(): Storage | undefined {
  return typeof window === "undefined" ? undefined : window.localStorage;
}

/**
 * The person's System state, owned on their device. `ready` is false during
 * SSR/first paint so the UI never flashes a wrong "empty" System.
 */
export function useSystemState() {
  const [state, setState] = useState<SystemState | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setState(loadState(browserStorage()));
    setReady(true);
    const onStorage = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY) setState(loadState(browserStorage()));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const update = useCallback((mutate: (draft: SystemState) => SystemState) => {
    setState((current) => {
      const next = { ...mutate(current ?? emptyState()), updatedAt: new Date().toISOString() };
      saveState(browserStorage(), next);
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    clearState(browserStorage());
    setState(null);
  }, []);

  return { state, ready, update, reset };
}
