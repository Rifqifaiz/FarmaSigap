from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import FireHotspot
from app.schemas import DisasterType, HazardMappingRequest, HazardMappingResponse
from app.services.forecasting import latest_hazard
from app.services.hazard_drug import DISASTER_PROFILES, build_mapping
from app.services.stock import puskesmas_summary

router = APIRouter(prefix="/api/hazard", tags=["Hazard-to-Drug & Early Warning"])


@router.get("/types")
def list_disaster_types() -> Dict[str, Any]:
    """Daftar jenis bencana yang didukung Hazard-to-Drug Engine."""
    return {
        "status": "success",
        "active_disaster": settings.active_disaster,
        "data": [{"disaster_type": k, "label": v["label"]} for k, v in DISASTER_PROFILES.items()],
    }


@router.get("/mapping/{disaster_type}", response_model=HazardMappingResponse)
def get_hazard_mapping(disaster_type: DisasterType, db: Session = Depends(get_db)):
    """Pemetaan jenis bencana -> penyakit dominan -> obat prioritas (+ catatan farmasi)."""
    return build_mapping(db, disaster_type)


@router.post("/drug-mapping", response_model=HazardMappingResponse)
def post_hazard_mapping(req: HazardMappingRequest, db: Session = Depends(get_db)):
    """Versi POST dari pemetaan Hazard-to-Drug."""
    return build_mapping(db, req.disaster_type)


@router.get("/telemetry")
def get_hazard_telemetry(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Status bahaya terkini (PM2.5/ISPU, titik panas, curah hujan, angin, status siaga)."""
    obs = latest_hazard(db)
    if obs is None:
        raise HTTPException(status_code=404, detail="Belum ada observasi bahaya")
    hotspots = db.scalars(select(FireHotspot).order_by(FireHotspot.confidence_pct.desc())).all()
    return {
        "status": "success",
        "data": {
            "region": f"Kabupaten {obs.district}, Kalimantan Barat",
            "disaster_type": settings.active_disaster,
            "alert_level": obs.alert_level,
            "pm25_val": obs.pm25_avg,
            "pm25_max": obs.pm25_max,
            "ispu_category": obs.ispu_category,
            "hotspot_count": obs.hotspot_count,
            "rainfall_mm": obs.rainfall_mm,
            "wind_direction": obs.wind_direction,
            "wind_speed_kmh": obs.wind_speed_kmh,
            "active_fire_clusters": [
                {"name": h.name, "lat": h.lat, "lng": h.lng, "confidence": f"{h.confidence_pct}%", "type": h.land_type, "source": h.source}
                for h in hotspots
            ],
            "updated_at": obs.observed_at.strftime("%Y-%m-%d %H:%M WIB"),
        },
    }


@router.get("/hotspots")
def get_hotspots(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Klaster titik panas aktif (NASA FIRMS)."""
    rows = db.scalars(select(FireHotspot).order_by(FireHotspot.confidence_pct.desc())).all()
    return {
        "status": "success",
        "total": len(rows),
        "data": [
            {"id": h.id, "name": h.name, "lat": h.lat, "lng": h.lng, "confidence_pct": h.confidence_pct,
             "land_type": h.land_type, "source": h.source, "detected_at": h.detected_at.isoformat(timespec="minutes")}
            for h in rows
        ],
    }


@router.get("/puskesmas")
def get_puskesmas_locations(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Koordinat, kerentanan, dan status stok terburuk 7 puskesmas mitra."""
    data = puskesmas_summary(db)
    return {"status": "success", "total": len(data), "data": data}
