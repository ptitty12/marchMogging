# Forecasting Pub 🍺

Centralized forecasting for Schneider Electric sales teams — the enterprise
replacement for the SharePoint/PowerApp forecasting hub. Reps enter where
they'll land this quarter (and future quarters); the app suggests a number
from orders/sales actuals plus open bfo pipeline, and keeps a full audit
trail of every change.

## The core idea: forecasting shape is configuration, not code

Twelve BUs, every one slicing differently (Seller/Account/Product,
Region/State/Product-group, Manager/Segment, …) — and no realistic path to
standardizing them. So the app doesn't try. A **forecast config** declares,
as data:

| Config field | What it controls | Example (Secure Power SAO) |
|---|---|---|
| `levels` | The L1/L2/L3 the team forecasts to (1–3 of the standard dimensions) | Seller → Account → Product Bucket |
| `metric_rules` | Orders vs Sales, with per-row lens overrides | default orders; `product_line = 'Transactional & Edge'` → sales |
| `pipeline_weighting` | How open pipeline feeds the suggested forecast | opportunity win probability (others: flat %, 100%) |
| `bucket_rollups` | Custom product-bucket groupings (the derived `product_rollup` dimension) | Digital Energy groups 6 buckets into 3 |
| `fact_filters` | Row-level restriction of the standard tables | `business_unit = 'Secure Power'` |
| `source_*_view` | The real SQL views to read in production | `partnersalesops.dbo.sp_ons` |

Onboarding a new BU = one config (there's a UI for it under
**Administration**) — no schema changes, no new endpoints, no new screens.

## Architecture

```
 orders/sales feed ─┐                       ┌─ React + Vite + Tailwind SPA
 (external, read-   ├─> standard fact       │    · editable forecast grid
  only skeletons    │   tables (sqlite dev/ │    · grand-total stat tiles
  for now)          │   SQL Server prod)    │    · period chips, level filters
 bfo pipeline feed ─┘         │             │    · audit drawer
                              v             │    · admin / onboarding
                    FastAPI + SQLAlchemy ───┘
                      · suggested-forecast engine (grid.py)
                      · forecast entries + immutable audit
                      · config CRUD
```

- `backend/app/models.py` — three zones: read-only fact skeletons,
  configuration, forecast input. Start here.
- `backend/app/services/grid.py` — the engine: lens rules, pipeline
  weighting, slice grouping, suggested math, entry merge.
- `backend/app/seed.py` — deterministic demo world: 2 BUs configured
  differently, 5 quarters of facts, sample rep entries.
- `frontend/src/pages/ForecastPage.tsx` — the grid experience.
- `frontend/src/pages/AdminPage.tsx` — BU onboarding.

### Grid semantics (matches the current tool, formalized)

- **All-bfo suggested** = actuals-to-date + 100% of open pipeline.
- **Build-up suggested** = actuals-to-date + *weighted* open pipeline.
- **Total forecast** = build-up + adjustment. Reps can edit either the
  adjustment or the total; they stay linked and **the last edit wins**
  (an explicit total is stored and survives suggested-forecast drift).
- Every change to adjustment / total / comment writes a `forecast_audit`
  row: field, old → new, who, when.
- Future quarters are always enterable: the slice universe carries forward
  even where facts are empty.

## Run it

Backend (API on :8000, seeds itself on first start):

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (dev server on :5173, proxies /api to :8000):

```bash
cd frontend
npm install
npm run dev
```

Single container (frontend compiled in, FastAPI serves it):

```bash
docker build -t forecasting-pub .
docker run -p 8000:8000 forecasting-pub
```

Tests:

```bash
cd backend && python3 -m pytest tests/
```

## Wiring in the real sources

The app only ever **reads** the fact tables — they're skeletons today, fed
by `seed.py`. To swap in production data:

1. Point `DATABASE_URL` at SQL Server (`mssql+pyodbc://…`); the app's own
   tables (configs, entries, audit) create themselves.
2. Materialize each BU's source query into the standard fact shape
   (`fact_orders_sales`, `fact_pipeline` — see `models.py` for the standard
   dimension set). Each BU already maintains such a query today; the
   `source_orders_view` / `source_pipeline_view` config fields record which
   views those are.
3. If volumes get heavy, push the aggregation in
   `services/grid.py::build_grid` down into the source views — the function's
   interface is the seam; nothing above it changes.

Identity is a placeholder (`X-User` header, picked in the top bar). Swap-in
point for SSO: `current_user` in `backend/app/routers/forecast.py`.

## API sketch

| Method & path | What |
|---|---|
| `GET /api/business-units` | BUs with their configs |
| `POST /api/business-units` · `POST /api/business-units/{id}/configs` · `PUT /api/business-units/configs/{id}` | onboarding |
| `GET /api/periods` · `GET /api/dimensions` | reference data |
| `GET /api/forecast/grid?config_id&periods=…` | the computed grid |
| `PUT /api/forecast/configs/{id}/entries` | save adjustment / total / comment |
| `GET /api/forecast/configs/{id}/audit` | change history |

Interactive docs at `http://localhost:8000/docs`.
