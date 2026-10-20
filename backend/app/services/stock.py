"""
Formula kebutuhan obat & hari stok tersisa.

    Kebutuhan obat (unit)  = Prediksi kasus (P90) × Proporsi kasus yang mendapat obat × Unit per kasus
    Konsumsi harian        = Kebutuhan obat selama horizon ÷ jumlah hari horizon
    Hari stok tersisa      = Stok saat ini ÷ Prediksi konsumsi harian

    MERAH  : hari stok < lead time
    KUNING : hari stok < lead time + 7 hari
    HIJAU  : hari stok >= lead time + 7 hari
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import Alert, Inventory, Puskesmas
from app.services.forecasting import district_forecast, horizon_p90_cases, puskesmas_case_share, puskesmas_weight
from app.services.hazard_drug import ANTIBIOTIC_KARHUTLA_NOTE, disaster_param

STATUS_ORDER = {"merah": 0, "kuning": 1, "hijau": 2}
NO_CONSUMPTION_DAYS = 999.0  # ditampilkan bila tidak ada konsumsi terprediksi


def medicine_need_units(predicted_cases_p90: float, proportion_treated: float, units_per_case: float) -> float:
    return predicted_cases_p90 * proportion_treated * units_per_case


def days_of_stock(current_stock: float, daily_consumption: float) -> float:
    if daily_consumption <= 0:
        return NO_CONSUMPTION_DAYS
    return current_stock / daily_consumption


def classify_status(days_remaining: float, lead_time_days: float, buffer_days: Optional[int] = None) -> str:
    buffer_days = settings.yellow_buffer_days if buffer_days is None else buffer_days
    if days_remaining < lead_time_days:
        return "merah"
    if days_remaining < lead_time_days + buffer_days:
        return "kuning"
    return "hijau"


def _note(status: str, days: float, lead: int, restricted: bool, disaster: str) -> str:
    buf = settings.yellow_buffer_days
    if status == "merah":
        text = (
            f"Kritis: stok {days:.1f} hari < waktu kirim {lead} hari. Risiko kekosongan sebelum kiriman Instalasi Farmasi tiba — "
            "ajukan mutasi antarfasilitas / pengadaan darurat."
        )
    elif status == "kuning":
        text = f"Waspada: stok {days:.1f} hari < lead time + {buf} hari ({lead + buf} hari). Pantau harian & siapkan permintaan ke Instalasi Farmasi."
    elif days >= NO_CONSUMPTION_DAYS:
        text = "Aman: tidak ada konsumsi terprediksi untuk skenario bencana aktif."
    else:
        text = f"Aman: stok {days:.1f} hari ≥ lead time + {buf} hari."
    if restricted and disaster == "karhutla":
        text += " Catatan: " + ANTIBIOTIC_KARHUTLA_NOTE
    return text


def compute_metrics(
    db: Session,
    puskesmas_id: Optional[str] = None,
    disaster: Optional[str] = None,
    include_non_priority: bool = True,
) -> List[Dict[str, Any]]:
    """Hitung kebutuhan, konsumsi harian, hari stok & status untuk setiap baris inventori."""
    disaster = disaster or settings.active_disaster
    horizon = settings.planning_horizon_days
    forecast = district_forecast(db)

    q = select(Inventory).options(selectinload(Inventory.medicine), selectinload(Inventory.puskesmas))
    if puskesmas_id:
        q = q.where(Inventory.puskesmas_id == puskesmas_id)
    rows = db.scalars(q).all()
    district_pkms = db.scalars(select(Puskesmas).where(Puskesmas.district == settings.active_district)).all()
    total_weight = sum(puskesmas_weight(p) for p in district_pkms)

    out: List[Dict[str, Any]] = []
    for inv in rows:
        med, pkm = inv.medicine, inv.puskesmas
        p = disaster_param(med, disaster)
        if not p or (not include_non_priority and not p.get("priority")):
            continue
        share = puskesmas_case_share(pkm, total_weight)
        cases_p90 = horizon_p90_cases(forecast, share, horizon)
        need = medicine_need_units(cases_p90, p.get("proportion_treated", 0.0), p.get("units_per_case", 0.0))
        daily = need / horizon if horizon else 0.0
        days = days_of_stock(inv.current_stock, daily)
        status = classify_status(days, pkm.lead_time_days)
        safe_threshold_days = pkm.lead_time_days + settings.yellow_buffer_days
        out.append(
            {
                "id": f"{pkm.id}:{med.id}",
                "puskesmas_id": pkm.id,
                "puskesmas_name": pkm.name,
                "medicine_id": med.id,
                "medicine_name": med.name,
                "category": med.category,
                "form": med.form,
                "unit": med.unit,
                "priority": bool(p.get("priority")),
                "restricted": bool(p.get("restricted")),
                "current_stock": inv.current_stock,
                "predicted_cases_p90": round(cases_p90, 1),
                "proportion_treated": p.get("proportion_treated", 0.0),
                "units_per_case": p.get("units_per_case", 0.0),
                "need_14_days": math.ceil(need),
                "planning_horizon_days": horizon,
                "daily_consumption_forecast": round(daily, 2),
                "days_remaining": round(days, 1),
                "lead_time_days": pkm.lead_time_days,
                "safe_threshold_days": safe_threshold_days,
                "status": status,
                "shortfall_units": max(0, math.ceil(need - inv.current_stock)),
                "reorder_to_safe_units": max(0, math.ceil(daily * safe_threshold_days - inv.current_stock)),
                "note": _note(status, days, pkm.lead_time_days, bool(p.get("restricted")), disaster),
                "updated_at": inv.updated_at.isoformat(timespec="seconds") if inv.updated_at else None,
            }
        )
    out.sort(key=lambda r: (r["puskesmas_id"], not r["priority"], STATUS_ORDER[r["status"]], r["days_remaining"]))
    return out


def puskesmas_summary(db: Session, disaster: Optional[str] = None) -> List[Dict[str, Any]]:
    metrics = compute_metrics(db, disaster=disaster, include_non_priority=False)
    pkms = db.scalars(select(Puskesmas).order_by(Puskesmas.id)).all()
    out = []
    for pkm in pkms:
        items = [m for m in metrics if m["puskesmas_id"] == pkm.id]
        worst = min(items, key=lambda m: (STATUS_ORDER[m["status"]], m["days_remaining"])) if items else None
        counts = {s: sum(1 for m in items if m["status"] == s) for s in STATUS_ORDER}
        out.append(
            {
                "id": pkm.id,
                "code": pkm.code,
                "name": pkm.name,
                "district": pkm.district,
                "lat": pkm.lat,
                "lng": pkm.lng,
                "lead_time_days": pkm.lead_time_days,
                "population_served": pkm.population_served,
                "vulnerability_score": pkm.vulnerability_score,
                "smoke_exposure_weight": pkm.smoke_exposure_weight,
                "description": pkm.description,
                "overall_status": worst["status"] if worst else "hijau",
                "min_days_remaining": worst["days_remaining"] if worst else None,
                "critical_medicine": worst["medicine_name"] if worst and worst["status"] != "hijau" else None,
                "status_counts": counts,
            }
        )
    return out


def sync_alerts(db: Session, disaster: Optional[str] = None) -> Dict[str, int]:
    """Buat alert untuk status MERAH/KUNING baru dan tutup alert yang sudah tidak berlaku."""
    metrics = compute_metrics(db, disaster=disaster, include_non_priority=False)
    current = {(m["puskesmas_id"], m["medicine_id"]): m for m in metrics}
    open_alerts = db.scalars(select(Alert).where(Alert.resolved.is_(False))).all()
    open_by_key = {(a.puskesmas_id, a.medicine_id): a for a in open_alerts}
    created = resolved = 0
    now = datetime.now()

    for key, alert in open_by_key.items():
        m = current.get(key)
        if m is None or m["status"] != alert.level:
            alert.resolved, alert.resolved_at = True, now
            resolved += 1
        else:
            alert.days_remaining = m["days_remaining"]

    for key, m in current.items():
        if m["status"] == "hijau":
            continue
        existing = open_by_key.get(key)
        if existing is not None and not existing.resolved:
            continue
        db.add(
            Alert(
                puskesmas_id=m["puskesmas_id"],
                medicine_id=m["medicine_id"],
                level=m["status"],
                days_remaining=m["days_remaining"],
                message=f"{m['puskesmas_name']} – {m['medicine_name']}: {m['note']}",
            )
        )
        created += 1
    db.commit()
    return {"created": created, "resolved": resolved}
