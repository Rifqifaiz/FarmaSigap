from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog
from app.schemas import RedistributionActionRequest
from app.services.redistribution import (
    apply_action,
    generate_suggestions,
    list_suggestions,
    serialize,
    serialize_audit,
)

router = APIRouter(prefix="/api/redistribution", tags=["Redistribution Engine"])


@router.get("/suggestions")
def get_redistribution_suggestions(
    status: Optional[Literal["pending", "approved", "rejected", "superseded"]] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Usulan mutasi obat antarfasilitas (Surplus -> Defisit). Jika belum ada usulan
    sama sekali, mesin redistribusi dijalankan otomatis.
    """
    if not list_suggestions(db):
        generate_suggestions(db)
    rows = list_suggestions(db, status)
    return {
        "status": "success",
        "total": len(rows),
        "pending": sum(1 for r in rows if r.status == "pending"),
        "data": [serialize(r) for r in rows],
    }


@router.post("/generate")
def regenerate_suggestions(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Hitung ulang usulan berdasarkan stok & prediksi terbaru (usulan pending lama -> superseded)."""
    result = generate_suggestions(db)
    rows = list_suggestions(db, "pending")
    return {"status": "success", "created": result["created"], "unmet_needs": result["unmet_needs"], "data": [serialize(r) for r in rows]}


@router.post("/action")
def execute_redistribution_action(payload: RedistributionActionRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Setujui / tolak usulan mutasi oleh Apoteker Instalasi Farmasi. Persetujuan memindahkan stok
    donor -> penerima. Setiap keputusan dicatat di audit log (nama apoteker,
    timestamp, alasan). Penolakan wajib menyertakan alasan.
    """
    res = apply_action(db, payload.suggestion_id, payload.action, payload.pharmacist_name, payload.effective_reason)
    verb = "disetujui" if payload.action == "approve" else "ditolak"
    return {
        "status": "success",
        "message": f"Mutasi {res['suggestion'].id} {verb} oleh {payload.pharmacist_name}",
        "mutation": serialize(res["suggestion"]),
        "audit_log": serialize_audit(res["audit_log"]),
    }


@router.get("/audit-logs")
def get_audit_logs(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Riwayat audit keputusan apoteker (redistribusi & pembaruan stok)."""
    rows = db.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(limit)).all()
    return {"status": "success", "total": len(rows), "data": [serialize_audit(r) for r in rows]}
