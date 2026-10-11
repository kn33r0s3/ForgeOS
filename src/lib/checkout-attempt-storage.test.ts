import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  checkoutAttemptStorageKey,
  clearStoredCheckoutAttempt,
  readStoredCheckoutAttempt,
  writeStoredCheckoutAttempt,
} from "./checkout-attempt-storage.ts";

type StoragePort = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function memoryStorage(seed: Record<string, string> = {}): StoragePort {
  const values = new Map(Object.entries(seed));
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, value); },
    removeItem: (key) => { values.delete(key); },
  };
}

const attempt = { key: "TEST-idempotency-key-123456", provider: "khalti" as const };

describe("shared checkout-attempt storage", () => {
  it("round-trips a valid provider-bound attempt", () => {
    const storage = memoryStorage();
    assert.equal(writeStoredCheckoutAttempt(5, attempt, () => storage), true);
    assert.deepEqual(readStoredCheckoutAttempt(5, () => storage), attempt);
  });

  it("refuses persistence when storage throws", () => {
    const storage: StoragePort = {
      getItem: () => null,
      setItem: () => { throw new Error("blocked"); },
      removeItem: () => {},
    };
    assert.equal(writeStoredCheckoutAttempt(5, attempt, () => storage), false);
  });

  it("does not treat a removal exception as successful clearing", () => {
    const storage: StoragePort = {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => { throw new Error("blocked"); },
    };
    assert.equal(clearStoredCheckoutAttempt(5, () => storage), false);
  });

  it("does not authorize clearing when read-back throws", () => {
    const storage: StoragePort = {
      getItem: () => { throw new Error("blocked"); },
      setItem: () => {},
      removeItem: () => {},
    };
    assert.equal(clearStoredCheckoutAttempt(5, () => storage), false);
  });

  it("does not authorize clearing when the key remains stored", () => {
    const key = checkoutAttemptStorageKey(5);
    const storage = memoryStorage({ [key]: JSON.stringify(attempt) });
    const stubbornStorage: StoragePort = {
      getItem: storage.getItem,
      setItem: storage.setItem,
      removeItem: () => {},
    };
    assert.equal(clearStoredCheckoutAttempt(5, () => stubbornStorage), false);
  });

  it("confirms clearing only after read-back proves the key absent", () => {
    const storage = memoryStorage({ [checkoutAttemptStorageKey(5)]: JSON.stringify(attempt) });
    assert.equal(clearStoredCheckoutAttempt(5, () => storage), true);
    assert.equal(readStoredCheckoutAttempt(5, () => storage), null);
  });

  it("rejects malformed or unsupported provider records", () => {
    const storage = memoryStorage({
      [checkoutAttemptStorageKey(5)]: JSON.stringify({ key: "too-short", provider: "khalti" }),
      [checkoutAttemptStorageKey(6)]: JSON.stringify({ key: attempt.key, provider: "other" }),
    });
    assert.equal(readStoredCheckoutAttempt(5, () => storage), null);
    assert.equal(readStoredCheckoutAttempt(6, () => storage), null);
  });
});
