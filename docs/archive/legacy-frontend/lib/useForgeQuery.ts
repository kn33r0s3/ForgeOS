"use client";

import { useEffect, useState, useCallback } from "react";
import { ForgeApiError } from "./api";

export type QueryState = "loading" | "ready" | "empty" | "error" | "offline";

/**
 * Shared data-fetching state machine for every screen in the app.
 * Distinguishes OFFLINE (no connection to the backend at all) from a
 * real HTTP error, and from EMPTY (backend reachable, just no data
 * yet — e.g. a fresh install with no opportunities). Nothing here
 * ever substitutes fabricated data for a failed fetch.
 */
export function useForgeQuery<T>(
  fetcher: () => Promise<T>,
  isEmpty: (data: T) => boolean = () => false,
  deps: unknown[] = []
) {
  const [state, setState] = useState<QueryState>("loading");
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setState("loading");
    fetcher()
      .then((result) => {
        setData(result);
        setError(null);
        setState(isEmpty(result) ? "empty" : "ready");
      })
      .catch((err) => {
        if (err instanceof ForgeApiError && err.status === 0) {
          setState("offline");
        } else {
          setState("error");
        }
        setError(err instanceof Error ? err.message : "Unknown error");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { state, data, error, reload: load };
}
