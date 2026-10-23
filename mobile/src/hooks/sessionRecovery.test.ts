import { describe, expect, it, vi } from 'vitest';

import type { SessionCreatedResponse, TutorSession } from '../types/tutor';
import { recoverBackendSession } from './sessionRecovery';

const created: SessionCreatedResponse = { session_id: 'new-session', created_at: '2026-10-12T10:00:00Z', mode: 'direct_explanation' };
const existing = { session_id: 'old-session' } as TutorSession;

function dependencies(getSession = vi.fn(async () => existing)) {
  return {
    checkHealth: vi.fn(async () => ({ status: 'ok', version: '0.1.1' })),
    getSession,
    createSession: vi.fn(async () => created),
  };
}

describe('session recovery', () => {
  it('reuses a valid persisted backend session', async () => {
    const deps = dependencies();
    const result = await recoverBackendSession('old-session', true, true, deps);
    expect(result).toMatchObject({ sessionId: 'old-session', reused: true, contextLost: false });
    expect(deps.createSession).not.toHaveBeenCalled();
  });

  it('creates a session and reports context loss when persisted session is missing', async () => {
    const deps = dependencies(vi.fn(async () => { throw Object.assign(new Error('missing'), { code: 'SESSION_NOT_FOUND' }); }));
    const result = await recoverBackendSession('old-session', true, true, deps);
    expect(result).toMatchObject({ sessionId: 'new-session', reused: false, contextLost: true });
  });

  it('keeps local messages while skipping a known-invalid server context', async () => {
    const deps = dependencies();
    const localMessages = ['local message'];
    const result = await recoverBackendSession('old-session', false, localMessages.length > 0, deps);
    expect(result.contextLost).toBe(true);
    expect(localMessages).toEqual(['local message']);
    expect(deps.getSession).not.toHaveBeenCalled();
  });
});
