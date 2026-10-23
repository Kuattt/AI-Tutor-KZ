import { expect, it } from 'vitest';

import type { ChatMessage } from '../types/tutor';
import {
  canStartGeneration,
  initialTutorState,
  tutorReducer,
  type TutorState,
} from './chatState';

const user: ChatMessage = {
  id: 'u1',
  role: 'user',
  text: 'Вопрос',
  status: 'complete',
  createdAt: '2026-10-12T10:00:00.000Z',
};
const assistant: ChatMessage = {
  id: 'a1',
  role: 'assistant',
  text: '',
  status: 'streaming',
  createdAt: '2026-10-12T10:00:00.000Z',
};

function generatingState(): TutorState {
  const ready = tutorReducer(initialTutorState, {
    type: 'SESSION_READY',
    sessionId: 'session-1',
  });
  return tutorReducer(ready, { type: 'SEND_STARTED', user, assistant, at: user.createdAt });
}

it('appends deltas to the same assistant message and completes it', () => {
  let state = generatingState();
  state = tutorReducer(state, {
    type: 'STREAM_EVENT',
    assistantId: 'a1',
    event: { type: 'delta', data: { text: 'Сәлем' } },
  });
  state = tutorReducer(state, {
    type: 'STREAM_EVENT',
    assistantId: 'a1',
    event: { type: 'delta', data: { text: '!' } },
  });
  state = tutorReducer(state, {
    type: 'STREAM_EVENT',
    assistantId: 'a1',
    event: { type: 'done', data: { finish_reason: 'stop' } },
  });

  expect(state.messages).toHaveLength(2);
  expect(state.messages[1]).toMatchObject({ text: 'Сәлем!', status: 'complete' });
  expect(state.phase).toBe('ready');
});

it('marks a streaming assistant message as failed', () => {
  const state = tutorReducer(generatingState(), {
    type: 'STREAM_FAILED',
    assistantId: 'a1',
    message: 'Ошибка сети',
  });
  expect(state.messages[1].status).toBe('error');
  expect(state.errorMessage).toBe('Ошибка сети');
  expect(state.phase).toBe('ready');
});

it('returns to ready after cancellation and preserves partial text', () => {
  let state = tutorReducer(generatingState(), {
    type: 'STREAM_EVENT',
    assistantId: 'a1',
    event: { type: 'delta', data: { text: 'Частичный ответ' } },
  });
  state = tutorReducer(state, { type: 'STREAM_CANCELLED', assistantId: 'a1' });
  expect(state.messages[1]).toMatchObject({
    text: 'Частичный ответ',
    status: 'cancelled',
  });
  expect(state.phase).toBe('ready');
});

it('blocks a duplicate generation while one is active', () => {
  const state = generatingState();
  const duplicate = tutorReducer(state, {
    type: 'SEND_STARTED',
    user: { ...user, id: 'u2' },
    assistant: { ...assistant, id: 'a2' },
    at: user.createdAt,
  });
  expect(canStartGeneration(state)).toBe(false);
  expect(duplicate).toBe(state);
  expect(duplicate.messages).toHaveLength(2);
});

it('replaces an expired session without deleting visible messages', () => {
  const oldState = {
    ...generatingState(),
    phase: 'ready' as const,
    activeAssistantId: null,
  };
  const state = tutorReducer(oldState, {
    type: 'SESSION_REPLACED',
    sessionId: 'session-2',
  });
  expect(state.sessionId).toBe('session-2');
  expect(state.messages).toEqual(oldState.messages);
  expect(state.contextReset).toBe(true);
  expect(state.statusMessage).toContain('Предыдущие сообщения видны только локально');
});

it('retries into the existing assistant slot without duplicating the user message', () => {
  let state = tutorReducer(generatingState(), {
    type: 'STREAM_FAILED', assistantId: 'a1', message: 'Ошибка сети', code: 'NETWORK_ERROR',
  });
  state = tutorReducer(state, { type: 'RETRY_STARTED', assistantId: 'a1', at: user.createdAt });
  expect(state.messages).toHaveLength(2);
  expect(state.messages[1]).toMatchObject({ id: 'a1', text: '', status: 'streaming' });
  expect(state.phase).toBe('generating');
});

it('starts a new conversation with cleared messages and reset session', () => {
  const conversation = {
    localConversationId: 'local-new', backendSessionId: 'session-new', messages: [],
    createdAt: user.createdAt, updatedAt: user.createdAt, serverContextValid: true,
  };
  const state = tutorReducer(generatingState(), { type: 'NEW_CONVERSATION', conversation });
  expect(state.messages).toEqual([]);
  expect(state.sessionId).toBe('session-new');
  expect(state.serverContextValid).toBe(true);
  expect(state.phase).toBe('ready');
});
