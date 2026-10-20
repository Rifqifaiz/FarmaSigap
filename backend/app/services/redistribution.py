"""
Mesin usulan redistribusi obat (Surplus -> Defisit).

1. Penerima: PKM berstatus MERAH/KUNING, diurutkan dari yang paling kritis.
   Kebutuhan = jumlah agar hari stok kembali ke ambang HIJAU (lead time + 7 hari).
2. Donor: PKM berstatus HIJAU dengan surplus, yaitu stok di atas cadangan yang
   tetap disimpan = konsumsi harian × (lead time donor + 7 + cadangan donor).
3. Pencocokan greedy: setiap penerima dipasangkan dengan donor terdekat (jarak
   jalan bila tersedia, selain itu haversine × faktor jalan) sampai kebutuhan
   terpenuhi atau surplus habis. Mutasi yang menambah < 1 hari stok dilewati. Sisa kebutuhan dilaporkan sebagai usulan
   pengadaan darurat ke IFK.
"""

import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import AuditLog, Inventory, Puskesmas, RedistributionSuggestion, RoadDistance
from app.services.stock import STATUS_ORDER, compute_metrics, sync_alerts

ROAD_FACTOR = 1.3  # rasio jarak jalan terhadap garis lurus (estimasi wilayah Kubu Raya)
MIN_TRANSFER_DAYS = 1.0  # mutasi minimal harus menambah 1 hari stok penerima


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_lookup(db: Session) -> Dict[Tuple[str, str], float]:
    pkms = {p.id: p for p in db.scalars(select(Puskesmas)).all()}
    dist: Dict[Tuple[str, str], float] = {}
    for a in pkms.values():
        for b in pkms.values():
            if a.id != b.id:
                dist[(a.id, b.id)] = round(haversine_km(a.lat, a.lng, b.lat, b.lng) * ROAD_FACTOR, 1)
    for rd in db.scalars(select(RoadDistance)).all():
        dist[(rd.from_puskesmas_id, rd.to_puskesmas_id)] = rd.distance_km
        dist[(rd.to_puskesmas_id, rd.from_puskesmas_id)] = rd.distance_km
    return dist


def delivery_hours(distance_km: float) -> int:
    return math.ceil(distance_km / settings.courier_speed_kmh + settings.handling_hours)


def _next_id(db: Session) -> str:
    year = (settings.reference_date).year
    n = db.scalar(select(func.count()).select_from(RedistributionSuggestion)) or 0
    return f"REDIST-{year}-{n + 1:03d}"


