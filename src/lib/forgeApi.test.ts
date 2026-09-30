import assert from 'node:assert/strict';
import { test } from 'node:test';
import { apiErrorMessage, parseTags, requestJson } from './forgeApi';

async function withMockedFetch<T>(response: Response, run: () => Promise<T>): Promise<T> {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => response;
  try {
    return await run();
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test('parseTags parses the backend comma-separated tag field', () => {
  assert.deepEqual(parseTags(' demand, ,regulatory '), ['demand', 'regulatory']);
  assert.deepEqual(parseTags(null), []);
});

test('apiErrorMessage preserves FastAPI detail text', () => {
  assert.equal(apiErrorMessage({ detail: 'Not authorized' }, 403), 'Not authorized');
  assert.equal(apiErrorMessage({ message: 'ignored' }, 502), 'API request failed (502)');
});

test('requestJson returns parsed JSON only for successful responses', async () => {
  const payload = await withMockedFetch(
    new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
    () => requestJson('/api/health'),
  );
  assert.deepEqual(payload, { status: 'ok' });
});

test('requestJson reports the backend error instead of treating it as data', async () => {
  await withMockedFetch(
    new Response(JSON.stringify({ detail: 'Database unavailable' }), { status: 503 }),
    async () => assert.rejects(requestJson('/api/health'), /Database unavailable/),
  );
});

test('requestJson rejects HTML and malformed response bodies', async () => {
  await withMockedFetch(
    new Response('<!doctype html>', { status: 200 }),
    async () => assert.rejects(requestJson('/api/signals'), /Expected JSON from \/api\/signals; received HTTP 200/),
  );
});
