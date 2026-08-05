import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { BusinessUnit, Dimension, MetricOverride } from '../types'

interface Props {
  businessUnits: BusinessUnit[]
  dimensions: Dimension[]
  onChanged: () => void
}

const WEIGHTING_LABEL: Record<string, string> = {
  win_probability: 'Win probability',
  flat: 'Flat rate',
  all: '100% of pipeline',
}

export function AdminPage({ businessUnits, dimensions, onChanged }: Props) {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
      <section className="space-y-4">
        <h2 className="text-sm font-semibold tracking-wide text-muted uppercase">Onboarded teams</h2>
        {businessUnits.map((bu) => (
          <div key={bu.id} className="rounded-xl border border-hairline bg-surface p-5">
            <div className="flex items-baseline gap-2">
              <span className="rounded bg-brandwash px-2 py-0.5 text-xs font-semibold text-brandink">{bu.code}</span>
              <h3 className="text-base font-semibold">{bu.name}</h3>
            </div>
            {bu.description && <p className="mt-1 text-xs text-muted">{bu.description}</p>}
            <div className="mt-3 space-y-3">
              {bu.configs.length === 0 && (
                <p className="text-xs text-muted italic">No forecast configs yet — add one from the panel.</p>
              )}
              {bu.configs.map((cfg) => (
                <div key={cfg.id} className="rounded-lg border border-line bg-page px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{cfg.name}</span>
                    <span className="text-xs text-muted">·</span>
                    {cfg.levels.map((lv, i) => (
                      <span key={lv.key} className="rounded-full border border-hairline bg-surface px-2 py-0.5 text-[11px] text-ink2">
                        L{i + 1} {lv.label}
                      </span>
                    ))}
                  </div>
                  <dl className="mt-2 grid gap-x-6 gap-y-1 text-[11px] text-muted sm:grid-cols-2">
                    <div>
                      <dt className="inline font-medium">Metric:</dt>{' '}
                      <dd className="inline">
                        {cfg.metric_rules.default}
                        {cfg.metric_rules.overrides.length > 0 &&
                          ` (+${cfg.metric_rules.overrides.length} lens rule${cfg.metric_rules.overrides.length > 1 ? 's' : ''})`}
                      </dd>
                    </div>
                    <div>
                      <dt className="inline font-medium">Pipeline weighting:</dt>{' '}
                      <dd className="inline">
                        {WEIGHTING_LABEL[cfg.pipeline_weighting.mode]}
                        {cfg.pipeline_weighting.mode === 'flat' && ` (${Math.round((cfg.pipeline_weighting.rate ?? 0) * 100)}%)`}
                      </dd>
                    </div>
                    {cfg.source_orders_view && (
                      <div className="sm:col-span-2">
                        <dt className="inline font-medium">Sources:</dt>{' '}
                        <dd className="inline">
                          {cfg.source_orders_view}
                          {cfg.source_pipeline_view && ` · ${cfg.source_pipeline_view}`}
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>

      <OnboardPanel businessUnits={businessUnits} dimensions={dimensions} onChanged={onChanged} />
    </div>
  )
}

function OnboardPanel({ businessUnits, dimensions, onChanged }: Props) {
  const [buMode, setBuMode] = useState<'existing' | 'new'>(businessUnits.length ? 'existing' : 'new')
  const [buId, setBuId] = useState<number | ''>('')
  const [newBu, setNewBu] = useState({ code: '', name: '', description: '' })
  const [configName, setConfigName] = useState('')
  const [levels, setLevels] = useState<string[]>(['', '', ''])
  const [metricDefault, setMetricDefault] = useState<'orders' | 'sales'>('orders')
  const [overrides, setOverrides] = useState<MetricOverride[]>([])
  const [weightMode, setWeightMode] = useState<'win_probability' | 'flat' | 'all'>('win_probability')
  const [flatRate, setFlatRate] = useState(40)
  const [rollupsText, setRollupsText] = useState('{\n  "Group A": ["bucket 1", "bucket 2"]\n}')
  const [sourceOrders, setSourceOrders] = useState('')
  const [sourcePipeline, setSourcePipeline] = useState('')
  const [status, setStatus] = useState<{ tone: 'ok' | 'err'; msg: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const usesRollup = levels.includes('product_rollup')
  const chosenLevels = levels.filter(Boolean)

  const labelFor = useMemo(
    () => Object.fromEntries(dimensions.map((d) => [d.key, d.label])),
    [dimensions],
  )

  const submit = async () => {
    setStatus(null)
    if (chosenLevels.length === 0) {
      setStatus({ tone: 'err', msg: 'Pick at least one level.' })
      return
    }
    if (!configName.trim()) {
      setStatus({ tone: 'err', msg: 'Name the forecast config (e.g. the sub-segment).' })
      return
    }
    let bucket_rollups: Record<string, string[]> | null = null
    if (usesRollup) {
      try {
        bucket_rollups = JSON.parse(rollupsText)
      } catch {
        setStatus({ tone: 'err', msg: 'Bucket rollups must be valid JSON.' })
        return
      }
    }
    setBusy(true)
    try {
      let targetBuId = buId
      if (buMode === 'new') {
        const created = await api.createBusinessUnit({
          code: newBu.code.trim(),
          name: newBu.name.trim(),
          description: newBu.description.trim() || undefined,
        })
        targetBuId = created.id
      }
      if (targetBuId === '') {
        setStatus({ tone: 'err', msg: 'Pick a business unit.' })
        return
      }
      await api.createConfig(targetBuId as number, {
        name: configName.trim(),
        levels: chosenLevels.map((key) => ({ key, label: labelFor[key] ?? key })),
        metric_rules: { default: metricDefault, overrides },
        pipeline_weighting: weightMode === 'flat' ? { mode: 'flat', rate: flatRate / 100 } : { mode: weightMode },
        bucket_rollups,
        source_orders_view: sourceOrders.trim() || null,
        source_pipeline_view: sourcePipeline.trim() || null,
      })
      setStatus({ tone: 'ok', msg: `“${configName.trim()}” onboarded — it's live in the forecast picker.` })
      setConfigName('')
      setOverrides([])
      onChanged()
    } catch (e) {
      setStatus({ tone: 'err', msg: String(e) })
    } finally {
      setBusy(false)
    }
  }

  const inputCls =
    'w-full rounded-lg border border-hairline bg-page px-3 py-2 text-sm text-ink outline-none focus:border-brandink'
  const labelCls = 'block text-xs font-medium text-ink2 mb-1'

  return (
    <section className="h-fit rounded-xl border border-hairline bg-surface p-5 lg:sticky lg:top-4">
      <h2 className="text-sm font-semibold tracking-wide text-muted uppercase">Onboard a team</h2>
      <p className="mt-1 text-xs text-muted">
        A team is live once it has a config: its levels, its metric lens, and how pipeline feeds the suggestion. No
        code required.
      </p>

      <div className="mt-4 space-y-4">
        <div>
          <span className={labelCls}>Business unit</span>
          <div className="flex gap-2 text-xs">
            {(['existing', 'new'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setBuMode(m)}
                className={`rounded-full border px-3 py-1 font-medium ${
                  buMode === m ? 'border-brandink bg-brandwash text-brandink' : 'border-hairline text-ink2'
                }`}
              >
                {m === 'existing' ? 'Existing' : 'New BU'}
              </button>
            ))}
          </div>
          {buMode === 'existing' ? (
            <select className={`${inputCls} mt-2`} value={buId} onChange={(e) => setBuId(Number(e.target.value) || '')}>
              <option value="">Select…</option>
              {businessUnits.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.code})
                </option>
              ))}
            </select>
          ) : (
            <div className="mt-2 grid grid-cols-[90px_1fr] gap-2">
              <input
                className={inputCls}
                placeholder="Code"
                value={newBu.code}
                onChange={(e) => setNewBu({ ...newBu, code: e.target.value })}
              />
              <input
                className={inputCls}
                placeholder="Name"
                value={newBu.name}
                onChange={(e) => setNewBu({ ...newBu, name: e.target.value })}
              />
              <input
                className={`${inputCls} col-span-2`}
                placeholder="Description (optional)"
                value={newBu.description}
                onChange={(e) => setNewBu({ ...newBu, description: e.target.value })}
              />
            </div>
          )}
        </div>

        <div>
          <label className={labelCls}>Config name (sub-segment)</label>
          <input
            className={inputCls}
            placeholder="e.g. SAO, Field Sales, OEM"
            value={configName}
            onChange={(e) => setConfigName(e.target.value)}
          />
        </div>

        <div>
          <span className={labelCls}>Forecast levels — how this team slices</span>
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <select
                key={i}
                className={inputCls}
                value={levels[i]}
                onChange={(e) => setLevels(levels.map((v, j) => (j === i ? e.target.value : v)))}
              >
                <option value="">{i === 0 ? 'L1 (required)' : `L${i + 1} (optional)`}</option>
                {dimensions
                  .filter((d) => !levels.includes(d.key) || levels[i] === d.key)
                  .map((d) => (
                    <option key={d.key} value={d.key}>
                      {d.label}
                      {d.derived ? ' (derived)' : ''}
                    </option>
                  ))}
              </select>
            ))}
          </div>
        </div>

        {usesRollup && (
          <div>
            <label className={labelCls}>Bucket rollups (JSON: group → product buckets)</label>
            <textarea
              rows={4}
              className={`${inputCls} font-mono text-xs`}
              value={rollupsText}
              onChange={(e) => setRollupsText(e.target.value)}
            />
          </div>
        )}

        <div>
          <span className={labelCls}>Forecast metric</span>
          <div className="flex gap-2 text-xs">
            {(['orders', 'sales'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMetricDefault(m)}
                className={`rounded-full border px-3 py-1 font-medium capitalize ${
                  metricDefault === m ? 'border-brandink bg-brandwash text-brandink' : 'border-hairline text-ink2'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <div className="mt-2 space-y-1.5">
            {overrides.map((o, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs">
                <span className="text-muted">if</span>
                <input
                  className="w-24 rounded border border-hairline bg-page px-1.5 py-1"
                  placeholder="field"
                  value={o.field}
                  onChange={(e) => setOverrides(overrides.map((x, j) => (j === i ? { ...x, field: e.target.value } : x)))}
                />
                <span className="text-muted">=</span>
                <input
                  className="min-w-0 flex-1 rounded border border-hairline bg-page px-1.5 py-1"
                  placeholder="value"
                  value={o.equals}
                  onChange={(e) => setOverrides(overrides.map((x, j) => (j === i ? { ...x, equals: e.target.value } : x)))}
                />
                <span className="text-muted">→</span>
                <select
                  className="rounded border border-hairline bg-page px-1.5 py-1"
                  value={o.metric}
                  onChange={(e) => setOverrides(overrides.map((x, j) => (j === i ? { ...x, metric: e.target.value } : x)))}
                >
                  <option value="orders">orders</option>
                  <option value="sales">sales</option>
                </select>
                <button onClick={() => setOverrides(overrides.filter((_, j) => j !== i))} className="px-1 text-muted hover:text-neg">
                  ✕
                </button>
              </div>
            ))}
            <button
              onClick={() => setOverrides([...overrides, { field: 'product_line', equals: '', metric: 'sales' }])}
              className="text-xs font-medium text-brandink hover:underline"
            >
              + Add lens rule (e.g. T&E forecasts on sales)
            </button>
          </div>
        </div>

        <div>
          <span className={labelCls}>Pipeline weighting in the suggested forecast</span>
          <div className="flex flex-wrap gap-2 text-xs">
            {(Object.keys(WEIGHTING_LABEL) as Array<keyof typeof WEIGHTING_LABEL>).map((m) => (
              <button
                key={m}
                onClick={() => setWeightMode(m as typeof weightMode)}
                className={`rounded-full border px-3 py-1 font-medium ${
                  weightMode === m ? 'border-brandink bg-brandwash text-brandink' : 'border-hairline text-ink2'
                }`}
              >
                {WEIGHTING_LABEL[m]}
              </button>
            ))}
          </div>
          {weightMode === 'flat' && (
            <div className="mt-2 flex items-center gap-2 text-xs text-ink2">
              <input
                type="range"
                min={5}
                max={100}
                step={5}
                value={flatRate}
                onChange={(e) => setFlatRate(Number(e.target.value))}
                className="flex-1 accent-(--brand)"
              />
              <span className="tnum w-10 text-right font-medium">{flatRate}%</span>
            </div>
          )}
        </div>

        <details>
          <summary className="cursor-pointer text-xs font-medium text-ink2">Production source views (optional)</summary>
          <div className="mt-2 space-y-2">
            <input
              className={inputCls}
              placeholder="Orders/sales view, e.g. partnersalesops.dbo.sp_ons"
              value={sourceOrders}
              onChange={(e) => setSourceOrders(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Pipeline view, e.g. ...UsPipelineStandards"
              value={sourcePipeline}
              onChange={(e) => setSourcePipeline(e.target.value)}
            />
          </div>
        </details>

        {status && (
          <div
            className={`rounded-lg px-3 py-2 text-xs ${
              status.tone === 'ok' ? 'bg-brandwash text-brandink' : 'bg-negwash text-neg'
            }`}
          >
            {status.msg}
          </div>
        )}

        <button
          onClick={submit}
          disabled={busy}
          className="w-full rounded-lg bg-brandink py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 dark:text-black"
        >
          {busy ? 'Onboarding…' : 'Onboard team'}
        </button>
      </div>
    </section>
  )
}
