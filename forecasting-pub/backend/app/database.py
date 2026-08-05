"""Database setup.

SQLite by default for local dev. Set DATABASE_URL to point at SQL Server
(mssql+pyodbc://...) when wiring up the real PartnerSalesOps-hosted tables.
The app only ever READS the fact tables (orders/sales, pipeline) — they are
managed by external processes in production.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./forecasting_pub.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
