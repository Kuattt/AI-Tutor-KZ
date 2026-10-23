import { fetch } from 'expo/fetch';

import { environment } from '../config/environment';
import type { ApiErrorResponse } from './types';

export class TutorApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'TutorApiError';
  }
}

export function assertValidApiConfiguration(): void {
  if (!environment.apiUrlValid) {
    throw new TutorApiError(
      'INVALID_BACKEND_URL',
      environment.apiUrlError ?? 'Backend URL is invalid.',
    );
  }
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (typeof value !== 'object' || value === null) return false;
  const error = (value as { error?: unknown }).error;
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { code?: unknown }).code === 'string' &&
    typeof (error as { message?: unknown }).message === 'string'
  );
}

export async function apiErrorFromResponse(response: Response): Promise<TutorApiError> {
  try {
    const payload: unknown = await response.json();
    if (isApiErrorResponse(payload)) {
      return new TutorApiError(
        payload.error.code,
        payload.error.message,
        response.status,
      );
    }
  } catch {
    // Fall through to a typed HTTP error without exposing parser details.
  }
  return new TutorApiError(
    'HTTP_ERROR',
    `Backend returned HTTP ${response.status}.`,
    response.status,
  );
}

export async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  assertValidApiConfiguration();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), environment.requestTimeoutMs);
  try {
    const response = await fetch(`${environment.apiBaseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...init.headers,
      },
    });
    if (!response.ok) throw await apiErrorFromResponse(response as unknown as Response);
    if (response.status === 204) return undefined as T;
    try {
      return (await response.json()) as T;
    } catch {
      throw new TutorApiError('INVALID_JSON', 'Backend returned invalid JSON.');
    }
  } catch (error) {
    if (controller.signal.aborted) {
      throw new TutorApiError('REQUEST_TIMEOUT', 'Backend request timed out.');
    }
    if (error instanceof TutorApiError) throw error;
    throw new TutorApiError('NETWORK_ERROR', 'Could not connect to the backend.');
  } finally {
    clearTimeout(timeout);
  }
}
