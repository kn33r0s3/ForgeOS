/** Shared, fail-closed storage for a buyer's unresolved checkout identity.

The key lets the next page or a refreshed tab reconcile the SAME provider
attempt. Losing it must never be mistaken for a successfully cleared attempt.
No buyer details or provider credentials are persisted here.
*/
export type CheckoutProvider = "esewa" | "khalti";
export type StoredCheckoutAttempt = { key: string; provider: CheckoutProvider };

type CheckoutAttemptStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
type StorageProvider = () => CheckoutAttemptStorage;

function browserSessionStorage(): CheckoutAttemptStorage {
  return window.sessionStorage;
}

export function checkoutAttemptStorageKey(offerId: number): string {
  return `hami:checkout-attempt:${offerId}`;
}

export function readStoredCheckoutAttempt(
  offerId: number,
  getStorage: StorageProvider = browserSessionStorage,
): StoredCheckoutAttempt | null {
  try {
    const raw = getStorage().getItem(checkoutAttemptStorageKey(offerId));
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<StoredCheckoutAttempt>;
    if (
      typeof value.key !== "string" ||
      value.key.length < 16 ||
      value.key.length > 128 ||
      (value.provider !== "esewa" && value.provider !== "khalti")
    ) return null;
    return { key: value.key, provider: value.provider };
  } catch {
    return null;
  }
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
