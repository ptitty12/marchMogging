"""Pydantic schemas for the API surface."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# --- configuration -----------------------------------------------------------

class LevelDef(BaseModel):
    key: str
    label: str


class ForecastConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_unit_id: int
    name: str
    active: bool
    levels: list[LevelDef]
    metric_rules: dict
    pipeline_weighting: dict
    fact_filters: dict | None = None
    bucket_rollups: dict | None = None
    source_orders_view: str | None = None
    source_pipeline_view: str | None = None


class ForecastConfigIn(BaseModel):
    name: str
    levels: list[LevelDef] = Field(min_length=1, max_length=3)
    metric_rules: dict = {"default": "orders", "overrides": []}
    pipeline_weighting: dict = {"mode": "win_probability"}
    fact_filters: dict | None = None
    bucket_rollups: dict | None = None
    source_orders_view: str | None = None
    source_pipeline_view: str | None = None


class BusinessUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None = None
    configs: list[ForecastConfigOut] = []


class BusinessUnitIn(BaseModel):
    code: str
    name: str
    description: str | None = None


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    year: int
    quarter: int
    start_date: date
    end_date: date


class DimensionOut(BaseModel):
    key: str
    label: str
    derived: bool = False
    description: str | None = None


# --- grid --------------------------------------------------------------------

class GridRowOut(BaseModel):
    period_code: str
    slice_key: str
    slice_values: dict
    actuals: float
    pipeline_open: float
    pipeline_weighted: float
    suggested_all_bfo: float
    suggested_buildup: float
    adjustment: float | None
    total_forecast: float | None
    effective_adjustment: float
    effective_total: float
    comment: str | None
    updated_by: str | None
    updated_at: str | None
    has_entry: bool


class GridOut(BaseModel):
    config: ForecastConfigOut
    periods: list[str]
    rows: list[GridRowOut]


# --- entry upsert ------------------------------------------------------------

class EntryUpsert(BaseModel):
    """One save from the grid.

    Exactly the fields present are applied. Setting `adjustment` clears any
    stored explicit total (and vice versa) so the last-edited value drives
    the effective total — unless both are sent together.
    """

    period_code: str
    slice_values: dict
    adjustment: float | None = None
    total_forecast: float | None = None
    comment: str | None = None
    set_fields: list[str] = Field(min_length=1)  # which of the 3 fields to apply


class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    config_id: int
    period_code: str
    slice_key: str
    slice_values: dict
    adjustment: float | None
    total_forecast: float | None
    comment: str | None
    updated_by: str
    updated_at: datetime


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    config_id: int
    period_code: str
    slice_key: str
    field: str
    old_value: str | None
    new_value: str | None
    changed_by: str
    changed_at: datetime
