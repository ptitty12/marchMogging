"""The forecast grid engine.

Turns (config, periods) into grid rows:

    actuals-to-date            sum of OnS facts, metric chosen per row by the
                               config's lens rules (orders vs sales)
    open pipeline              sum of open bfo opportunities closing in period
    suggested (all bfo)        actuals + 100% of open pipeline
    suggested (build-up)       actuals + weighted open pipeline
    adjustment / total / comment   rep input from ForecastEntry

Slicing is fully config-driven: rows are grouped by the config's declared
levels, which reference standard dimension columns or the derived
"product_rollup" dimension.

All grouping happens in Python over period-filtered fact rows. That is the
right trade-off while the facts are skeletons; when the real sources are
wired in, push the aggregation into the source views if volumes demand it —
the interface of build_grid() doesn't change.
"""
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FactOrdersSales, FactPipeline, ForecastConfig, ForecastEntry

ROLLUP_DIMENSION = "product_rollup"
UNMAPPED_ROLLUP = "Other"


def make_slice_key(levels: list[dict], values: dict) -> str:
    return "||".join(f"{lv['key']}={values.get(lv['key']) or ''}" for lv in levels)


def metric_for_row(metric_rules: dict, row: dict) -> str:
    """Pick 'orders' or 'sales' for one fact row via the config's lens rules."""
    for rule in metric_rules.get("overrides", []):
        if str(row.get(rule["field"], "")) == rule["equals"]:
            return rule["metric"]
    return metric_rules.get("default", "orders")


def resolve_dimension(config: ForecastConfig, row: dict, key: str) -> str:
    if key == ROLLUP_DIMENSION:
        bucket = row.get("product_bucket")
        for rollup_name, buckets in (config.bucket_rollups or {}).items():
            if bucket in buckets:
                return rollup_name
        return UNMAPPED_ROLLUP
    return row.get(key) or ""


def pipeline_weight(weighting: dict, row: dict) -> float:
    mode = weighting.get("mode", "win_probability")
    if mode == "all":
        return 1.0
    if mode == "flat":
        return float(weighting.get("rate", 0.5))
    return float(row.get("win_probability") or 0.0)


def _passes_filters(fact_filters: dict | None, row: dict) -> bool:
    if not fact_filters:
        return True
    for column, allowed in fact_filters.items():
        if row.get(column) not in allowed:
            return False
    return True


def _row_dict(obj) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


@dataclass
class GridRow:
    period_code: str
    slice_key: str
    slice_values: dict
    actuals: float = 0.0
    pipeline_open: float = 0.0
    pipeline_weighted: float = 0.0
    suggested_all_bfo: float = 0.0
    suggested_buildup: float = 0.0
    adjustment: float | None = None
    total_forecast: float | None = None
    effective_adjustment: float = 0.0
    effective_total: float = 0.0
    comment: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None
    has_entry: bool = field(default=False)


def build_grid(db: Session, config: ForecastConfig, period_codes: list[str]) -> list[GridRow]:
    levels = config.levels
    level_keys = [lv["key"] for lv in levels]

    ons_rows = [
        _row_dict(r)
        for r in db.scalars(
            select(FactOrdersSales).where(FactOrdersSales.fiscal_period.in_(period_codes))
        )
    ]
    pipe_rows = [
        _row_dict(r)
        for r in db.scalars(
            select(FactPipeline).where(
                FactPipeline.fiscal_period.in_(period_codes),
                FactPipeline.status == "Open",
            )
        )
    ]
    entries = db.scalars(
        select(ForecastEntry).where(
            ForecastEntry.config_id == config.id,
            ForecastEntry.period_code.in_(period_codes),
        )
    ).all()

    def slice_of(row: dict) -> tuple:
        return tuple(resolve_dimension(config, row, k) for k in level_keys)

    actuals: dict[tuple[str, tuple], float] = defaultdict(float)
    pipe_open: dict[tuple[str, tuple], float] = defaultdict(float)
    pipe_weighted: dict[tuple[str, tuple], float] = defaultdict(float)
    slice_universe: set[tuple] = set()

    for row in ons_rows:
        if not _passes_filters(config.fact_filters, row):
            continue
        metric = metric_for_row(config.metric_rules, row)
        wanted_type = "Orders" if metric == "orders" else "Sales"
        if row["transaction_type"] != wanted_type:
            continue
        s = slice_of(row)
        slice_universe.add(s)
        actuals[(row["fiscal_period"], s)] += row["amount"]

    for row in pipe_rows:
        if not _passes_filters(config.fact_filters, row):
            continue
        s = slice_of(row)
        slice_universe.add(s)
        key = (row["fiscal_period"], s)
        pipe_open[key] += row["amount"]
        pipe_weighted[key] += row["amount"] * pipeline_weight(config.pipeline_weighting, row)

    entry_map: dict[tuple[str, str], ForecastEntry] = {}
    for e in entries:
        entry_map[(e.period_code, e.slice_key)] = e
        slice_universe.add(tuple(e.slice_values.get(k) or "" for k in level_keys))

    # Every known slice appears in every requested period, so reps can enter
    # future quarters even where facts are still empty.
    rows: list[GridRow] = []
    for period in period_codes:
        for s in sorted(slice_universe):
            values = dict(zip(level_keys, s))
            skey = make_slice_key(levels, values)
            a = actuals.get((period, s), 0.0)
            po = pipe_open.get((period, s), 0.0)
            pw = pipe_weighted.get((period, s), 0.0)
            row = GridRow(
                period_code=period,
                slice_key=skey,
                slice_values=values,
                actuals=round(a, 2),
                pipeline_open=round(po, 2),
                pipeline_weighted=round(pw, 2),
                suggested_all_bfo=round(a + po, 2),
                suggested_buildup=round(a + pw, 2),
            )
            entry = entry_map.get((period, skey))
            if entry:
                row.has_entry = True
                row.adjustment = entry.adjustment
                row.total_forecast = entry.total_forecast
                row.comment = entry.comment
                row.updated_by = entry.updated_by
                row.updated_at = entry.updated_at.isoformat() if entry.updated_at else None
            # Precedence: an explicit total wins; else buildup + adjustment.
            if row.total_forecast is not None:
                row.effective_total = round(row.total_forecast, 2)
                row.effective_adjustment = round(row.total_forecast - row.suggested_buildup, 2)
            elif row.adjustment is not None:
                row.effective_adjustment = round(row.adjustment, 2)
                row.effective_total = round(row.suggested_buildup + row.adjustment, 2)
            else:
                row.effective_adjustment = 0.0
                row.effective_total = row.suggested_buildup
            rows.append(row)
    return rows
