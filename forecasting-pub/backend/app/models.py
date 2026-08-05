"""Data model for the Forecasting Pub.

Three zones:

1. SOURCE FACTS (read-only skeletons) — stand-ins for the real standard
   tables (sp_ons-shaped orders/sales, UsPipelineStandards-shaped pipeline).
   In production these are fed by external processes; the app never writes
   them. They carry a superset of the dimension columns any BU forecasts by,
   so a BU's "how we slice" is pure configuration.

2. CONFIGURATION — BusinessUnit + ForecastConfig. A ForecastConfig declares
   which dimension columns become that team's L1/L2/L3 levels, its metric
   lens rules (e.g. Secure Power's "T&E uses Sales, everything else Orders"),
   how open pipeline is weighted into the suggested forecast, and optional
   custom product-bucket rollups. Onboarding a new BU = inserting config
   rows, not writing code.

3. FORECAST INPUT — ForecastEntry (one row per config x period x slice) and
   ForecastAudit (immutable trail of every change).
"""
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Zone 1 — source facts (skeleton standard tables, read-only to the app)
# ---------------------------------------------------------------------------

# Dimension columns shared by both fact tables. Every dimension a BU might
# forecast by must exist here (or be derivable, like custom rollups).
STANDARD_DIMENSIONS = [
    "business_unit",
    "manager",
    "seller",
    "region",
    "account_segment",
    "state",
    "country",
    "account",
    "product_bucket",
    "product_line",
]


class FactOrdersSales(Base):
    """Skeleton of the standardized orders & sales table.

    Mirrors the conventions of the real thing: Orders = bookings,
    Sales = invoicing, and every query MUST filter transaction_type.
    """

    __tablename__ = "fact_orders_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    fiscal_period: Mapped[str] = mapped_column(String(16), index=True)  # e.g. "2026 Q3"
    transaction_type: Mapped[str] = mapped_column(String(16), index=True)  # Orders | Sales
    amount: Mapped[float] = mapped_column(Float)

    business_unit: Mapped[str] = mapped_column(String(64), index=True)
    manager: Mapped[str | None] = mapped_column(String(128))
    seller: Mapped[str | None] = mapped_column(String(128), index=True)
    region: Mapped[str | None] = mapped_column(String(64))
    account_segment: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(String(32))
    account: Mapped[str | None] = mapped_column(String(128), index=True)
    product_bucket: Mapped[str | None] = mapped_column(String(64))
    product_line: Mapped[str | None] = mapped_column(String(64))


class FactPipeline(Base):
    """Skeleton of the standardized open-pipeline (bfo opportunity) table."""

    __tablename__ = "fact_pipeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(32), index=True)
    opportunity_name: Mapped[str | None] = mapped_column(String(256))
    close_date: Mapped[date] = mapped_column(Date, index=True)
    fiscal_period: Mapped[str] = mapped_column(String(16), index=True)
    stage: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)  # Open | Won | Lost
    win_probability: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    amount: Mapped[float] = mapped_column(Float)

    business_unit: Mapped[str] = mapped_column(String(64), index=True)
    manager: Mapped[str | None] = mapped_column(String(128))
    seller: Mapped[str | None] = mapped_column(String(128), index=True)
    region: Mapped[str | None] = mapped_column(String(64))
    account_segment: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(String(32))
    account: Mapped[str | None] = mapped_column(String(128), index=True)
    product_bucket: Mapped[str | None] = mapped_column(String(64))
    product_line: Mapped[str | None] = mapped_column(String(64))


class Period(Base):
    """Fiscal quarters available for forecasting."""

    __tablename__ = "periods"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)  # "2026 Q3"
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


# ---------------------------------------------------------------------------
# Zone 2 — configuration
# ---------------------------------------------------------------------------


class BusinessUnit(Base):
    __tablename__ = "business_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)

    configs: Mapped[list["ForecastConfig"]] = relationship(back_populates="business_unit")


class ForecastConfig(Base):
    """How one team forecasts. The heart of the config-driven design.

    levels: ordered list of {"key", "label"} — key is either a standard
        dimension column or "product_rollup" (derived via bucket_rollups).
        1 to 3 levels supported by the UI; the model allows more.
    metric_rules: {"default": "orders"|"sales",
                   "overrides": [{"field", "equals", "metric"}, ...]}
        Applied per fact row — this is how lens rules like
        "PM0LOB = 'Transactional & Edge' uses Sales" are expressed.
    pipeline_weighting: {"mode": "win_probability"} |
                        {"mode": "flat", "rate": 0.4} |
                        {"mode": "all"}
        How open pipeline contributes to the build-up suggested forecast.
        (The all-bfo-included suggested forecast always uses 100%.)
    fact_filters: optional {"column": [allowed values]} applied to both
        fact tables (e.g. restrict to the BU's own rows, exclude segments).
    bucket_rollups: optional {"Rollup name": ["bucket", ...]} enabling the
        derived "product_rollup" dimension.
    source_orders_view / source_pipeline_view: names of the real SQL
        views to read in production; unused while running on skeletons but
        stored now so swap-in is a config change.
    """

    __tablename__ = "forecast_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_unit_id: Mapped[int] = mapped_column(ForeignKey("business_units.id"))
    name: Mapped[str] = mapped_column(String(128))  # sub-segment, e.g. "SAO"
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    levels: Mapped[list] = mapped_column(JSON)
    metric_rules: Mapped[dict] = mapped_column(JSON, default=lambda: {"default": "orders", "overrides": []})
    pipeline_weighting: Mapped[dict] = mapped_column(JSON, default=lambda: {"mode": "win_probability"})
    fact_filters: Mapped[dict | None] = mapped_column(JSON)
    bucket_rollups: Mapped[dict | None] = mapped_column(JSON)
    source_orders_view: Mapped[str | None] = mapped_column(String(256))
    source_pipeline_view: Mapped[str | None] = mapped_column(String(256))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    business_unit: Mapped[BusinessUnit] = relationship(back_populates="configs")

    __table_args__ = (UniqueConstraint("business_unit_id", "name", name="uq_config_bu_name"),)


# ---------------------------------------------------------------------------
# Zone 3 — forecast input
# ---------------------------------------------------------------------------


class ForecastEntry(Base):
    """One editable row of the grid: config x period x slice.

    slice_key is the canonical identity string ("seller=A||account=B"),
    slice_values the same data as a dict for display/filtering.
    total_forecast, when set, wins; otherwise the effective total is
    suggested_buildup + adjustment (computed at read time).
    """

    __tablename__ = "forecast_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("forecast_configs.id"), index=True)
    period_code: Mapped[str] = mapped_column(String(16), index=True)
    slice_key: Mapped[str] = mapped_column(String(512))
    slice_values: Mapped[dict] = mapped_column(JSON)

    adjustment: Mapped[float | None] = mapped_column(Float)
    total_forecast: Mapped[float | None] = mapped_column(Float)
    comment: Mapped[str | None] = mapped_column(Text)

    updated_by: Mapped[str] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("config_id", "period_code", "slice_key", name="uq_entry_slice"),
        Index("ix_entry_lookup", "config_id", "period_code"),
    )


class ForecastAudit(Base):
    """Immutable audit trail: one row per field change."""

    __tablename__ = "forecast_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(Integer, index=True)
    period_code: Mapped[str] = mapped_column(String(16))
    slice_key: Mapped[str] = mapped_column(String(512))
    field: Mapped[str] = mapped_column(String(32))  # adjustment | total_forecast | comment
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(String(128))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
