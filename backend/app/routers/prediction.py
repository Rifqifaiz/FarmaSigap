from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.ml.ispa_model import forecaster
from app.schemas import ISPAForecastPoint, ISPAPredictRequest, ISPAPredictResponse
from app.services.forecasting import case_history, district_forecast

router = APIRouter(prefix="/api/predict", tags=["AI Predictive Engine"])
legacy_router = APIRouter(prefix="/api/prediction", tags=["AI Predictive Engine"])

_BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _fmt(d: date) -> str:
    return f"{d.day:02d} {_BULAN[d.month - 1]}"


def _interpret(forecasts: List[Dict[str, Any]], lag1: int) -> str:
    peak = max(forecasts, key=lambda f: f["p90"])
    change = (forecasts[0]["p50"] - lag1) / lag1 * 100 if lag1 else 0
    arah = "naik" if change > 3 else "turun" if change < -3 else "stabil"
    return (
        f"Minggu depan kunjungan ISPA diprediksi {arah} ({change:+.0f}% median). "
        f"Batas atas P90 tertinggi {peak['p90']:,} kasus pada minggu +{peak['horizon_week']} — "
        "gunakan P90 sebagai dasar safety stock & Rencana Kebutuhan Obat (RKO) bencana."
    )


@router.post("/ispa", response_model=ISPAPredictResponse)
def predict_ispa(req: ISPAPredictRequest):
    """
    Prediksi kunjungan ISPA 3 minggu ke depan (P10 / P50 / P90) dengan
    Quantile Regression (LightGBM / Gradient Boosting). Bila model belum dilatih,
    otomatis memakai fallback heuristik.
    """
    lags = [req.ispa_lag_1, req.ispa_lag_2, req.ispa_lag_3, req.ispa_lag_4]
    result = forecaster.predict(
        kabupaten=req.kabupaten,
        epi_week=req.epi_week,
        pm25_avg=req.pm25_avg,
        pm25_max=req.pm25_max,
        hotspot_count=req.hotspot_count,
        rainfall_mm=req.rainfall_mm,
        lags=lags,
        population=req.population,
    )
    return {"status": "success", **result, "interpretation": _interpret(result["forecasts"], req.ispa_lag_1)}


def _trend(db: Session, history_weeks: int) -> Dict[str, Any]:
    try:
        fc = district_forecast(db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    history = case_history(db, weeks=history_weeks)
    n = len(history)
    points: List[ISPAForecastPoint] = []
    for i, h in enumerate(history):
        offset = n - 1 - i
        label = f"Minggu Ini ({_fmt(h.week_start)})" if offset == 0 else f"W-{offset} ({_fmt(h.week_start)})"
        anchor = offset == 0  # titik sambung kurva aktual & prediksi
        points.append(
            ISPAForecastPoint(
                week_label=label,
                week_start=h.week_start.isoformat(),
                is_actual=True,
                actual_cases=h.cases,
                p10_cases=h.cases if anchor else None,
                p50_cases=h.cases if anchor else None,
                p90_cases=h.cases if anchor else None,
            )
        )
    for f in fc["forecasts"]:
        ws = date.fromisoformat(f["week_start"])
        points.append(
            ISPAForecastPoint(
                week_label=f"+{f['horizon_week']} Minggu ({_fmt(ws)})",
                week_start=f["week_start"],
                is_actual=False,
                p10_cases=f["p10"],
                p50_cases=f["p50"],
                p90_cases=f["p90"],
            )
        )
    info = forecaster.info()
    return {
        "status": "success",
        "kabupaten": fc["kabupaten"],
        "algorithm": info["method"],
        "model_version": info["model_version"],
        "features_used": [
            "PM2.5 rata-rata & maksimum mingguan",
            "Jumlah titik panas (NASA FIRMS)",
            "Curah hujan mingguan (BMKG)",
            "Minggu epidemiologi (musiman)",
            "Kunjungan ISPA lag 1–4 minggu",
            "Populasi kabupaten",
        ],
        "validation_metrics": info["validation_metrics"],
        "inputs": fc["inputs"],
        "forecasts": fc["forecasts"],
        "smoke_attributable_p50": fc["smoke_attributable_p50"],
        "interpretation": _interpret(fc["forecasts"], fc["based_on_week"]["cases"]),
        "data": [p.model_dump() for p in points],
    }


@router.get("/ispa-trend")
def get_ispa_trend(history_weeks: int = Query(5, ge=4, le=52), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Tren kunjungan ISPA aktual + proyeksi P10/P50/P90 untuk kabupaten aktif (data grafik dasbor)."""
    return _trend(db, history_weeks)


@router.get("/model-info")
def get_model_info() -> Dict[str, Any]:
    """Status model, backend (LightGBM/sklearn/heuristik), fitur, dan metrik validasi holdout."""
    return {"status": "success", "active_district": settings.active_district, **forecaster.info()}


@router.post("/train")
def retrain_model(prefer_lightgbm: bool = True) -> Dict[str, Any]:
    """Latih ulang model quantile regression dan simpan artefaknya."""
    info = forecaster.train(prefer_lightgbm=prefer_lightgbm)
    path = forecaster.save(settings.model_dir)
    return {"status": "success", "artifact": str(path), **info}


@legacy_router.get("/ispa-trend", deprecated=True)
def get_ispa_trend_legacy(history_weeks: int = Query(5, ge=4, le=52), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Alias lama dari `GET /api/predict/ispa-trend`."""
    return _trend(db, history_weeks)
