import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AuditRecord } from '../types'
import { fmtCompact } from '../lib/format'

interface Props {
  configId: number
  periodCode: string
  sliceKey: string | null // null = whole config/period
  title: string
  onClose: () => void
}

function fmtValue(field: string, v: string | null): string {
  if (v === null) return '—'
  if (field === 'comment') return `“${v}”`
  const n = Number(v)
  return Number.isNaN(n) ? v : fmtCompact(n)
}

const FIELD_LABEL: Record<string, string> = {
  adjustment: 'Adjustment',
  total_forecast: 'Total forecast',
  comment: 'Comment',
}

export function AuditDrawer({ configId, periodCode, sliceKey, title, onClose }: Props) {
  const [records, setRecords] = useState<AuditRecord[] | null>(null)

  useEffect(() => {
    api
      .audit(configId, sliceKey ? { period_code: periodCode, slice_key: sliceKey } : { period_code: periodCode })
      .then(setRecords)
      .catch(() => setRecords([]))
  }, [configId, periodCode, sliceKey])

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-label="Change history">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-hairline bg-surface shadow-2xl">
        <div className="flex items-start justify-between border-b border-line px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold">Change history</h2>
            <p className="mt-0.5 text-xs text-muted">{title}</p>
          </div>
          <button onClick={onClose} className="rounded px-2 py-1 text-sm text-muted hover:bg-page">
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {records === null && <p className="text-sm text-muted">Loading…</p>}
          {records?.length === 0 && <p className="text-sm text-muted">No changes recorded yet.</p>}
          <ol className="space-y-3">
            {records?.map((r) => (
              <li key={r.id} className="rounded-lg border border-hairline bg-page px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-xs font-semibold text-ink">{FIELD_LABEL[r.field] ?? r.field}</span>
                  <span className="text-[11px] text-muted">
                    {new Date(r.changed_at + (r.changed_at.endsWith('Z') ? '' : 'Z')).toLocaleString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
                {!sliceKey && (
                  <div className="mt-0.5 truncate text-[11px] text-muted" title={r.slice_key}>
                    {r.slice_key.split('||').map((p) => p.split('=')[1]).filter(Boolean).join(' · ')}
                  </div>
                )}
                <div className="tnum mt-1 text-xs text-ink2">
                  {fmtValue(r.field, r.old_value)} <span className="text-muted">→</span>{' '}
                  <span className="font-medium text-ink">{fmtValue(r.field, r.new_value)}</span>
                </div>
                <div className="mt-1 text-[11px] text-brandink">{r.changed_by}</div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  )
}
