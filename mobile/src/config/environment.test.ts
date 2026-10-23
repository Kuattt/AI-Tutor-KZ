import { describe, expect, it } from 'vitest';

import { validateApiBaseUrl } from './environment';

describe('API URL validation', () => {
  it('accepts emulator and private-device backend URLs', () => {
    expect(validateApiBaseUrl('http://10.0.2.2:8000').valid).toBe(true);
    expect(validateApiBaseUrl('http://192.168.1.25:8000/').url).toBe('http://192.168.1.25:8000');
  });

  it('rejects malformed URLs', () => {
    expect(validateApiBaseUrl('192.168.1.25:8000').valid).toBe(false);
  });

  it('rejects direct Ollama configuration', () => {
    expect(validateApiBaseUrl('http://127.0.0.1:11434').error).toContain('FastAPI');
  });
});
