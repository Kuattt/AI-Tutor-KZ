export type TutorContentSegment =
  | { type: 'markdown'; value: string }
  | { type: 'inlineMath'; value: string }
  | { type: 'blockMath'; value: string };

export interface ParsedTutorContent {
  segments: TutorContentSegment[];
  hasMath: boolean;
  hasIncompleteMath: boolean;
}

function isEscaped(text: string, index: number): boolean {
  let slashes = 0;
  for (let cursor = index - 1; cursor >= 0 && text[cursor] === '\\'; cursor -= 1) {
    slashes += 1;
  }
  return slashes % 2 === 1;
}

function pushMarkdown(segments: TutorContentSegment[], value: string) {
  if (!value) return;
  const previous = segments.at(-1);
  if (previous?.type === 'markdown') previous.value += value;
  else segments.push({ type: 'markdown', value });
}

export function parseTutorContent(text: string): ParsedTutorContent {
  const segments: TutorContentSegment[] = [];
  let cursor = 0;
  let markdownStart = 0;
  let fenced = false;
  let inlineCode = false;
  let incomplete = false;

  while (cursor < text.length) {
    if (text.startsWith('```', cursor) && !inlineCode) {
      fenced = !fenced;
      cursor += 3;
      continue;
    }
    if (text[cursor] === '`' && !fenced && !isEscaped(text, cursor)) {
      inlineCode = !inlineCode;
      cursor += 1;
      continue;
    }
    if (text[cursor] !== '$' || fenced || inlineCode || isEscaped(text, cursor)) {
      cursor += 1;
      continue;
    }

    const block = text[cursor + 1] === '$';
    const delimiter = block ? '$$' : '$';
    const contentStart = cursor + delimiter.length;
    let closing = contentStart;
    while (closing < text.length) {
      if (text.startsWith(delimiter, closing) && !isEscaped(text, closing)) break;
      closing += 1;
    }
    if (closing >= text.length) {
      incomplete = true;
      break;
    }

    const math = text.slice(contentStart, closing);
    if (!math.trim()) {
      cursor = closing + delimiter.length;
      continue;
    }
    pushMarkdown(segments, text.slice(markdownStart, cursor));
    segments.push({
      type: block ? 'blockMath' : 'inlineMath',
      value: math.trim(),
    });
    cursor = closing + delimiter.length;
    markdownStart = cursor;
  }

  pushMarkdown(segments, text.slice(markdownStart));
  return {
    segments,
    hasMath: segments.some((segment) => segment.type !== 'markdown'),
    hasIncompleteMath: incomplete,
  };
}
