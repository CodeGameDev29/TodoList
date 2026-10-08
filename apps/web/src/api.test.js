import { afterEach, describe, expect, it, vi } from 'vitest';
import { request } from './api.js';

afterEach(() => vi.unstubAllGlobals());

describe('API error feedback', () => {
  it.each(['', '<html><body>Bad gateway</body></html>'])(
    'gives retry guidance for a non-JSON server error (%j)',
    async (body) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 500 })));
      await expect(request('', { method: 'POST', body: '{}' })).rejects.toThrow(
        'The request failed. Please try again.',
      );
    },
  );

  it('gives connection guidance for network rejection', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(request()).rejects.toThrow(
      'Unable to reach the server. Check your connection and try again.',
    );
  });

  it('preserves structured server validation messages and fields', async () => {
    const validation = { message: 'Invalid task.', fields: { title: 'Title is required.' } };
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify({ error: validation }), { status: 400 })),
    );
    await expect(request()).rejects.toMatchObject(validation);
  });

  it('preserves fetch cancellation', async () => {
    const abort = new DOMException('Cancelled', 'AbortError');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort));
    await expect(request()).rejects.toBe(abort);
  });

  it('preserves cancellation while reading the body', async () => {
    const abort = new DOMException('Cancelled', 'AbortError');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ status: 200, ok: true, json: vi.fn().mockRejectedValue(abort) }),
    );
    await expect(request()).rejects.toBe(abort);
  });
});
