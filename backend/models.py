from datetime import date
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

CLASSES = ('O1','O2','S1','S2','S3','V1','V2','P','J','Q1','Q2a','Q2b','SbS')

class Driver(Base):
    __tablename__ = 'drivers'
    id: Mapped[int] = mapped_column(primary_key=True)
    start_number: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(default='')
    email: Mapped[str] = mapped_column(default='')
    club: Mapped[str] = mapped_column(default='')
    adac_number: Mapped[str] = mapped_column(default='')
    __table_args__ = (CheckConstraint('start_number > 0'),)

class Vehicle(Base):
    __tablename__ = 'vehicles'
    id: Mapped[int] = mapped_column(primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    year: Mapped[str] = mapped_column(default='')
    plate: Mapped[str] = mapped_column(default='')
    tyres: Mapped[str] = mapped_column(default='')
    kind: Mapped[str] = mapped_column(default='offroad')
    length_cm: Mapped[int | None]
    width_cm: Mapped[int | None]
    wheelbase_cm: Mapped[int | None]
    front_lock: Mapped[bool] = mapped_column(default=False)
    rear_lock: Mapped[bool] = mapped_column(default=False)
    traction_control: Mapped[bool] = mapped_column(default=False)
    closed_body: Mapped[bool] = mapped_column(default=False)
    class_code: Mapped[str] = mapped_column(String(10))
    hcf: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    hcf_note: Mapped[str] = mapped_column(default='Technische Abnahme: manuell bestätigt')
    __table_args__ = (CheckConstraint('hcf > 0'),)

class DriverVehicle(Base):
    __tablename__ = 'driver_vehicles'
    driver_id: Mapped[int] = mapped_column(ForeignKey('drivers.id'), primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey('vehicles.id'), primary_key=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (Index('one_default_per_driver', 'driver_id', unique=True, sqlite_where=text('is_default = 1')),)

class Event(Base):
    __tablename__ = 'events'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    event_date: Mapped[date] = mapped_column(Date)
    location: Mapped[str] = mapped_column(default='')
    organizer: Mapped[str] = mapped_column(default='')
    section_count: Mapped[int]
    rounds: Mapped[int] = mapped_column(default=1)
    rules_version: Mapped[str] = mapped_column(default='ADAC-SH-2026-03-09')
    __table_args__ = (CheckConstraint('section_count BETWEEN 1 AND 30'), CheckConstraint('rounds BETWEEN 1 AND 10'))

class Entry(Base):
    __tablename__ = 'entries'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'))
    driver_id: Mapped[int] = mapped_column(ForeignKey('drivers.id'))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey('vehicles.id'))
    start_number: Mapped[int]
    driver_name: Mapped[str]
    vehicle_snapshot: Mapped[dict] = mapped_column(JSON)
    driver_snapshot: Mapped[dict | None] = mapped_column(JSON)
    class_code: Mapped[str]
    hcf: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    codriver: Mapped[str] = mapped_column(default='')
    paid: Mapped[bool] = mapped_column(default=False)
    technical_approved: Mapped[bool] = mapped_column(default=False)
    paperwork_approved: Mapped[bool] = mapped_column(default=False)
    card_status: Mapped[str] = mapped_column(default='missing')
    scoring_status: Mapped[str] = mapped_column(default='pending')
    niw_reason: Mapped[str] = mapped_column(default='')
    version: Mapped[int] = mapped_column(default=1)
    card_summary: Mapped[dict | None] = mapped_column(JSON)
    results: Mapped[list['SectionResult']] = relationship(cascade='all, delete-orphan', order_by='SectionResult.ordinal')
    __mapper_args__ = {'version_id_col': version, 'version_id_generator': False}
    __table_args__ = (
        UniqueConstraint('event_id','driver_id'), UniqueConstraint('event_id','start_number'),
        CheckConstraint("card_status IN ('missing','received')"),
        CheckConstraint("scoring_status IN ('pending','complete','niw')"),
        CheckConstraint("scoring_status != 'niw' OR length(niw_reason) > 0"),
        CheckConstraint('hcf > 0'),
    )

class SectionResult(Base):
    __tablename__ = 'section_results'
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey('entries.id'))
    ordinal: Mapped[int]
    # Final paper score, including applicable HCF. Never divide the total again.
    points: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    error_counts: Mapped[dict | None] = mapped_column(JSON)
    error1: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    error2: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    driven: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (UniqueConstraint('entry_id','ordinal'), CheckConstraint('ordinal > 0'), CheckConstraint('points IS NULL OR points >= 0'))

class EntryChange(Base):
    __tablename__ = 'entry_changes'
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey('entries.id'),index=True)
    changed_at: Mapped[str]
    reason: Mapped[str]
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)


class EventClass(Base):
    __tablename__ = 'event_classes'
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'),primary_key=True)
    code: Mapped[str] = mapped_column(String(30),primary_key=True)
    section_group: Mapped[str] = mapped_column(default='')
    required_sections: Mapped[int] = mapped_column(default=5,server_default='5')
    trophy_count: Mapped[int | None]

class Team(Base):
    __tablename__ = 'teams'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'))
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(default=1)
    members: Mapped[list['TeamMember']] = relationship(cascade='all, delete-orphan')
    __mapper_args__ = {'version_id_col': version, 'version_id_generator': False}
    __table_args__ = (UniqueConstraint('event_id','name'),)

class TeamMember(Base):
    __tablename__ = 'team_members'
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'),primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey('entries.id'),primary_key=True)
