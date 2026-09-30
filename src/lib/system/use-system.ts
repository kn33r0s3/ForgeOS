import { useCallback, useEffect, useState } from "react";
import {
  clearGuestState,
  emptyState,
  loadGuestState,
  saveState,
  type SystemState,
} from "./state";
import { authEnabled } from "@/lib/auth/client";
import { useCurrentUserState } from "@/lib/auth/use-current-user";
import {
  clearPersonalContext,
  getPersonalContext,
  savePersonalContext,
} from "./personal-context";

function browserStorage(kind: "session" | "local"): Storage | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    return kind === "session" ? window.sessionStorage : window.localStorage;
  } catch {
    return undefined;
  }
}

/**
 * Signed-in context is fetched and written only through owner-scoped server
 * functions. A guest's temporary context stays in tab-scoped session storage.
 */
export function useSystemState() {
  const [state, setState] = useState<SystemState | null>(null);
  const [guestState, setGuestState] = useState<SystemState | null>(null);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<"guest" | "account">("guest");
  const [error, setError] = useState<string | null>(null);
  const [storageWarning, setStorageWarning] = useState<string | null>(null);
  const [reviewingTemporary, setReviewingTemporary] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const { user, isPending } = useCurrentUserState();
  const userId = authEnabled && !isPending && user && !user.isDevFallback ? user.id : null;
  const scopeKey = authEnabled && isPending ? null : userId ? `account:${userId}` : "guest";
  const requestKey = scopeKey === null ? null : `${scopeKey}:${reloadKey}`;
  const contextReady = ready && requestKey !== null && loadedKey === requestKey;

  useEffect(() => {
    if (authEnabled && isPending) {
      setReady(false);
      return;
    }

    const nextScopeKey = userId ? `account:${userId}` : "guest";
    const nextRequestKey = `${nextScopeKey}:${reloadKey}`;
    const temporary = loadGuestState(browserStorage("session"), browserStorage("local"));
    setGuestState(temporary);
    setReviewingTemporary(false);
    setError(null);
    setStorageWarning(null);

    if (userId) {
      setMode("account");
      setState(null);
      setReady(false);
      void getPersonalContext()
        .then((context) => setState(context))
        .catch(() => setError("Private context could not be loaded. Nothing is shown as empty or saved."))
        .finally(() => {
          setLoadedKey(nextRequestKey);
          setReady(true);
        });
      return;
    }

    setMode("guest");
    setState(temporary);
    setLoadedKey(nextRequestKey);
    setReady(true);
  }, [userId, isPending, reloadKey]);

  const update = useCallback(async (mutate: (draft: SystemState) => SystemState) => {
    const next = { ...mutate(state ?? emptyState()), updatedAt: new Date().toISOString() };
    if (mode === "account" && userId) {
      try {
        const saved = await savePersonalContext({ data: next });
        setState(saved);
        if (reviewingTemporary) {
          clearGuestState(browserStorage("session"), browserStorage("local"));
          setGuestState(null);
          setReviewingTemporary(false);
        }
        setError(null);
      } catch (cause) {
        setError("Private context could not be saved. Please retry; it was not added to public Hami data.");
        throw cause;
      }
      return;
    }

    setState(next);
    setGuestState(next);
    if (!saveState(browserStorage("session"), next)) {
      setStorageWarning("This browser could not retain the temporary context in tab storage. It may be lost when the tab closes or refreshes.");
    }
  }, [mode, reviewingTemporary, state, userId]);

  const reset = useCallback(async () => {
    if (mode === "account" && userId) {
      try {
        await clearPersonalContext();
      } catch (cause) {
        setError("Private context could not be cleared. Please retry.");
        throw cause;
      }
    }
    clearGuestState(browserStorage("session"), browserStorage("local"));
    setState(null);
    setGuestState(null);
    setError(null);
  }, [mode, userId]);

  const useTemporaryContext = useCallback(() => {
    if (mode === "account" && guestState) {
      setState(guestState);
      setReviewingTemporary(true);
    }
  }, [mode, guestState]);

  return {
    state: contextReady ? state : null,
    guestState,
    ready: contextReady,
    mode,
    error,
    storageWarning,
    update,
    reset,
    useTemporaryContext,
    retry: () => setReloadKey((value) => value + 1),
  };
}
