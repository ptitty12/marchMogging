"""Reference data: periods and the standard dimension catalog."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Period
from ..schemas import DimensionOut, PeriodOut
from ..services.grid import ROLLUP_DIMENSION

router = APIRouter(prefix="/api", tags=["meta"])

DIMENSION_CATALOG: list[DimensionOut] = [
    DimensionOut(key="manager", label="Manager"),
    DimensionOut(key="seller", label="Seller"),
    DimensionOut(key="region", label="Region"),
    DimensionOut(key="account_segment", label="Account Segment"),
    DimensionOut(key="state", label="State"),
    DimensionOut(key="country", label="Country"),
    DimensionOut(key="account", label="Account"),
    DimensionOut(key="product_bucket", label="Product Bucket"),
    DimensionOut(key="product_line", label="Product Line"),
    DimensionOut(
        key=ROLLUP_DIMENSION,
        label="Product Rollup",
        derived=True,
        description="Custom groupings of product buckets, defined per config via bucket_rollups.",
    ),
]


@router.get("/periods", response_model=list[PeriodOut])
def list_periods(db: Session = Depends(get_db)):
    return db.scalars(select(Period).order_by(Period.year, Period.quarter)).all()


@router.get("/dimensions", response_model=list[DimensionOut])
def list_dimensions():
    return DIMENSION_CATALOG
