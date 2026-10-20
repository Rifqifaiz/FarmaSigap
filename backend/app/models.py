"""ORM models FarmaSigap."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now()


class Puskesmas(Base):
    __tablename__ = "puskesmas"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)          # PKM-A
    code: Mapped[str] = mapped_column(String(4))                           # A
    name: Mapped[str] = mapped_column(String(120))
    district: Mapped[str] = mapped_column(String(80))
    province: Mapped[str] = mapped_column(String(80), default="Kalimantan Barat")
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    population_served: Mapped[int] = mapped_column(Integer)
    vulnerability_score: Mapped[float] = mapped_column(Float, default=0.5)
    # Bobot paparan asap (dipakai untuk membagi prediksi kasus kabupaten ke tiap PKM)
    smoke_exposure_weight: Mapped[float] = mapped_column(Float, default=1.0)
    description: Mapped[str] = mapped_column(Text, default="")

    inventory: Mapped[list["Inventory"]] = relationship(back_populates="puskesmas", cascade="all, delete-orphan")


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(80))
    form: Mapped[str] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(32))
    is_antibiotic: Mapped[bool] = mapped_column(Boolean, default=False)
    # Kata kunci pencocokan nama (dipakai pencocok donasi), dipisah koma
    aliases: Mapped[str] = mapped_column(Text, default="")
    # {"karhutla": {"priority": true, "proportion_treated": 0.12, "units_per_case": 1, "indication": "..."}}
    disaster_params: Mapped[dict] = mapped_column(JSON, default=dict)
    pharmacy_note: Mapped[str] = mapped_column(Text, default="")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("puskesmas_id", "medicine_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    puskesmas_id: Mapped[str] = mapped_column(ForeignKey("puskesmas.id"))
    medicine_id: Mapped[str] = mapped_column(ForeignKey("medicines.id"))
    current_stock: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    puskesmas: Mapped[Puskesmas] = relationship(back_populates="inventory")
    medicine: Mapped[Medicine] = relationship()


class HazardObservation(Base):
    """Observasi bahaya mingguan per kabupaten (agregat ISPU/PM2.5, FIRMS, BMKG)."""

    __tablename__ = "hazard_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district: Mapped[str] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    alert_level: Mapped[str] = mapped_column(String(80))
    pm25_avg: Mapped[float] = mapped_column(Float)
    pm25_max: Mapped[float] = mapped_column(Float)
    ispu_category: Mapped[str] = mapped_column(String(40))
    hotspot_count: Mapped[int] = mapped_column(Integer)
    rainfall_mm: Mapped[float] = mapped_column(Float)
    wind_direction: Mapped[str] = mapped_column(String(60), default="")
    wind_speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)


class FireHotspot(Base):
    __tablename__ = "fire_hotspots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    confidence_pct: Mapped[int] = mapped_column(Integer)
    land_type: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(40), default="NASA FIRMS VIIRS")
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ISPAWeeklyCase(Base):
    """Kunjungan ISPA mingguan tingkat kabupaten (laporan surveilans puskesmas)."""

    __tablename__ = "ispa_weekly_cases"
    __table_args__ = (UniqueConstraint("district", "week_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district: Mapped[str] = mapped_column(String(80))
    week_start: Mapped[date] = mapped_column(Date)
    epi_week: Mapped[int] = mapped_column(Integer)
    cases: Mapped[int] = mapped_column(Integer)
    pm25_avg: Mapped[float] = mapped_column(Float)
    pm25_max: Mapped[float] = mapped_column(Float)
    hotspot_count: Mapped[int] = mapped_column(Integer)
    rainfall_mm: Mapped[float] = mapped_column(Float)


class RoadDistance(Base):
    """Jarak tempuh jalan antar-PKM (jika tidak ada, dipakai haversine × faktor jalan)."""

    __tablename__ = "road_distances"
    __table_args__ = (UniqueConstraint("from_puskesmas_id", "to_puskesmas_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_puskesmas_id: Mapped[str] = mapped_column(ForeignKey("puskesmas.id"))
    to_puskesmas_id: Mapped[str] = mapped_column(ForeignKey("puskesmas.id"))
    distance_km: Mapped[float] = mapped_column(Float)


class RedistributionSuggestion(Base):
    __tablename__ = "redistribution_suggestions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    from_puskesmas_id: Mapped[str] = mapped_column(ForeignKey("puskesmas.id"))
    to_puskesmas_id: Mapped[str] = mapped_column(ForeignKey("puskesmas.id"))
    medicine_id: Mapped[str] = mapped_column(ForeignKey("medicines.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    distance_km: Mapped[float] = mapped_column(Float)
    estimated_delivery_hours: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(16))          # merah / kuning
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # angka donor & penerima saat usulan dibuat
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected/superseded
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    action_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    action_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    action_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    from_puskesmas: Mapped[Puskesmas] = relationship(foreign_keys=[from_puskesmas_id])
    to_puskesmas: Mapped[Puskesmas] = relationship(foreign_keys=[to_puskesmas_id])
    medicine: Mapped[Medicine] = relationship()


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    puskesmas_id: Mapped[str] = mapped_column(ForeignKey("puskesmas.id"))
    medicine_id: Mapped[str] = mapped_column(ForeignKey("medicines.id"))
    level: Mapped[str] = mapped_column(String(16))  # merah / kuning
    days_remaining: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    puskesmas: Mapped[Puskesmas] = relationship()
    medicine: Mapped[Medicine] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(40))   # redistribution / inventory
    entity_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now)
