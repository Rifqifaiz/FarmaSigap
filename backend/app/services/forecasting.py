"""Penghubung data surveilans di database dengan model prediksi ISPA."""

from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.ispa_model import forecaster
from app.models import HazardObservation, ISPAWeeklyCase, Puskesmas

_cache: Dict[tuple, Dict[str, Any]] = {}


def ispu_category(pm25: float) -> str:
    """Kategori ISPU PM2.5 (Permen LHK P.14/2020, µg/m³ rata-rata 24 jam)."""
    if pm25 <= 15.5:
        return "Baik"
    if pm25 <= 55.4:
        return "Sedang"
    if pm25 <= 150.4:
        return "Tidak Sehat"
    if pm25 <= 250.4:
        return "Sangat Tidak Sehat"
    return "Berbahaya"


def latest_hazard(db: Session, district: Optional[str] = None) -> Optional[HazardObservation]:
    district = district or settings.active_district
    return db.scalars(
        select(HazardObservation).where(HazardObservation.district == district).order_by(HazardObservation.observed_at.desc())
    ).first()


def case_history(db: Session, district: Optional[str] = None, weeks: int = 12) -> List[ISPAWeeklyCase]:
    district = district or settings.active_district
    rows = db.scalars(
        select(ISPAWeeklyCase).where(ISPAWeeklyCase.district == district).order_by(ISPAWeeklyCase.week_start.desc()).limit(weeks)
    ).all()
    return list(reversed(rows))


def district_forecast(db: Session, district: Optional[str] = None) -> Dict[str, Any]:
    """Prediksi 3 minggu ke depan untuk kabupaten aktif dari data terbaru di database."""
    district = district or settings.active_district
    history = case_history(db, district, weeks=4)
    hazard = latest_hazard(db, district)
    if len(history) < 4 or hazard is None:
        raise ValueError(f"Data surveilans {district} belum cukup (butuh 4 minggu kasus & observasi bahaya)")

    last = history[-1]
    key = (district, last.id, last.cases, hazard.id, forecaster.trained_at)
    if key in _cache:
        return _cache[key]

    lags = [h.cases for h in reversed(history)]  # lag1 = minggu terakhir
    result = forecaster.predict(
        kabupaten=district,
        epi_week=last.epi_week,
        pm25_avg=hazard.pm25_avg,
        pm25_max=hazard.pm25_max,
        hotspot_count=hazard.hotspot_count,
        rainfall_mm=hazard.rainfall_mm,
        lags=lags,
    )
    for f in result["forecasts"]:
        f["week_start"] = (last.week_start + timedelta(weeks=f["horizon_week"])).isoformat()
    result["based_on_week"] = {"week_start": last.week_start.isoformat(), "epi_week": last.epi_week, "cases": last.cases}
    result["inputs"] = {
        "pm25_avg": hazard.pm25_avg,
        "pm25_max": hazard.pm25_max,
        "hotspot_count": hazard.hotspot_count,
        "rainfall_mm": hazard.rainfall_mm,
        "ispa_lags": lags,
    }
    _cache.clear()
    _cache[key] = result
    return result


def puskesmas_weight(pkm: Puskesmas) -> float:
    return pkm.population_served * pkm.smoke_exposure_weight


def puskesmas_case_share(pkm: Puskesmas, total_weight: float) -> float:
    """
    Porsi kasus ISPA yang jatuh ke Puskesmas ini. Deret ISPA kabupaten adalah agregat laporan
    Puskesmas yang dipantau, sehingga dibagi proporsional populasi × bobot paparan asap.
    """
    return puskesmas_weight(pkm) / total_weight if total_weight else 0.0


def horizon_p90_cases(forecast: Dict[str, Any], share: float, horizon_days: int) -> float:
    """Jumlah kasus P90 dalam horizon perencanaan (hari) untuk satu Puskesmas."""
    total, remaining = 0.0, horizon_days
    for f in forecast["forecasts"]:
        if remaining <= 0:
            break
        frac = min(1.0, remaining / 7)
        total += f["p90"] * share * frac
        remaining -= 7
    if remaining > 0:  # horizon > 3 minggu: perpanjang dengan P90 minggu terakhir
        total += forecast["forecasts"][-1]["p90"] * share * remaining / 7
    return total
