from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import Alert, AuditLog, Inventory, Puskesmas
from app.schemas import (
    DisasterType,
    InventoryResponse,
    StockCalcRequest,
    StockCalcResponse,
    StockUpdateRequest,
)
from app.services.stock import (
    STATUS_ORDER,
    classify_status,
    compute_metrics,
    days_of_stock,
    medicine_need_units,
    puskesmas_summary,
    sync_alerts,
)

router = APIRouter(prefix="/api/inventory", tags=["Disaster Medicine Inventory"])

FORMULA = {
    "kebutuhan_obat": "Prediksi kasus (P90) × Proporsi kasus yang mendapat obat × Unit per kasus",
    "konsumsi_harian": "Kebutuhan obat selama horizon ÷ jumlah hari horizon",
    "hari_stok_tersisa": "Stok saat ini ÷ Prediksi konsumsi harian",
    "merah": "Hari stok < lead time",
    "kuning": f"Hari stok < lead time + {settings.yellow_buffer_days} hari",
    "hijau": f"Hari stok ≥ lead time + {settings.yellow_buffer_days} hari",
}


@router.get("/priority-medicines", response_model=InventoryResponse)
def get_priority_medicines(
    puskesmas_id: str = Query("PKM-A", description="ID Puskesmas, mis. PKM-A"),
    disaster_type: Optional[DisasterType] = Query(None, description="Default: bencana aktif"),
    include_non_priority: bool = Query(True, description="Sertakan obat pendukung/terbatas (mis. oralit, antibiotik)"),
    db: Session = Depends(get_db),
):
    """
    Obat prioritas bencana untuk satu puskesmas, lengkap dengan kebutuhan (P90),
    konsumsi harian, hari stok tersisa, dan status Merah/Kuning/Hijau.
    """
    pkm = db.get(Puskesmas, puskesmas_id)
    if pkm is None:
        raise HTTPException(status_code=404, detail="Puskesmas tidak ditemukan")
    disaster = disaster_type or settings.active_disaster
    return {
        "status": "success",
        "puskesmas_id": pkm.id,
        "puskesmas": pkm.name,
        "lead_time_days": pkm.lead_time_days,
        "disaster_type": disaster,
        "formula": FORMULA,
        "data": compute_metrics(db, pkm.id, disaster, include_non_priority),
    }


@router.get("/summary")
def get_inventory_summary(disaster_type: Optional[DisasterType] = None, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Ringkasan status stok per puskesmas (status terburuk & jumlah item per status)."""
    data = puskesmas_summary(db, disaster_type)
    totals = {s: sum(1 for p in data if p["overall_status"] == s) for s in ("merah", "kuning", "hijau")}
    return {"status": "success", "puskesmas_by_status": totals, "data": data}


@router.get("/all")
def get_all_inventory(disaster_type: Optional[DisasterType] = None, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Seluruh baris inventori semua puskesmas beserta metrik stok."""
    data = compute_metrics(db, None, disaster_type)
    return {"status": "success", "total": len(data), "data": data}


@router.put("/{puskesmas_id}/{medicine_id}")
def update_stock(puskesmas_id: str, medicine_id: str, req: StockUpdateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Perbarui stok (stock opname / penerimaan) dengan pencatatan audit log."""
    inv = db.scalar(select(Inventory).where(Inventory.puskesmas_id == puskesmas_id, Inventory.medicine_id == medicine_id))
    if inv is None:
        raise HTTPException(status_code=404, detail="Item inventori tidak ditemukan")
    before = inv.current_stock
    inv.current_stock = req.current_stock
    db.add(
        AuditLog(
            entity_type="inventory",
            entity_id=f"{puskesmas_id}:{medicine_id}",
            action="update_stock",
            actor=req.updated_by,
            reason=req.reason or "Pembaruan stok",
            details={"stock_before": before, "stock_after": req.current_stock},
        )
    )
    db.commit()
    alerts = sync_alerts(db)
    item = next((m for m in compute_metrics(db, puskesmas_id) if m["medicine_id"] == medicine_id), None)
    return {"status": "success", "data": item, "alerts": alerts}


@router.post("/calculate", response_model=StockCalcResponse)
def calculate_stock(req: StockCalcRequest):
    """Kalkulator formula kebutuhan obat & status stok tanpa database (untuk uji/simulasi)."""
    need = medicine_need_units(req.predicted_cases_p90, req.proportion_treated, req.units_per_case)
    daily = need / req.horizon_days
    days = days_of_stock(req.current_stock, daily)
    return {
        "need_units": round(need, 1),
        "daily_consumption_forecast": round(daily, 2),
        "days_remaining": round(days, 1),
        "status": classify_status(days, req.lead_time_days),
        "thresholds": {"merah_below_days": req.lead_time_days, "kuning_below_days": req.lead_time_days + settings.yellow_buffer_days},
    }


@router.get("/alerts")
def get_alerts(include_resolved: bool = False, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Alert stok MERAH/KUNING (disinkronkan dengan metrik terbaru)."""
    sync_alerts(db)
    q = select(Alert).options(selectinload(Alert.puskesmas), selectinload(Alert.medicine))
    if not include_resolved:
        q = q.where(Alert.resolved.is_(False))
    rows = sorted(db.scalars(q).all(), key=lambda a: (a.resolved, STATUS_ORDER.get(a.level, 9), a.days_remaining))
    return {
        "status": "success",
        "total": len(rows),
        "data": [
            {
                "id": a.id,
                "puskesmas_id": a.puskesmas_id,
                "puskesmas_name": a.puskesmas.name,
                "medicine_id": a.medicine_id,
                "medicine_name": a.medicine.name,
                "level": a.level,
                "days_remaining": a.days_remaining,
                "message": a.message,
                "created_at": a.created_at.isoformat(timespec="seconds"),
                "resolved": a.resolved,
                "resolved_at": a.resolved_at.isoformat(timespec="seconds") if a.resolved_at else None,
            }
            for a in rows
        ],
    }
