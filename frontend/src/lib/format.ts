// Shared colour palette and number formatting. Colours: forest/green + saffron + brick; no blue/purple.

/** Named palette used by charts and inline styles. */
export const C = {
  s1: '#1f7a4a',
  s2: '#dd8f22',
  grid: '#e7e0d3',
  axis: '#cfc6b5',
  muted: '#8a847b',
  ink: '#1f1d1a',
  ink2: '#57524b',
  good: '#1f6b3a',
  brick: '#b4432a',
  mustard: '#8a5a0b',
  mid: '#ece7dc',
  surface: '#fffdf8',
}

// Diverging change scale: brick (worse) ↔ green (better), warm-gray midpoint. Always paired with signed numbers.
const NEGATIVE_SCALE = ['#f4dcd2', '#e8ae9b', '#d67d63', '#b9533a', '#8c3423']
const POSITIVE_SCALE = ['#dcebdf', '#b2d4ba', '#7fb68f', '#3f8f5d', '#1f6b3a']
const NO_DATA_COLOR = '#e7e2d7'
/** Scale steps dark enough to need light text on top. */
const DARK_BACKGROUNDS = ['#b9533a', '#8c3423', '#3f8f5d', '#1f6b3a', '#d67d63']

/** Colour for a signed change value; `max` is the magnitude that maps to the darkest step. */
export function divergingColor(value: number | null | undefined, max = 15): string {
  if (value === null || value === undefined) return NO_DATA_COLOR
  if (Math.abs(value) < 1) return C.mid
  const scale = value < 0 ? NEGATIVE_SCALE : POSITIVE_SCALE
  const step = Math.floor((Math.abs(value) / max) * scale.length)
  return scale[Math.min(scale.length - 1, step)]
}

/** Readable text colour for a given scale background. */
export const inkOn = (background: string) => (DARK_BACKGROUNDS.includes(background) ? C.surface : C.ink)

/** Sequential (low → high) green scale. */
export const SEQ = ['#f3efe4', '#dcebdf', '#b2d4ba', '#7fb68f', '#3f8f5d', '#2a6f47', '#1e4d36']

/** Format a percentage with `digits` decimals, or an em dash when missing. */
export const pct = (value: number | null | undefined, digits = 1) =>
  value === null || value === undefined ? '—' : `${Number(value).toFixed(digits)}%`

/** Format a number with an explicit `+` for positive values, or an em dash when missing. */
export const signed = (value: number | null | undefined) =>
  value === null || value === undefined ? '—' : `${value > 0 ? '+' : ''}${value}`
