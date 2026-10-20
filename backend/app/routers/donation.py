"""
Pencocok donasi obat berdasarkan WHO Guidelines for Medicine Donations (2010):
donasi harus sesuai kebutuhan yang dinyatakan, tercantum dalam formularium, dan
memiliki sisa masa simpan yang memadai.

Flag ED: MERAH < 6 bulan, KUNING 6–12 bulan, HIJAU > 12 bulan.
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Medicine
from app.schemas import DisasterType, DonationItem, DonationMatchRequest, DonationMatchResponse
from app.services.hazard_drug import ANTIBIOTIC_KARHUTLA_NOTE, build_mapping, disaster_param
from app.services.stock import STATUS_ORDER, compute_metrics

router = APIRouter(prefix="/api/donation", tags=["Donation Matcher"])


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError("tanggal tidak valid")


def months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def expiry_flag(expiry: date, today: date) -> Tuple[str, int, str]:
    months = months_between(today, expiry)
    if expiry <= today:
        return "merah", months, "Sudah kedaluwarsa."
    if expiry < add_months(today, 6):
        return "merah", months, f"Sisa masa simpan {max(months, 0)} bulan (< 6 bulan, tidak memenuhi pedoman WHO)."
    if expiry <= add_months(today, 12):
        return "kuning", months, f"Sisa masa simpan {months} bulan (6–12 bulan) — harus segera didistribusikan (FEFO)."
    return "hijau", months, f"Sisa masa simpan {months} bulan (> 12 bulan) — aman."


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def match_medicine(name: str, medicines: List[Medicine]) -> Optional[Medicine]:
    """Cocokkan nama obat donasi ke formularium lewat alias; alias terpanjang yang cocok menang."""
    n = f" {_norm(name)} "
    best, best_len = None, 0
    for m in medicines:
        for alias in [m.name] + m.aliases.split(","):
            a = _norm(alias)
            if a and f" {a} " in n and len(a) > best_len:
                best, best_len = m, len(a)
    return best


def _allocation_text(medicine_id: str, metrics: List[Dict[str, Any]]) -> Optional[str]:
    rows = [m for m in metrics if m["medicine_id"] == medicine_id]
    if not rows:
        return None
    needy = sorted((m for m in rows if m["status"] != "hijau"), key=lambda m: (STATUS_ORDER[m["status"]], m["days_remaining"]))
    if not needy:
        return "Semua puskesmas berstatus aman — simpan di gudang Instalasi Farmasi sebagai buffer bencana."
    top = needy[:2]
    parts = [f"{m['puskesmas_name']} ({m['status'].upper()}, sisa {m['days_remaining']:.1f} hari, kurang {m['shortfall_units']:,} {m['unit']}/14 hari)" for m in top]
    return "Alokasikan prioritas ke " + "; ".join(parts) + "."


def evaluate(items: List[DonationItem], disaster: str, db: Session) -> Dict[str, Any]:
    today = settings.reference_date
    medicines = db.scalars(select(Medicine)).all()
    metrics = compute_metrics(db, disaster=disaster) if disaster == settings.active_disaster else []
    results = []

    for item in items:
        exp_status, months, exp_reason = expiry_flag(item.expiry_date, today)
        med = match_medicine(item.medicine_name, medicines)
        params = disaster_param(med, disaster) if med else {}

        if med is None:
            relevance, rel_reason = "tidak_relevan", "Tidak tercantum dalam formularium bencana FarmaSigap."
        elif not params:
            relevance, rel_reason = "tidak_relevan", f"Tercantum di formularium ({med.name}) namun tidak dibutuhkan pada skenario {disaster}."
        elif params.get("restricted"):
            note = ANTIBIOTIC_KARHUTLA_NOTE if disaster == "karhutla" else "Penggunaan terbatas sesuai indikasi."
            relevance, rel_reason = "terbatas", f"Obat dengan penggunaan terbatas ({params.get('indication', '')}). {note}"
        elif params.get("priority"):
            relevance, rel_reason = "prioritas_tinggi", f"Obat prioritas {disaster}: {params.get('indication', '')}."
        else:
            relevance, rel_reason = "diterima", f"Obat pendukung skenario {disaster}: {params.get('indication', '')}."

        allocation = None
        if exp_status == "merah":
            decision = "TOLAK"
            recommendation = "TOLAK DONASI: sisa masa simpan < 6 bulan, tidak sesuai WHO Guidelines for Medicine Donations."
        elif relevance == "tidak_relevan":
            decision = "TOLAK"
            recommendation = (
                "TOLAK / KONFIRMASI DULU: donasi harus berdasarkan kebutuhan yang dinyatakan (WHO). "
                "Koordinasikan dengan Instalasi Farmasi sebelum diterima agar tidak membebani gudang."
            )
        elif relevance == "terbatas":
            decision = "TERIMA_BERSYARAT"
            recommendation = "TERIMA BERSYARAT: simpan di gudang Instalasi Farmasi, distribusi hanya dengan resep sesuai indikasi (bukan distribusi massal ke posko)."
        else:
            decision = "TERIMA" if exp_status == "hijau" else "TERIMA_BERSYARAT"
            recommendation = (
                "DITERIMA: masuk alokasi posko/puskesmas sesuai kebutuhan."
                if exp_status == "hijau"
                else "TERIMA BERSYARAT: distribusikan segera dengan prinsip FEFO karena masa simpan 6–12 bulan."
            )
            allocation = _allocation_text(med.id, metrics)

        results.append(
            {
                "medicine_name": item.medicine_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "expiry_date": item.expiry_date.isoformat(),
                "donor_source": item.donor_source,
                "months_to_expiry": months,
                "expiry_status": exp_status,
                "expiry_reason": exp_reason,
                "matched_medicine_id": med.id if med else None,
                "matched_medicine_name": med.name if med else None,
                "relevance_status": relevance,
                "relevance_reason": rel_reason,
                "decision": decision,
                "recommendation": recommendation,
                "allocation_suggestion": allocation,
                "reason": exp_reason,
            }
        )

    summary = {k: sum(1 for r in results if r["decision"] == k) for k in ("TERIMA", "TERIMA_BERSYARAT", "TOLAK")}
    return {
        "status": "success",
        "disaster_type": disaster,
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        "total_evaluated": len(results),
        "summary": summary,
        "results": results,
    }


@router.post("/match", response_model=DonationMatchResponse)
def match_donations(
    payload: Union[DonationMatchRequest, List[DonationItem]] = Body(
        ...,
        examples=[
            {
                "disaster_type": "karhutla",
                "items": [
                    {"medicine_name": "Salbutamol Inhaler 100 mcg", "quantity": 120, "unit": "Canister", "expiry_date": "2027-11-30", "donor_source": "NGO Peduli Sehat"},
                    {"medicine_name": "Amoksisilin Kapsul 500 mg", "quantity": 500, "unit": "Kapsul", "expiry_date": "2028-04-15", "donor_source": "Yayasan ABC"},
                    {"medicine_name": "Parasetamol Tablet 500 mg", "quantity": 300, "unit": "Tablet", "expiry_date": "2026-11-20", "donor_source": "Komunitas Relawan X"},
                ],
            }
        ],
    ),
    db: Session = Depends(get_db),
):
    """
    Validasi daftar obat donasi: kesesuaian dengan formularium bencana aktif,
    flag ED (MERAH < 6 bln, KUNING 6–12 bln, HIJAU > 12 bln), keputusan
    terima/tolak, dan saran alokasi ke puskesmas yang paling membutuhkan.
    Body dapat berupa objek `{disaster_type, items}` atau langsung array item.
    """
    if isinstance(payload, list):
        return evaluate(payload, settings.active_disaster, db)
    return evaluate(payload.items, payload.disaster_type, db)


@router.get("/formulary")
def get_disaster_formulary(disaster_type: Optional[DisasterType] = Query(None), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Formularium bencana yang dipakai sebagai acuan pencocokan donasi."""
    mapping = build_mapping(db, disaster_type or settings.active_disaster)
    return {"status": "success", "disaster_type": mapping["disaster_type"], "data": mapping["medicines"]}