def generate_suggestions(db: Session, disaster: Optional[str] = None) -> Dict[str, Any]:
    """Hitung ulang usulan; usulan 'pending' lama ditandai 'superseded'."""
    metrics = compute_metrics(db, disaster=disaster, include_non_priority=False)
    dist = distance_lookup(db)
    buf, reserve = settings.yellow_buffer_days, settings.donor_reserve_days

    for old in db.scalars(select(RedistributionSuggestion).where(RedistributionSuggestion.status == "pending")).all():
        old.status = "superseded"
    db.flush()

    by_med: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in metrics:
        by_med[m["medicine_id"]].append(m)

    created: List[RedistributionSuggestion] = []
    unmet: List[Dict[str, Any]] = []
    for med_id, rows in by_med.items():
        recipients = sorted(
            (r for r in rows if r["status"] in ("merah", "kuning") and r["daily_consumption_forecast"] > 0),
            key=lambda r: (STATUS_ORDER[r["status"]], r["days_remaining"]),
        )
        surplus: Dict[str, int] = {}
        donor_rows = {}
        for r in rows:
            if r["status"] != "hijau":
                continue
            keep = math.ceil(r["daily_consumption_forecast"] * (r["lead_time_days"] + buf + reserve))
            s = r["current_stock"] - keep
            if s > 0:
                surplus[r["puskesmas_id"]] = s
                donor_rows[r["puskesmas_id"]] = r

        for rec in recipients:
            daily = rec["daily_consumption_forecast"]
            need = math.ceil(daily * rec["safe_threshold_days"] - rec["current_stock"])
            if need <= 0:
                continue
            for donor_id in sorted(surplus, key=lambda d: dist[(d, rec["puskesmas_id"])]):
                if need <= 0:
                    break
                qty = min(need, surplus[donor_id])
                if qty / daily < MIN_TRANSFER_DAYS:
                    continue  # mutasi terlalu kecil, tidak sebanding dengan biaya pengiriman
                don = donor_rows[donor_id]
                km = dist[(donor_id, rec["puskesmas_id"])]
                rec_after = (rec["current_stock"] + qty) / daily
                don_after = (don["current_stock"] - qty) / don["daily_consumption_forecast"]
                rationale = (
                    f"{rec['puskesmas_name']} tersisa {rec['days_remaining']:.1f} hari stok {rec['medicine_name']} "
                    f"({'kritis, di bawah' if rec['status'] == 'merah' else 'waspada, mendekati'} waktu kirim IFK "
                    f"{rec['lead_time_days']} hari). {don['puskesmas_name']} surplus {surplus[donor_id]:,} {rec['unit']} "
                    f"(buffer {don['days_remaining']:.0f} hari). Mutasi {qty:,} {rec['unit']} menaikkan stok penerima "
                    f"menjadi {rec_after:.1f} hari, donor tetap {don_after:.0f} hari (≥ lead time + {buf} + cadangan {reserve} hari)."
                )
                sug = RedistributionSuggestion(
                    id=_next_id(db),
                    from_puskesmas_id=donor_id,
                    to_puskesmas_id=rec["puskesmas_id"],
                    medicine_id=med_id,
                    quantity=qty,
                    distance_km=km,
                    estimated_delivery_hours=delivery_hours(km),
                    priority=rec["status"],
                    rationale=rationale,
                    snapshot={
                        "donor_stock": don["current_stock"],
                        "donor_surplus": surplus[donor_id],
                        "donor_days_before": don["days_remaining"],
                        "donor_days_after": round(don_after, 1),
                        "recipient_stock": rec["current_stock"],
                        "recipient_days_before": rec["days_remaining"],
                        "recipient_days_after": round(rec_after, 1),
                        "recipient_lead_time_days": rec["lead_time_days"],
                        "recipient_need_to_safe": need,
                        "recipient_shortfall_14d": rec["shortfall_units"],
                    },
                )
                db.add(sug)
                db.flush()
                created.append(sug)
                surplus[donor_id] -= qty
                need -= qty
            if need > 0:
                unmet.append(
                    {
                        "puskesmas_id": rec["puskesmas_id"],
                        "puskesmas_name": rec["puskesmas_name"],
                        "medicine_id": med_id,
                        "medicine_name": rec["medicine_name"],
                        "unit": rec["unit"],
                        "status": rec["status"],
                        "remaining_need_units": need,
                        "recommendation": "Tidak ada surplus antarfasilitas yang cukup — ajukan pengadaan/buffer darurat ke IFK.",
                    }
                )
    db.commit()
    return {"created": len(created), "unmet_needs": unmet}


def serialize(s: RedistributionSuggestion) -> Dict[str, Any]:
    return {
        "id": s.id,
        "from_puskesmas_id": s.from_puskesmas_id,
        "from_puskesmas_name": s.from_puskesmas.name,
        "to_puskesmas_id": s.to_puskesmas_id,
        "to_puskesmas_name": s.to_puskesmas.name,
        "medicine_id": s.medicine_id,
        "medicine_name": s.medicine.name,
        "medicine_category": s.medicine.category,
        "unit": s.medicine.unit,
        "quantity": s.quantity,
        "distance_km": s.distance_km,
        "estimated_delivery_hours": s.estimated_delivery_hours,
        "priority": s.priority,
        "rationale": s.rationale,
        "snapshot": s.snapshot,
        "status": s.status,
        "created_at": s.created_at.isoformat(timespec="seconds"),
        "action_by": s.action_by,
        "action_at": s.action_at.isoformat(timespec="seconds") if s.action_at else None,
        "action_reason": s.action_reason,
    }


