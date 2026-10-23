import { fetch } from 'expo/fetch';

import { environment } from '../config/environment';
import {
  apiErrorFromResponse,
  assertValidApiConfiguration,
  requestJson,
  TutorApiError,
} from './client';
import { SSEParseError, SSEParser } from './sse';
import type {
  CreateSessionRequest,
  SessionCreatedResponse,
  TutorMessageRequest,
  TutorSession,
  TutorStreamEvent,
} from './types';

export interface BackendHealth {
  status: string;
  version?: string;
}

export interface OllamaHealth {
  status: string;
  provider: string;
  model: string;
  version?: string | null;
}

export async function checkBackendHealth(): Promise<BackendHealth> {
  const result = await requestJson<BackendHealth>('/health');
  if (result.status !== 'ok') {
    throw new TutorApiError('BACKEND_UNHEALTHY', 'Backend health check failed.');
  }
  return result;
}

export async function checkOllamaHealth(): Promise<OllamaHealth> {
  const result = await requestJson<OllamaHealth>('/health/ollama');
  if (result.status !== 'ok') {
    throw new TutorApiError('OLLAMA_UNAVAILABLE', 'Ollama health check failed.');
  }
  return result;
}

export function createTutorSession(
  request: CreateSessionRequest = { language: 'auto' },
): Promise<SessionCreatedResponse> {
  return requestJson('/api/v1/tutor/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
}

export function getTutorSession(sessionId: string): Promise<TutorSession> {
  return requestJson(`/api/v1/tutor/sessions/${sessionId}`);
}

export async function deleteTutorSession(sessionId: string): Promise<void> {
  await requestJson(`/api/v1/tutor/sessions/${sessionId}`, { method: 'DELETE' });
}

export interface StreamTutorMessageOptions {
  signal: AbortSignal;
  onEvent: (event: TutorStreamEvent) => void;
}

export async function streamTutorMessage(
  sessionId: string,
  request: TutorMessageRequest,
  options: StreamTutorMessageOptions,
): Promise<void> {
  assertValidApiConfiguration();
  const controller = new AbortController();
  let timedOut = false;
  const onCallerAbort = () => controller.abort();
  options.signal.addEventListener('abort', onCallerAbort, { once: true });
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, environment.streamTimeoutMs);

  try {
    const response = await fetch(
      `${environment.apiBaseUrl}/api/v1/tutor/sessions/${sessionId}/messages`,
      {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode: 'auto', ...request }),
        signal: controller.signal,
      },
    );
    if (!response.ok) {
      throw await apiErrorFromResponse(response as unknown as Response);
    }
    if (!response.body) {
      throw new TutorApiError('STREAM_UNAVAILABLE', 'Streaming is unavailable.');
    }

    const parser = new SSEParser();
    const reader = response.body.getReader();
    let terminalEventReceived = false;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const event of parser.push(value)) {
          options.onEvent(event);
          if (event.type === 'done') terminalEventReceived = true;
          if (event.type === 'error') {
            terminalEventReceived = true;
            throw new TutorApiError(event.data.code, event.data.message);
          }
        }
      }
      for (const event of parser.finish()) {
        options.onEvent(event);
        if (event.type === 'done') terminalEventReceived = true;
        if (event.type === 'error') {
          terminalEventReceived = true;
          throw new TutorApiError(event.data.code, event.data.message);
        }
      }
    } finally {
      reader.releaseLock();
    }
    if (!terminalEventReceived) {
      throw new TutorApiError('STREAM_INTERRUPTED', 'Tutor stream ended unexpectedly.');
    }
  } catch (error) {
    if (timedOut) {
      throw new TutorApiError('REQUEST_TIMEOUT', 'Tutor response timed out.');
    }
    if (options.signal.aborted) {
      throw new TutorApiError('CANCELLED', 'Request cancelled.');
    }
    if (error instanceof TutorApiError) throw error;
    if (error instanceof SSEParseError) {
      throw new TutorApiError('MALFORMED_SSE', 'Backend sent an invalid stream.');
    }
    throw new TutorApiError('NETWORK_ERROR', 'Connection to the backend was interrupted.');
  } finally {
    clearTimeout(timeout);
    options.signal.removeEventListener('abort', onCallerAbort);
  }
}
