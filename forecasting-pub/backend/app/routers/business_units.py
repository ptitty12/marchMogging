"""BU + forecast-config administration — how new teams get onboarded."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import BusinessUnit, ForecastConfig
from ..schemas import (
    BusinessUnitIn,
    BusinessUnitOut,
    ForecastConfigIn,
    ForecastConfigOut,
)
from ..routers.meta import DIMENSION_CATALOG

router = APIRouter(prefix="/api/business-units", tags=["business-units"])

VALID_DIMENSION_KEYS = {d.key for d in DIMENSION_CATALOG}


def _validate_config(payload: ForecastConfigIn) -> None:
    keys = [lv.key for lv in payload.levels]
    if len(set(keys)) != len(keys):
        raise HTTPException(422, "Levels must use distinct dimensions")
    for key in keys:
        if key not in VALID_DIMENSION_KEYS:
            raise HTTPException(422, f"Unknown dimension '{key}'")
    if "product_rollup" in keys and not payload.bucket_rollups:
        raise HTTPException(422, "product_rollup level requires bucket_rollups")
    if payload.metric_rules.get("default") not in ("orders", "sales"):
        raise HTTPException(422, "metric_rules.default must be 'orders' or 'sales'")
    if payload.pipeline_weighting.get("mode") not in ("win_probability", "flat", "all"):
        raise HTTPException(422, "pipeline_weighting.mode must be win_probability|flat|all")


@router.get("", response_model=list[BusinessUnitOut])
def list_business_units(db: Session = Depends(get_db)):
    return db.scalars(
        select(BusinessUnit).options(selectinload(BusinessUnit.configs)).order_by(BusinessUnit.name)
    ).all()


@router.post("", response_model=BusinessUnitOut, status_code=201)
def create_business_unit(payload: BusinessUnitIn, db: Session = Depends(get_db)):
    if db.scalar(select(BusinessUnit).where(BusinessUnit.code == payload.code)):
        raise HTTPException(409, f"Business unit '{payload.code}' already exists")
    bu = BusinessUnit(**payload.model_dump())
    db.add(bu)
    db.commit()
    db.refresh(bu)
    return bu


@router.post("/{bu_id}/configs", response_model=ForecastConfigOut, status_code=201)
def create_config(bu_id: int, payload: ForecastConfigIn, db: Session = Depends(get_db)):
    bu = db.get(BusinessUnit, bu_id)
    if not bu:
        raise HTTPException(404, "Business unit not found")
    _validate_config(payload)
    existing = db.scalar(
        select(ForecastConfig).where(
            ForecastConfig.business_unit_id == bu_id, ForecastConfig.name == payload.name
        )
    )
    if existing:
        raise HTTPException(409, f"Config '{payload.name}' already exists for this BU")
    config = ForecastConfig(business_unit_id=bu_id, **payload.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.put("/configs/{config_id}", response_model=ForecastConfigOut)
def update_config(config_id: int, payload: ForecastConfigIn, db: Session = Depends(get_db)):
    config = db.get(ForecastConfig, config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    _validate_config(payload)
    for k, v in payload.model_dump().items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config
