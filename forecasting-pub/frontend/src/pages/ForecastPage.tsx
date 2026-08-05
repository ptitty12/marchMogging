import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { ForecastConfig, Grid, GridRow, Period } from '../types'
import { StatTile } from '../components/StatTile'
import { CommentCell, EditableNumberCell } from '../components/EditableCell'
import { AuditDrawer } from '../components/AuditDrawer'
import { fmtWhen } from '../lib/format'

interface Props {
  config: ForecastConfig
  periods: Period[]
}

interface DrawerState {
  sliceKey: string | null
  periodCode: string
  title: string
}

export function ForecastPage({ config, periods }: Props) {
  const [selectedPeriods, setSelectedPeriods] = useState<string[]>([])
  const [grid, setGrid] = useState<Grid | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [hideEmpty, setHideEmpty] = useState(true)
  const [drawer, setDrawer] = useState<DrawerState | null>(null)

  // default: the current quarter (2026 Q3 in seed time) — else first period
  useEffect(() => {
    if (periods.length && selectedPeriods.length === 0) {
      const now = new Date()
      const current = periods.find(
        (p) => new Date(p.start_date) <= now && now <= new Date(p.end_date + 'T23:59:59'),
      )
      setSelectedPeriods([current?.code ?? periods[0].code])
    }
  }, [periods, selectedPeriods.length])

  const refresh = useCallback(() => {
    if (!selectedPeriods.length) return
    api
      .grid(config.id, selectedPeriods)
      .then((g) => {
        setGrid(g)
        setError(null)
      })
      .catch((e) => setError(String(e)))
  }, [config.id, selectedPeriods])

  useEffect(() => {
    setGrid(null)
    setFilters({})
    refresh()
  }, [refresh])

  const levelKeys = config.levels.map((l) => l.key)

  const filterOptions = useMemo(() => {
    const opts: Record<string, string[]> = {}
    for (const key of levelKeys) {
      opts[key] = [...new Set((grid?.rows ?? []).map((r) => r.slice_values[key] || ''))]
        .filter(Boolean)
        .sort()
    }
    return opts
  }, [grid, levelKeys])

  const visibleRows = useMemo(() => {
    let rows = grid?.rows ?? []
    for (const [key, val] of Object.entries(filters)) {
      if (val) rows = rows.filter((r) => (r.slice_values[key] || '') === val)
    }
    if (hideEmpty) {
      rows = rows.filter((r) => r.actuals !== 0 || r.pipeline_open !== 0 || r.has_entry)
    }
    return rows
  }, [grid, filters, hideEmpty])

  const totals = useMemo(() => {
    return visibleRows.reduce(
      (acc, r) => {
        acc.actuals += r.actuals
        acc.pipeline += r.pipeline_open
        acc.buildup += r.suggested_buildup
        acc.adjustment += r.effective_adjustment
        acc.total += r.effective_total
        return acc
      },
      { actuals: 0, pipeline: 0, buildup: 0, adjustment: 0, total: 0 },
    )
  }, [visibleRows])

  const save = async (
    row: GridRow,
    fields: Partial<{ adjustment: number | null; total_forecast: number | null; comment: string | null }>,
  ) => {
    await api.saveEntry(config.id, {
      period_code: row.period_code,
      slice_values: row.slice_values,
      ...fields,
      set_fields: Object.keys(fields),
    })
    refresh()
  }

  const multiPeriod = selectedPeriods.length > 1

  return (
    <div className="space-y-4">
      {/* period chips + toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Forecast periods">
          {periods.map((p) => {
            const active = selectedPeriods.includes(p.code)
            return (
              <button
                key={p.code}
                onClick={() =>
                  setSelectedPeriods((cur) => {
                    const next = active ? cur.filter((c) => c !== p.code) : [...cur, p.code]
                    return next.length ? next.sort() : cur
                  })
                }
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  active
                    ? 'border-brandink bg-brandwash text-brandink'
                    : 'border-hairline bg-surface text-ink2 hover:border-line'
                }`}
              >
                {p.code}
              </button>
            )
          })}
        </div>
        <div className="ml-auto flex items-center gap-3">
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-ink2">
            <input
              type="checkbox"
              checked={!hideEmpty}
              onChange={(e) => setHideEmpty(!e.target.checked)}
              className="accent-(--brand)"
            />
            Show all slices
          </label>
          <button
            onClick={() =>
              setDrawer({
                sliceKey: null,
                periodCode: selectedPeriods[0],
                title: `${config.name} · ${selectedPeriods.join(', ')}`,
              })
            }
            className="rounded-lg border border-hairline bg-surface px-3 py-1.5 text-xs font-medium text-ink2 hover:bg-page"
          >
            Change history
          </button>
        </div>
      </div>

      {/* grand totals */}
      <div className="flex flex-wrap gap-3">
        <StatTile label="Actuals to date" value={totals.actuals} hint="Booked so far in the selected periods" />
        <StatTile label="Open pipeline" value={totals.pipeline} hint="Open bfo opportunities closing in period" />
        <StatTile
          label="Suggested forecast"
          value={totals.buildup}
          hint="Actuals + weighted open pipeline (build-up)"
        />
        <StatTile label="Adjustments" value={totals.adjustment} tone="signed" hint="Net rep adjustments" />
        <StatTile label="Total forecast" value={totals.total} tone="brand" hint="Where the team says it lands" />
      </div>

      {/* level filters */}
      <div className="flex flex-wrap items-center gap-2">
        {config.levels.map((lv, i) => (
          <label key={lv.key} className="flex items-center gap-1.5 text-xs text-muted">
            <span className="font-medium">
              L{i + 1} · {lv.label}
            </span>
            <select
              value={filters[lv.key] ?? ''}
              onChange={(e) => setFilters((f) => ({ ...f, [lv.key]: e.target.value }))}
              className="rounded-lg border border-hairline bg-surface px-2 py-1.5 text-xs text-ink"
            >
              <option value="">All</option>
              {filterOptions[lv.key]?.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        ))}
        {Object.values(filters).some(Boolean) && (
          <button onClick={() => setFilters({})} className="text-xs font-medium text-brandink hover:underline">
            Clear filters
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-neg bg-negwash px-4 py-3 text-sm text-neg">{error}</div>
      )}

      {/* the grid */}
      <div className="overflow-x-auto rounded-xl border border-hairline bg-surface">
        <table className="w-full min-w-[980px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-left text-[11px] font-semibold tracking-wide text-muted uppercase">
              {multiPeriod && <th className="px-3 py-2.5">Period</th>}
              {config.levels.map((lv) => (
                <th key={lv.key} className="px-3 py-2.5">
                  {lv.label}
                </th>
              ))}
              <th className="px-3 py-2.5 text-right">Actuals</th>
              <th className="px-3 py-2.5 text-right">Open pipeline</th>
              <th className="px-3 py-2.5 text-right" title="Actuals + 100% of open pipeline">
                All-bfo suggested
              </th>
              <th className="px-3 py-2.5 text-right" title="Actuals + weighted open pipeline">
                Build-up suggested
              </th>
              <th className="bg-editwash px-3 py-2.5 text-right">Adjustment</th>
              <th className="bg-editwash px-3 py-2.5 text-right">Total forecast</th>
              <th className="bg-editwash px-3 py-2.5">Comments</th>
              <th className="px-3 py-2.5">Last edit</th>
            </tr>
          </thead>
          <tbody>
            {grid === null && (
              <tr>
                <td colSpan={12} className="px-4 py-10 text-center text-sm text-muted">
                  Loading grid…
                </td>
              </tr>
            )}
            {grid !== null && visibleRows.length === 0 && (
              <tr>
                <td colSpan={12} className="px-4 py-10 text-center text-sm text-muted">
                  No slices match — clear filters or enable “Show all slices”.
                </td>
              </tr>
            )}
            {visibleRows.map((row) => (
              <tr
                key={`${row.period_code}|${row.slice_key}`}
                className="border-b border-line/60 last:border-0 hover:bg-page/60"
              >
                {multiPeriod && (
                  <td className="tnum px-3 py-1.5 text-xs whitespace-nowrap text-muted">{row.period_code}</td>
                )}
                {config.levels.map((lv) => (
                  <td key={lv.key} className="max-w-44 truncate px-3 py-1.5 text-ink2" title={row.slice_values[lv.key]}>
                    {row.slice_values[lv.key] || <span className="text-muted">—</span>}
                  </td>
                ))}
                <td className="tnum px-3 py-1.5 text-right text-ink2">{row.actuals === 0 ? '—' : fmt(row.actuals)}</td>
                <td className="tnum px-3 py-1.5 text-right text-ink2">
                  {row.pipeline_open === 0 ? '—' : fmt(row.pipeline_open)}
                </td>
                <td className="tnum px-3 py-1.5 text-right text-muted italic">{fmt(row.suggested_all_bfo)}</td>
                <td className="tnum px-3 py-1.5 text-right font-medium">{fmt(row.suggested_buildup)}</td>
                <td className="w-32 bg-editwash/50 px-1 py-1">
                  <EditableNumberCell
                    value={row.effective_adjustment}
                    isSet={row.adjustment !== null || row.total_forecast !== null}
                    signed
                    onSave={(v) => save(row, { adjustment: v })}
                  />
                </td>
                <td className="w-36 bg-editwash/50 px-1 py-1">
                  <EditableNumberCell
                    value={row.effective_total}
                    isSet={true}
                    emphasis
                    onSave={(v) => save(row, { total_forecast: v })}
                  />
                </td>
                <td className="w-56 min-w-44 bg-editwash/50 px-1 py-1">
                  <CommentCell value={row.comment} onSave={(v) => save(row, { comment: v })} />
                </td>
                <td className="px-3 py-1.5">
                  {row.updated_by ? (
                    <button
                      onClick={() =>
                        setDrawer({
                          sliceKey: row.slice_key,
                          periodCode: row.period_code,
                          title: `${Object.values(row.slice_values).filter(Boolean).join(' · ')} — ${row.period_code}`,
                        })
                      }
                      className="text-left text-[11px] leading-tight text-muted hover:text-brandink hover:underline"
                      title="View change history"
                    >
                      {row.updated_by}
                      <br />
                      {row.updated_at ? fmtWhen(row.updated_at) : ''}
                    </button>
                  ) : (
                    <span className="text-[11px] text-muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted">
        Build-up = actuals + open pipeline weighted by{' '}
        {config.pipeline_weighting.mode === 'win_probability'
          ? 'opportunity win probability'
          : config.pipeline_weighting.mode === 'flat'
            ? `a flat ${Math.round((config.pipeline_weighting.rate ?? 0) * 100)}%`
            : '100%'}
        . Editing Adjustment or Total keeps them linked — the last edit wins. Amounts accept 1.2M / 500K shorthand.
      </p>

      {drawer && (
        <AuditDrawer
          configId={config.id}
          periodCode={drawer.periodCode}
          sliceKey={drawer.sliceKey}
          title={drawer.title}
          onClose={() => setDrawer(null)}
        />
      )}
    </div>
  )
}

function fmt(v: number): string {
  return Math.round(v).toLocaleString('en-US')
}
