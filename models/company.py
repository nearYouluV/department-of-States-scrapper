from sqlalchemy import Column, Integer, String, Date, DateTime
from models.base import Base
from datetime import datetime
from sqlalchemy.dialects.postgresql import ARRAY

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    source_state = Column(String)
    entity_number = Column(Integer, unique=True, index=True)
    entity_name = Column(String)
    entity_type = Column(String)
    entity_subtype = Column(String)
    status = Column(String)
    registration_date = Column(Date)
    last_filing_date = Column(Date)
    expiration_date = Column(Date)
    jurisdiction = Column(String)

    previous_names = Column(ARRAY(String))
    source_last_seen_at = Column(DateTime, default=datetime.utcnow)