def list_suggestions(db: Session, status: Optional[str] = None) -> List[RedistributionSuggestion]:
    q = select(RedistributionSuggestion).options(
        selectinload(RedistributionSuggestion.from_puskesmas),
        selectinload(RedistributionSuggestion.to_puskesmas),
        selectinload(RedistributionSuggestion.medicine),
    )
    if status:
        q = q.where(RedistributionSuggestion.status == status)
    rows = db.scalars(q).all()
    return sorted(rows, key=lambda s: (s.status != "pending", STATUS_ORDER.get(s.priority, 9), s.id))


def apply_action(db: Session, suggestion_id: str, action: str, pharmacist: str, reason: Optional[str]) -> Dict[str, Any]:
    sug = db.get(RedistributionSuggestion, suggestion_id)
    if sug is None:
        raise HTTPException(status_code=404, detail="Usulan mutasi tidak ditemukan")
    if sug.status != "pending":
        raise HTTPException(status_code=409, detail=f"Usulan sudah berstatus '{sug.status}', tidak dapat diproses ulang")
    reason = (reason or "").strip()
    if action == "reject" and len(reason) < 5:
        raise HTTPException(status_code=422, detail="Alasan penolakan wajib diisi (minimal 5 karakter) untuk audit trail")

    details: Dict[str, Any] = {"quantity": sug.quantity, "medicine_id": sug.medicine_id, "unit": sug.medicine.unit}
    if action == "approve":
        donor = db.scalar(select(Inventory).where(Inventory.puskesmas_id == sug.from_puskesmas_id, Inventory.medicine_id == sug.medicine_id))
        recipient = db.scalar(select(Inventory).where(Inventory.puskesmas_id == sug.to_puskesmas_id, Inventory.medicine_id == sug.medicine_id))
        if donor is None or donor.current_stock < sug.quantity:
            raise HTTPException(status_code=409, detail="Stok donor sudah tidak mencukupi. Hitung ulang usulan redistribusi.")
        if recipient is None:
            recipient = Inventory(puskesmas_id=sug.to_puskesmas_id, medicine_id=sug.medicine_id, current_stock=0)
            db.add(recipient)
            db.flush()
        details.update(
            {
                "donor_stock_before": donor.current_stock,
                "recipient_stock_before": recipient.current_stock,
            }
        )
        donor.current_stock -= sug.quantity
        recipient.current_stock += sug.quantity
        details.update({"donor_stock_after": donor.current_stock, "recipient_stock_after": recipient.current_stock})

    now = datetime.now()
    sug.status = "approved" if action == "approve" else "rejected"
    sug.action_by, sug.action_at = pharmacist, now
    sug.action_reason = reason or ("Disetujui: mutasi darurat untuk mencegah kekosongan obat" if action == "approve" else None)

    log = AuditLog(
        entity_type="redistribution",
        entity_id=sug.id,
        action=action,
        actor=pharmacist,
        reason=sug.action_reason or "",
        details={**details, "from": sug.from_puskesmas_id, "to": sug.to_puskesmas_id},
        timestamp=now,
    )
    db.add(log)
    db.commit()
    if action == "approve":
        sync_alerts(db)
    db.refresh(sug)
    return {"suggestion": sug, "audit_log": log}


def serialize_audit(log: AuditLog) -> Dict[str, Any]:
    return {
        "id": f"AUDIT-{log.id:04d}",
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "action": log.action,
        "pharmacist": log.actor,
        "reason": log.reason,
        "details": log.details,
        "timestamp": log.timestamp.isoformat(timespec="seconds"),
    }
