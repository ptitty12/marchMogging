import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, getUser, setUser } from './api/client'
import type { BusinessUnit, Dimension, Period } from './types'
import { ForecastPage } from './pages/ForecastPage'
import { AdminPage } from './pages/AdminPage'

type Tab = 'forecast' | 'admin'

export default function App() {
  const [tab, setTab] = useState<Tab>('forecast')
  const [businessUnits, setBusinessUnits] = useState<BusinessUnit[]>([])
  const [periods, setPeriods] = useState<Period[]>([])
  const [dimensions, setDimensions] = useState<Dimension[]>([])
  const [configId, setConfigId] = useState<number | null>(null)
  const [userText, setUserText] = useState(getUser())
  const [loadError, setLoadError] = useState<string | null>(null)

  const reload = useCallback(() => {
    Promise.all([api.businessUnits(), api.periods(), api.dimensions()])
      .then(([bus, pds, dims]) => {
        setBusinessUnits(bus)
        setPeriods(pds)
        setDimensions(dims)
        setLoadError(null)
        setConfigId((cur) => {
          const all = bus.flatMap((b) => b.configs)
          if (cur && all.some((c) => c.id === cur)) return cur
          return all[0]?.id ?? null
        })
      })
      .catch((e) => setLoadError(String(e)))
  }, [])

  useEffect(reload, [reload])

  const activeConfig = useMemo(() => {
    for (const bu of businessUnits) {
      const cfg = bu.configs.find((c) => c.id === configId)
      if (cfg) return { bu, cfg }
    }
    return null
  }, [businessUnits, configId])

  return (
    <div className="min-h-screen">
      <header className="border-b border-hairline bg-surface">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-lg bg-brandink text-sm font-bold text-white dark:text-black">
              FP
            </div>
            <div>
              <h1 className="text-sm leading-tight font-semibold">Forecasting Pub</h1>
              <p className="text-[11px] leading-tight text-muted">Schneider Electric · one place to call your number</p>
            </div>
          </div>

          <nav className="flex gap-1 text-sm" aria-label="Main">
            {(['forecast', 'admin'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-lg px-3 py-1.5 font-medium capitalize ${
                  tab === t ? 'bg-brandwash text-brandink' : 'text-ink2 hover:bg-page'
                }`}
              >
                {t === 'forecast' ? 'Forecast' : 'Administration'}
              </button>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {tab === 'forecast' && (
              <select
                value={configId ?? ''}
                onChange={(e) => setConfigId(Number(e.target.value))}
                className="max-w-64 rounded-lg border border-hairline bg-page px-3 py-1.5 text-sm"
                aria-label="Forecast view"
              >
                {businessUnits.map((bu) => (
                  <optgroup key={bu.id} label={`${bu.name} (${bu.code})`}>
                    {bu.configs.map((cfg) => (
                      <option key={cfg.id} value={cfg.id}>
                        {bu.code} · {cfg.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            )}
            <label className="flex items-center gap-1.5 text-xs text-muted">
              <span>Signed in as</span>
              <input
                className="w-32 rounded-lg border border-hairline bg-page px-2 py-1.5 text-xs text-ink"
                value={userText}
                onChange={(e) => setUserText(e.target.value)}
                onBlur={() => setUser(userText.trim() || 'demo.user')}
                title="Placeholder identity — swaps for SSO"
              />
            </label>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-5">
        {loadError && (
          <div className="mb-4 rounded-lg border border-neg bg-negwash px-4 py-3 text-sm text-neg">
            Backend unreachable: {loadError} — is the API running on :8000?
          </div>
        )}
        {tab === 'forecast' &&
          (activeConfig ? (
            <>
              <div className="mb-4">
                <h2 className="text-lg font-semibold">
                  {activeConfig.bu.name} — {activeConfig.cfg.name}
                </h2>
                <p className="text-xs text-muted">
                  Forecasting by {activeConfig.cfg.levels.map((l) => l.label).join(' → ')}
                </p>
              </div>
              <ForecastPage key={activeConfig.cfg.id} config={activeConfig.cfg} periods={periods} />
            </>
          ) : (
            !loadError && <p className="text-sm text-muted">No forecast configs yet — onboard a team under Administration.</p>
          ))}
        {tab === 'admin' && (
          <AdminPage businessUnits={businessUnits} dimensions={dimensions} onChanged={reload} />
        )}
      </main>
    </div>
  )
}
