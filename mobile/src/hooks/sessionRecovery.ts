import type { BackendHealth } from '../api/tutorApi';
import type { SessionCreatedResponse, TutorSession } from '../types/tutor';

export interface SessionRecoveryDependencies {
  checkHealth: () => Promise<BackendHealth>;
  getSession: (sessionId: string) => Promise<TutorSession>;
  createSession: () => Promise<SessionCreatedResponse>;
}

export interface SessionRecoveryResult {
  sessionId: string;
  reused: boolean;
  contextLost: boolean;
  backendVersion: string | null;
  connectionMs: number;
}

export async function recoverBackendSession(
  persistedSessionId: string | null,
  serverContextValid: boolean,
  hasLocalMessages: boolean,
  dependencies: SessionRecoveryDependencies,
): Promise<SessionRecoveryResult> {
  const startedAt = performance.now();
  const health = await dependencies.checkHealth();

  if (persistedSessionId && serverContextValid) {
    try {
      await dependencies.getSession(persistedSessionId);
      return {
        sessionId: persistedSessionId,
        reused: true,
        contextLost: false,
        backendVersion: health.version ?? null,
        connectionMs: Math.round(performance.now() - startedAt),
      };
    } catch (error) {
      if (
        typeof error !== 'object' ||
        error === null ||
        !('code' in error) ||
        error.code !== 'SESSION_NOT_FOUND'
      ) {
        throw error;
      }
    }
  }

  const created = await dependencies.createSession();
  return {
    sessionId: created.session_id,
    reused: false,
    contextLost: hasLocalMessages,
    backendVersion: health.version ?? null,
    connectionMs: Math.round(performance.now() - startedAt),
  };
}
