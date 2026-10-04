/**
 * Short-lived read cache for the public projections this site displays.
 *
 * Every page loads its data in a `useEffect`, so without a cache the same four
 * endpoints are re-requested on each visit and two pages can request
 * `/api/forge/runtime` at the same moment. This module does exactly two things:
 *
 * 1. **TTL reuse** — a settled read is served from memory for `FRESH_TTL_MS`, so
 *    moving between pages (or going back) paints from memory instead of holding
 *    the page in skeleton state for another round trip.
 * 2. **In-flight dedupe** — callers that ask for the same key while a request is
 *    still open share that one request.
 *
 * Two rules keep this honest:
 *
 * - Anything that must reflect a just-performed action passes `{ fresh: true }`,
 *   which always goes to the network: "Retry"/"Refresh" buttons and post-action
 *   reads never receive a cached failure or a stale snapshot.
 * - A `null` result means "could not be checked", so it is cached for
 *   `MISSING_TTL_MS` only — long enough to stop a retry storm while the service
 *   is down, short enough that recovery is picked up quickly.
 *
 * Nothing here is authorization, evidence, or an outcome record; these are
 * public read-only projections, so reusing a response for seconds changes no
 * state and makes no claim about the system.
 */
export type CacheScope = { fresh?: boolean };

type Entry = { at: number; value: unknown };

export type ReadCache = {
  read: <T>(key: string, load: () => Promise<T>, scope?: CacheScope) => Promise<T>;
  invalidate: (prefix?: string) => void;
  reset: () => void;
};

export type ReadCacheOptions = {
  /** `false` disables caching entirely, running every read straight through. */
  enabled?: boolean;
  /** Injectable clock so TTL behaviour is testable without sleeping. */
  now?: () => number;
  freshTtlMs?: number;
  missingTtlMs?: number;
};

export function createReadCache({
  enabled = true,
  now = () => Date.now(),
  freshTtlMs = 20_000,
  missingTtlMs = 5_000,
}: ReadCacheOptions = {}): ReadCache {
  const entries = new Map<string, Entry>();
  const inFlight = new Map<string, Promise<unknown>>();
  // A `fresh` read can start while an older request for the key is still open;
  // the newest generation owns the in-flight entry, so a late finisher cannot
  // clear a request that is still running.
  const generations = new Map<string, number>();

  function read<T>(key: string, load: () => Promise<T>, { fresh = false }: CacheScope = {}): Promise<T> {
    if (!enabled) return load();

    if (!fresh) {
      const entry = entries.get(key);
      if (entry) {
        const ttl = entry.value === null ? missingTtlMs : freshTtlMs;
        if (now() - entry.at < ttl) return Promise.resolve(entry.value as T);
      }
      const pending = inFlight.get(key);
      if (pending) return pending as Promise<T>;
    }

    const generation = (generations.get(key) ?? 0) + 1;
    generations.set(key, generation);
    const request = load()
      .then((value) => {
        // A request that finished after an invalidate() (or a newer
        // generation) must not repopulate the cache with data the caller
        // already dropped: the newest generation owns the entry.
        if (generations.get(key) !== generation) return value;
        // Even a `fresh: true` read refreshes the shared entry, so the next
        // page visit starts from what this caller just observed.
        entries.set(key, { at: now(), value });
        return value;
      })
      .finally(() => {
        if (generations.get(key) !== generation) return;
        generations.delete(key);
        if (inFlight.get(key) === request) inFlight.delete(key);
      });
    inFlight.set(key, request);
    return request;
  }

  function invalidate(prefix?: string) {
    const keys = new Set<string>([
      ...entries.keys(),
      ...inFlight.keys(),
      ...generations.keys(),
    ]);
    for (const key of keys) {
      if (prefix && !key.startsWith(prefix)) continue;
      entries.delete(key);
      inFlight.delete(key);
      // Bump the generation so a request that started before this
      // invalidation cannot write its (now stale) result back into the cache
      // when it settles. The awaiting caller still receives the data it
      // asked for — only the shared entry is withheld.
      generations.set(key, (generations.get(key) ?? 0) + 1);
    }
  }

  function reset() {
    entries.clear();
    inFlight.clear();
    generations.clear();
  }

  return { read, invalidate, reset };
}

/**
 * The instance the site uses. Module-level state is only safe in the browser:
 * the server bundle is shared by every request, so SSR reads run uncached
 * rather than leaking one visitor's response into another request's render.
 */
const readCache = createReadCache({ enabled: typeof window !== "undefined" });

/**
 * Resolve `key` from cache when a recent value exists, otherwise run `load()`
 * once and share that promise with any concurrent caller for the same key.
 *
 * Thrown errors are never cached, so a failing endpoint is retried by whichever
 * caller asks next — the exception stays a live signal.
 */
export function cachedRead<T>(key: string, load: () => Promise<T>, scope: CacheScope = {}): Promise<T> {
  return readCache.read(key, load, scope);
}

/** Drop cached reads so the next `cachedRead` for that prefix hits the network. */
export function invalidateReadCache(prefix?: string) {
  readCache.invalidate(prefix);
}
