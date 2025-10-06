from sqlalchemy import Column, Integer, String, Date, DateTime, Text
from models.base import Base
from datetime import datetime
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import  DeclarativeBase, Mapped, mapped_column
from typing import Optional, List
from datetime import date, datetime, timezone

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_state: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_subtype: Mapped[Optional[str]] = mapped_column(String(100))

    status: Mapped[str] = mapped_column(String(100), nullable=False)
    registration_date: Mapped[Optional[date]] = mapped_column(Date)
    next_filing_date: Mapped[Optional[date]] = mapped_column(Date)
    expiration_date: Mapped[Optional[date]] = mapped_column(Date)

    jurisdiction: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    principal_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    principal_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    principal_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    principal_postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    principal_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    mailing_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mailing_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mailing_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mailing_postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mailing_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    agent_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    agent_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    agent_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    agent_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    business_purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    incorporator_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    previous_names: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    document_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    source_detail_url: Mapped[str] = mapped_column(Text, nullable=True)
    source_last_seen_at: Mapped[Date] = mapped_column(Date, nullable=False, default=datetime.now(timezone.utc).date())