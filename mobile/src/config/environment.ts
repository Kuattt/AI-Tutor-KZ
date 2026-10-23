const DEFAULT_ANDROID_EMULATOR_URL = 'http://10.0.2.2:8000';

export interface ApiUrlValidation {
  url: string;
  valid: boolean;
  error: string | null;
}

export function validateApiBaseUrl(value: string): ApiUrlValidation {
  const normalized = value.trim().replace(/\/+$/, '');
  try {
    const parsed = new URL(normalized);
    if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname) {
      throw new Error('unsupported protocol');
    }
    if (parsed.username || parsed.password || parsed.search || parsed.hash) {
      throw new Error('credentials, query, and fragment are not allowed');
    }
    if (parsed.port === '11434') {
      return {
        url: normalized,
        valid: false,
        error: 'Мобильное приложение должно подключаться к FastAPI, а не к Ollama.',
      };
    }
    return { url: normalized, valid: true, error: null };
  } catch {
    return {
      url: normalized,
      valid: false,
      error: 'EXPO_PUBLIC_API_BASE_URL должен быть корректным HTTP(S)-адресом FastAPI.',
    };
  }
}

const apiUrl = validateApiBaseUrl(
  process.env.EXPO_PUBLIC_API_BASE_URL ?? DEFAULT_ANDROID_EMULATOR_URL,
);

export const environment = {
  apiBaseUrl: apiUrl.url,
  apiUrlValid: apiUrl.valid,
  apiUrlError: apiUrl.error,
  requestTimeoutMs: 15_000,
  streamTimeoutMs: 210_000,
} as const;
