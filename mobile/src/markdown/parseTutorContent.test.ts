import { describe, expect, it } from 'vitest';

import { parseTutorContent } from './parseTutorContent';

describe('parseTutorContent', () => {
  it('recognizes inline math', () => {
    const result = parseTutorContent('Формула: $a = v^2/r$.');
    expect(result.segments).toContainEqual({ type: 'inlineMath', value: 'a = v^2/r' });
  });

  it('recognizes block math', () => {
    const result = parseTutorContent('Ответ:\n$$\na = \\frac{v^2}{r}\n$$');
    expect(result.segments).toContainEqual({ type: 'blockMath', value: 'a = \\frac{v^2}{r}' });
  });

  it('keeps Kazakh, Russian, lists, and emphasis around math', () => {
    const source = '**Үдеу** — ускорение:\n\n- $v$ — жылдамдық\n- $R$ — радиус';
    const result = parseTutorContent(source);
    expect(result.hasMath).toBe(true);
    expect(result.segments.filter((segment) => segment.type === 'inlineMath')).toHaveLength(2);
    expect(result.segments.map((segment) => segment.value).join(' ')).toContain('Үдеу');
  });

  it('does not parse math inside code', () => {
    expect(parseTutorContent('`$not_math$`').hasMath).toBe(false);
    expect(parseTutorContent('```txt\n$not_math$\n```').hasMath).toBe(false);
  });

  it('reports incomplete streaming math without throwing', () => {
    const result = parseTutorContent('Формула: $a =');
    expect(result.hasIncompleteMath).toBe(true);
  });
});
