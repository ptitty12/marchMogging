# Forecasting Pub — agent guide

Read `README.md` first for the architecture. This file is the working
contract for agents iterating on the codebase.

## Ground rules

- **The fact tables are read-only to the app.** `fact_orders_sales` and
  `fact_pipeline` are fed by external processes in production (seeded
  skeletons in dev). Never add app code that writes them outside `seed.py`.
- **BU differences belong in config, not code.** If a change is "BU X wants
  to slice/weight/lens differently," the answer is a `ForecastConfig` field
  (and, if new, its handling in `services/grid.py`) — never a BU-specific
  branch, endpoint, or component.
- **Every rep-input mutation must audit.** Any new editable field goes
  through the `upsert_entry` change-tracking pattern and lands in
  `forecast_audit`.
- **Orders ≠ Sales.** Orders = bookings, Sales = invoicing. Any fact query
  must filter `transaction_type`; the lens rules in `metric_rules` decide
  which one per row.
- Adjustment and total are linked, last-edit-wins. Preserve the
  `set_fields` semantics in `EntryUpsert` if you touch saving.

## Verify your work

```bash
cd backend && python3 -m pytest tests/          # must stay green
cd frontend && npx tsc -b && npm run build      # must stay clean
```

Run both servers (`uvicorn app.main:app --port 8000`, `npm run dev`) and
check the grid loads for BOTH seeded configs — they exercise different
code paths (rollup dimension, lens override, flat vs win-prob weighting).

## Style

- Backend: SQLAlchemy 2.0 typed mappings, pydantic v2, routers thin /
  services thick.
- Frontend: no state library — props down from `App.tsx`; Tailwind v4
  tokens defined in `src/index.css` (use `bg-surface`, `text-ink2`,
  `text-brandink`, etc., never raw hex in components); numeric cells get
  the `.tnum` class.
- Keep light AND dark mode working — tokens flip via
  `prefers-color-scheme`; check both when touching styles.
