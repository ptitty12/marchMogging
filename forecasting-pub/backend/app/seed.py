"""Seed the skeleton environment.

Two business units configured deliberately differently, to exercise the
config-driven design end to end:

- Secure Power / SAO — Seller > Account > Product Bucket, with the real
  T&E lens rule (Transactional & Edge forecasts on Sales, everything else
  on Orders) and win-probability pipeline weighting.
- Digital Energy / Field Sales — Region > State > Product Rollup (custom
  bucket groupings) with a flat 40% pipeline weighting.

Facts span five quarters around the seeded "today" (2026-08-05): two closed
quarters of actuals, the in-flight quarter with partial actuals + open
pipeline, and two future quarters that are pipeline-only.

Idempotent: runs only when the database has no business units.
"""
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    BusinessUnit,
    FactOrdersSales,
    FactPipeline,
    ForecastConfig,
    ForecastEntry,
    Period,
)
from .services.grid import make_slice_key

TODAY = date(2026, 8, 5)

PERIODS = [
    ("2026 Q1", 2026, 1, date(2026, 1, 1), date(2026, 3, 31)),
    ("2026 Q2", 2026, 2, date(2026, 4, 1), date(2026, 6, 30)),
    ("2026 Q3", 2026, 3, date(2026, 7, 1), date(2026, 9, 30)),
    ("2026 Q4", 2026, 4, date(2026, 10, 1), date(2026, 12, 31)),
    ("2027 Q1", 2027, 1, date(2027, 1, 1), date(2027, 3, 31)),
]

SP_SELLERS = {
    "Adam Roberts": ["Switch Communications", "Vantage Data Centers", "Iron Mountain DC"],
    "Maria Chen": ["Equinix", "Digital Realty"],
    "DeShawn Carter": ["Microsoft", "CoreWeave"],
    "Priya Natarajan": ["Meta Platforms", "Oracle Cloud"],
}
SP_BUCKETS = ["3ph", "Cooling", "Modular DC", "Racks & PDU", "Software", "Transactional & Edge"]

DE_REGIONS = {
    "Northeast": ["NY", "MA", "PA"],
    "South": ["TX", "FL", "GA"],
    "West": ["CA", "WA", "AZ"],
}
DE_BUCKETS = ["Metering", "Protection Relays", "Grid Software", "Switchgear", "Transformers", "EcoStruxure Services"]
DE_ROLLUPS = {
    "Grid Hardware": ["Switchgear", "Transformers", "Protection Relays"],
    "Digital Grid": ["Grid Software", "Metering"],
    "Services": ["EcoStruxure Services"],
}

PIPE_STAGES = [("Identify", 0.10), ("Qualify", 0.25), ("Propose", 0.45), ("Negotiate", 0.70), ("Commit", 0.90)]


