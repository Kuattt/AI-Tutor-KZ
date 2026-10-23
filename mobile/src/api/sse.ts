import type { TutorStreamEvent } from './types';

const EVENT_TYPES = new Set(['start', 'delta', 'metadata', 'done', 'error']);

export class SSEParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SSEParseError';
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseRecord(record: string): TutorStreamEvent | null {
  let eventName = '';
  const dataLines: string[] = [];

  for (const line of record.split(/\r\n|\n|\r/)) {
    if (!line || line.startsWith(':')) continue;
    const separator = line.indexOf(':');
    const field = separator === -1 ? line : line.slice(0, separator);
    let value = separator === -1 ? '' : line.slice(separator + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') eventName = value;
    if (field === 'data') dataLines.push(value);
  }

  if (!eventName && dataLines.length === 0) return null;
  if (!EVENT_TYPES.has(eventName)) {
    throw new SSEParseError(`Unknown SSE event: ${eventName || '(missing)'}`);
  }
  if (dataLines.length === 0) {
    throw new SSEParseError(`SSE event ${eventName} has no data`);
  }

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join('\n'));
  } catch {
    throw new SSEParseError(`SSE event ${eventName} contains invalid JSON`);
  }
  if (!isRecord(data)) {
    throw new SSEParseError(`SSE event ${eventName} data must be an object`);
  }
  return { type: eventName, data } as TutorStreamEvent;
}

export class SSEParser {
  private readonly decoder = new TextDecoder();
  private buffer = '';

  push(chunk: Uint8Array | string): TutorStreamEvent[] {
    this.buffer +=
      typeof chunk === 'string'
        ? chunk
        : this.decoder.decode(chunk, { stream: true });
    return this.drain(false);
  }

  finish(): TutorStreamEvent[] {
    this.buffer += this.decoder.decode();
    return this.drain(true);
  }

  private drain(final: boolean): TutorStreamEvent[] {
    const events: TutorStreamEvent[] = [];
    const boundary = /\r\n\r\n|\n\n|\r\r/;

    while (true) {
      const match = boundary.exec(this.buffer);
      if (!match) break;
      const record = this.buffer.slice(0, match.index);
      this.buffer = this.buffer.slice(match.index + match[0].length);
      const event = parseRecord(record);
      if (event) events.push(event);
    }

    if (final && this.buffer.trim()) {
      const event = parseRecord(this.buffer);
      this.buffer = '';
      if (event) events.push(event);
    }
    return events;
  }
}
