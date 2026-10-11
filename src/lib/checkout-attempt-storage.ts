/** Shared, fail-closed storage for a buyer's unresolved checkout identity.

The key lets the next page or a refreshed tab reconcile the SAME provider
attempt. Losing it must never be mistaken for a successfully cleared attempt.
No buyer details or provider credentials are persisted here.
*/
export type CheckoutProvider = "esewa" | "khalti";
export type StoredCheckoutAttempt = { key: string; provider: CheckoutProvider };
export type StoredCheckoutAttemptRead =
  | { state: "stored"; attempt: StoredCheckoutAttempt }
  | { state: "absent" }
  | { state: "unavailable" }
  | { state: "invalid" };

export type CheckoutKeyRandomSource = {
  uuid?: () => string;
  randomBytes?: (length: number) => Uint8Array;
};

type CheckoutAttemptStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
type StorageProvider = () => CheckoutAttemptStorage;

function browserSessionStorage(): CheckoutAttemptStorage {
  return window.sessionStorage;
}

function browserCheckoutKeyRandomSource(): CheckoutKeyRandomSource {
  const cryptoSource = typeof window === "undefined" ? undefined : window.crypto;
  return {
    uuid: typeof cryptoSource?.randomUUID === "function"
      ? () => cryptoSource.randomUUID()
      : undefined,
    randomBytes: typeof cryptoSource?.getRandomValues === "function"
      ? (length) => cryptoSource.getRandomValues(new Uint8Array(length))
      : undefined,
  };
}

/** Generate an idempotency key only from a cryptographic browser random source. */
export function createCheckoutAttemptKey(
  source: CheckoutKeyRandomSource = browserCheckoutKeyRandomSource(),
): string | null {
  try {
    const uuid = source.uuid?.();
    if (typeof uuid === "string" && uuid.length >= 16 && uuid.length <= 128) {
      return uuid;
    }
  } catch {
    // Try the cryptographic random-bytes API if UUID generation is unavailable.
  }

  try {
    const bytes = source.randomBytes?.(32);
    if (!(bytes instanceof Uint8Array) || bytes.length !== 32) return null;
    return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  } catch {
    return null;
  }
}

export function checkoutAttemptStorageKey(offerId: number): string {
  return `hami:checkout-attempt:${offerId}`;
}

export function readStoredCheckoutAttempt(
  offerId: number,
  getStorage: StorageProvider = browserSessionStorage,
): StoredCheckoutAttemptRead {
  let raw: string | null;
  try {
    raw = getStorage().getItem(checkoutAttemptStorageKey(offerId));
  } catch {
    return { state: "unavailable" };
  }
  if (raw === null) return { state: "absent" };
  if (raw.length === 0) return { state: "invalid" };

  let value: Partial<StoredCheckoutAttempt>;
  try {
    value = JSON.parse(raw) as Partial<StoredCheckoutAttempt>;
  } catch {
    return { state: "invalid" };
  }
  if (
    typeof value.key !== "string" ||
    value.key.length < 16 ||
    value.key.length > 128 ||
    (value.provider !== "esewa" && value.provider !== "khalti")
  ) return { state: "invalid" };
  return {
    state: "stored",
    attempt: { key: value.key, provider: value.provider },
  };
}

export function writeStoredCheckoutAttempt(
  offerId: number,
  attempt: StoredCheckoutAttempt,
  getStorage: StorageProvider = browserSessionStorage,
): boolean {
  try {
    getStorage().setItem(checkoutAttemptStorageKey(offerId), JSON.stringify(attempt));
    return true;
  } catch {
    return false;
  }
}

export function clearStoredCheckoutAttempt(
  offerId: number,
  getStorage: StorageProvider = browserSessionStorage,
): boolean {
  try {
    const storage = getStorage();
    const key = checkoutAttemptStorageKey(offerId);
    storage.removeItem(key);
    return storage.getItem(key) === null;
  } catch {
    return false;
  }
}