def _rand_day(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def seed_if_empty(db: Session) -> bool:
    if db.scalar(select(BusinessUnit).limit(1)):
        return False

    for code, year, quarter, start, end in PERIODS:
        db.add(Period(code=code, year=year, quarter=quarter, start_date=start, end_date=end))

    sp = BusinessUnit(code="SP", name="Secure Power", description="UPS, cooling, racks, DC infrastructure")
    de = BusinessUnit(code="DE", name="Digital Energy", description="Grid automation, metering, power systems")
    db.add_all([sp, de])
    db.flush()

    sp_cfg = ForecastConfig(
        business_unit_id=sp.id,
        name="SAO",
        levels=[
            {"key": "seller", "label": "Seller"},
            {"key": "account", "label": "Account"},
            {"key": "product_bucket", "label": "Product Bucket"},
        ],
        metric_rules={
            "default": "orders",
            "overrides": [
                {"field": "product_line", "equals": "Transactional & Edge", "metric": "sales"}
            ],
        },
        pipeline_weighting={"mode": "win_probability"},
        fact_filters={"business_unit": ["Secure Power"]},
        source_orders_view="partnersalesops.dbo.sp_ons",
        source_pipeline_view="partnersalesops.dbo.UsPipelineStandards",
    )
    de_cfg = ForecastConfig(
        business_unit_id=de.id,
        name="Field Sales",
        levels=[
            {"key": "region", "label": "Region"},
            {"key": "state", "label": "State"},
            {"key": "product_rollup", "label": "Product Group"},
        ],
        metric_rules={"default": "orders", "overrides": []},
        pipeline_weighting={"mode": "flat", "rate": 0.4},
        fact_filters={"business_unit": ["Digital Energy"]},
        bucket_rollups=DE_ROLLUPS,
    )
    db.add_all([sp_cfg, de_cfg])
    db.flush()

    rng = random.Random(51)  # deterministic seed data

    def add_ons(period_end_cap: date, code: str, start: date, end: date, **dims):
        end = min(end, period_end_cap)
        if start > end:
            return
        for txn_type in ("Orders", "Sales"):
            n = rng.randint(2, 5)
            for _ in range(n):
                db.add(
                    FactOrdersSales(
                        transaction_date=_rand_day(rng, start, end),
                        fiscal_period=code,
                        transaction_type=txn_type,
                        amount=round(rng.uniform(80_000, 2_400_000), 2),
                        **dims,
                    )
                )

    opp_counter = [0]

    def add_pipeline(code: str, start: date, end: date, **dims):
        for _ in range(rng.randint(1, 4)):
            opp_counter[0] += 1
            stage, prob = rng.choice(PIPE_STAGES)
            db.add(
                FactPipeline(
                    opportunity_id=f"OPP-{opp_counter[0]:05d}",
                    opportunity_name=f"{dims.get('account') or dims.get('state')} {dims['product_bucket']} project",
                    close_date=_rand_day(rng, max(start, TODAY), end) if end >= TODAY else _rand_day(rng, start, end),
                    fiscal_period=code,
                    stage=stage,
                    status="Open",
                    win_probability=prob,
                    amount=round(rng.uniform(150_000, 5_000_000), 2),
                    **dims,
                )
            )

    for code, _, _, start, end in PERIODS:
        past = end < TODAY
        current = start <= TODAY <= end

        # Secure Power: seller/account/bucket grain
        for seller, accounts in SP_SELLERS.items():
            for account in accounts:
                for bucket in rng.sample(SP_BUCKETS, rng.randint(3, 5)):
                    dims = dict(
                        business_unit="Secure Power",
                        manager="Dana Whitfield",
                        seller=seller,
                        region="NAM",
                        account_segment="Cloud & Service Provider",
                        state=rng.choice(["NV", "VA", "TX", "OR"]),
                        country="US",
                        account=account,
                        product_bucket=bucket,
                        product_line=bucket,
                    )
                    if past or current:
                        add_ons(TODAY if current else end, code, start, end, **dims)
                    if not past and rng.random() < 0.8:
                        add_pipeline(code, start, end, **dims)

        # Digital Energy: region/state/bucket grain
        for region, states in DE_REGIONS.items():
            for state in states:
                for bucket in rng.sample(DE_BUCKETS, rng.randint(3, 5)):
                    dims = dict(
                        business_unit="Digital Energy",
                        manager="Luis Ortega",
                        seller=rng.choice(["Sam Patel", "Jo Lindqvist", "Terry Adams"]),
                        region=region,
                        account_segment="Utilities",
                        state=state,
                        country="US",
                        account=f"{state} Utility Co",
                        product_bucket=bucket,
                        product_line=bucket,
                    )
                    if past or current:
                        add_ons(TODAY if current else end, code, start, end, **dims)
                    if not past and rng.random() < 0.7:
                        add_pipeline(code, start, end, **dims)

    # A few pre-existing rep entries so the grid shows lived-in state.
    sample_entries = [
        dict(
            period_code="2026 Q3",
            slice_values={"seller": "Adam Roberts", "account": "Switch Communications", "product_bucket": "3ph"},
            adjustment=-1_250_000.0,
            comment="Hyper Solutions GVXL rollout slipping to Q4 — pulled 2 units out.",
            updated_by="adam.roberts",
        ),
        dict(
            period_code="2026 Q3",
            slice_values={"seller": "Adam Roberts", "account": "Switch Communications", "product_bucket": "Modular DC"},
            adjustment=800_000.0,
            comment="Ph2 expansion verbal, PO expected mid-Sep.",
            updated_by="adam.roberts",
        ),
        dict(
            period_code="2026 Q4",
            slice_values={"seller": "Maria Chen", "account": "Equinix", "product_bucket": "Cooling"},
            total_forecast=6_500_000.0,
            comment="Committing at 6.5M — liquid cooling retrofit locked in.",
            updated_by="maria.chen",
        ),
    ]
    for item in sample_entries:
        slice_values = item.pop("slice_values")
        db.add(
            ForecastEntry(
                config_id=sp_cfg.id,
                slice_key=make_slice_key(sp_cfg.levels, slice_values),
                slice_values=slice_values,
                **item,
            )
        )

    db.commit()
    return True
