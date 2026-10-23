import { describe, expect, it } from 'vitest';

import type { LocalConversation } from '../types/tutor';
import {
  CONVERSATION_STORAGE_KEY,
  loadConversation,
  parseStoredConversation,
  saveConversation,
  serializeConversation,
  type StorageLike,
} from './conversationStorage';

const now = '2026-10-12T10:00:00.000Z';

function conversation(status: 'complete' | 'cancelled' | 'streaming' = 'complete'): LocalConversation {
  return {
    localConversationId: 'local-1', backendSessionId: 'server-1',
    createdAt: now, updatedAt: now, serverContextValid: true,
    messages: [
      { id: 'u-stable', role: 'user', text: 'Сұрақ', status: 'complete', createdAt: now },
      { id: 'a-stable', role: 'assistant', text: 'Ответ', status, createdAt: now },
    ],
  };
}

class MemoryStorage implements StorageLike {
  values = new Map<string, string>();
  async getItem(key: string) { return this.values.get(key) ?? null; }
  async setItem(key: string, value: string) { this.values.set(key, value); }
  async removeItem(key: string) { this.values.delete(key); }
}

describe('conversation persistence', () => {
  it('saves and restores a complete conversation with stable IDs', async () => {
    const storage = new MemoryStorage();
    await saveConversation(conversation(), storage);
    const restored = await loadConversation(storage);
    expect(restored.conversation?.messages.map((message) => message.id)).toEqual(['u-stable', 'a-stable']);
    expect(storage.values.has(CONVERSATION_STORAGE_KEY)).toBe(true);
  });

  it('preserves a cancelled partial assistant response', () => {
    const restored = parseStoredConversation(serializeConversation(conversation('cancelled')));
    expect(restored.conversation?.messages[1].status).toBe('cancelled');
  });

  it('marks an active stream interrupted and invalidates server context', () => {
    const restored = parseStoredConversation(serializeConversation(conversation('streaming')));
    expect(restored.conversation?.messages[1].status).toBe('interrupted');
    expect(restored.conversation?.serverContextValid).toBe(false);
    expect(restored.warning).toContain('прерван');
  });

  it.each([
    ['invalid JSON', '{oops'],
    ['unsupported version', JSON.stringify({ version: 99, conversation: conversation() })],
    ['missing required field', JSON.stringify({ version: 1, conversation: { messages: [] } })],
    ['incomplete message', JSON.stringify({ version: 1, conversation: { ...conversation(), messages: [{ id: 'bad' }] } })],
  ])('recovers from %s', async (_label, raw) => {
    const storage = new MemoryStorage();
    storage.values.set(CONVERSATION_STORAGE_KEY, raw);
    const restored = await loadConversation(storage);
    expect(restored.conversation).toBeNull();
    expect(restored.warning).toBeTruthy();
    expect(storage.values.has(CONVERSATION_STORAGE_KEY)).toBe(false);
  });
});
