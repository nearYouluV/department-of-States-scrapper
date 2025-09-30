from models.base import Base
from sqlalchemy import Column, String, Date, func
from datetime import date


class ScraperCheckpoint(Base):
    __tablename__ = "scraper_checkpoints"

    id = Column(String, primary_key=True, default=f"daily_{date.today()}")  # one record per day only
    last_prefix = Column(String, nullable=True)
    updated_at = Column(Date, server_default=func.current_date(), onupdate=func.current_date())