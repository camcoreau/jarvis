import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fetchMock = vi.fn<typeof fetch>();

class MemoryStorage {
  private store = new Map<string, string>();
  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
  clear(): void {
    this.store.clear();
  }
}

beforeEach(() => {
  vi.resetModules();
  fetchMock.mockReset();
  globalThis.fetch = fetchMock;
  (globalThis as unknown as { localStorage: MemoryStorage }).localStorage =
    new MemoryStorage();
});

afterEach(() => {
  (globalThis as unknown as { localStorage?: MemoryStorage }).localStorage =
    undefined;
});

async function freshApi() {
  return import('./api');
}

describe('CamCore web model boundary', () => {
  it('never contacts client-local Ollama when preloading from web mode', async () => {
    const { preloadModel } = await freshApi();

    await expect(preloadModel('qwen3.5:4b')).resolves.toBeUndefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('managed-agent channel authentication', () => {
  it('binds channels through apiFetch with the configured Bearer key', async () => {
    localStorage.setItem(
      'openjarvis-settings',
      JSON.stringify({ apiKey: 'oj_sk_test' }),
    );
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'binding-1',
          agent_id: 'agent-1',
          channel_type: 'test',
          config: {},
          session_id: 'session-1',
          routing_mode: 'dedicated',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const { bindAgentChannel } = await freshApi();

    await bindAgentChannel('agent-1', 'test');

    expect(fetchMock).toHaveBeenCalledWith(
      '/v1/managed-agents/agent-1/channels',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer oj_sk_test',
        },
        body: JSON.stringify({
          channel_type: 'test',
          config: {},
          routing_mode: 'dedicated',
        }),
      },
    );
  });

  it('unbinds channels through apiFetch with the configured Bearer key', async () => {
    localStorage.setItem(
      'openjarvis-settings',
      JSON.stringify({ apiKey: 'oj_sk_test' }),
    );
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
    const { unbindAgentChannel } = await freshApi();

    await unbindAgentChannel('agent-1', 'binding-1');

    expect(fetchMock).toHaveBeenCalledWith(
      '/v1/managed-agents/agent-1/channels/binding-1',
      {
        method: 'DELETE',
        headers: { Authorization: 'Bearer oj_sk_test' },
      },
    );
  });
});
