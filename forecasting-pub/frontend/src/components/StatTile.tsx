import { fmtCompact } from '../lib/format'

interface Props {
  label: string
  value: number
  tone?: 'default' | 'brand' | 'signed'
  hint?: string
}

export function StatTile({ label, value, tone = 'default', hint }: Props) {
  const valueClass =
    tone === 'brand'
      ? 'text-brandink'
      : tone === 'signed'
        ? value < 0
          ? 'text-neg'
          : value > 0
            ? 'text-pos'
            : 'text-ink'
        : 'text-ink'
  const signed = tone === 'signed' && value > 0 ? '+' : ''
  return (
    <div
      className="min-w-36 flex-1 rounded-xl border border-hairline bg-surface px-4 py-3"
      title={hint}
    >
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${valueClass}`}>
        {signed}
        {fmtCompact(value)}
      </div>
    </div>
  )
}
