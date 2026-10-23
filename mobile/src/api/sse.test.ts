import { describe, expect, it } from 'vitest';

import { SSEParseError, SSEParser } from './sse';

describe('SSEParser', () => {
  it('parses one complete event', () => {
    const parser = new SSEParser();
    expect(parser.push('event: delta\ndata: {"text":"Hello"}\n\n')).toEqual([
      { type: 'delta', data: { text: 'Hello' } },
    ]);
  });

  it('buffers an event split between arbitrary chunks', () => {
    const parser = new SSEParser();
    expect(parser.push('eve')).toEqual([]);
    expect(parser.push('nt: delta\nda')).toEqual([]);
    expect(parser.push('ta: {"text":"Hello"}\n\n')).toEqual([
      { type: 'delta', data: { text: 'Hello' } },
    ]);
  });

  it('parses several events in one chunk', () => {
    const parser = new SSEParser();
    expect(
      parser.push(
        'event: start\ndata: {"session_id":"s","mode":"guided_solving"}\n\n' +
          'event: done\ndata: {"finish_reason":"stop"}\n\n',
      ),
    ).toHaveLength(2);
  });

  it('decodes Kazakh and Russian UTF-8 split inside a character', () => {
    const bytes = new TextEncoder().encode('event: delta\ndata: {"text":"Сәлем, оқушы"}\n\n');
    const parser = new SSEParser();
    const split = bytes.findIndex((value) => value > 127) + 1;
    expect(parser.push(bytes.slice(0, split))).toEqual([]);
    expect(parser.push(bytes.slice(split))).toEqual([
      { type: 'delta', data: { text: 'Сәлем, оқушы' } },
    ]);
  });

  it('throws a typed error for malformed JSON', () => {
    const parser = new SSEParser();
    expect(() => parser.push('event: delta\ndata: {bad}\n\n')).toThrow(SSEParseError);
  });

  it('parses a final event without a trailing blank line', () => {
    const parser = new SSEParser();
    parser.push('event: done\ndata: {"finish_reason":"stop"}');
    expect(parser.finish()).toEqual([
      { type: 'done', data: { finish_reason: 'stop' } },
    ]);
  });
});
