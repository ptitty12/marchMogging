/** Compact for stat tiles: 1,284 / 12.9K / 4.2M */
export function fmtCompact(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(1)}B`
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1)}M`
  if (abs >= 10_000) return `${sign}${(abs / 1_000).toFixed(1)}K`
  return `${sign}${Math.round(abs).toLocaleString('en-US')}`
}

/** Full separators for grid cells (aligned with .tnum) */
export function fmtFull(value: number): string {
  return Math.round(value).toLocaleString('en-US')
}

/** Parse a user-typed number: allows commas, K/M/B suffixes, leading minus */
export function parseAmount(text: string): number | null {
  const cleaned = text.trim().replace(/,/g, '').replace(/\$/g, '')
  if (cleaned === '') return null
  const m = cleaned.match(/^(-?\d*\.?\d+)\s*([kKmMbB])?$/)
  if (!m) return NaN
  let v = parseFloat(m[1])
  const suffix = m[2]?.toLowerCase()
  if (suffix === 'k') v *= 1_000
  if (suffix === 'm') v *= 1_000_000
  if (suffix === 'b') v *= 1_000_000_000
  return v
}

export function fmtWhen(iso: string): string {
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
