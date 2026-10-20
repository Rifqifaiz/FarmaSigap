"""
Kalkulator kit obat posko pengungsian (adaptasi WHO Interagency Emergency Health Kit 2024).

IEHK basic module dirancang untuk ±1.000 orang selama ±3 bulan. Kalkulator ini
menurunkan kebutuhan per item dari:

    jumlah = Σ_segmen (jumlah jiwa segmen × insidens episode/jiwa/minggu)
             × durasi (minggu) × unit per episode × pengali jenis bencana × (1 + buffer 10%)

Segmen populasi: balita, dewasa (termasuk anak usia sekolah & ibu hamil), lansia,
dan ibu hamil (khusus suplementasi).
"""

import math
from typing import Any, Dict, List

from fastapi import APIRouter

from app.schemas import PoskoKitRequest, PoskoKitResponse

router = APIRouter(prefix="/api/posko", tags=["Posko Kit Calculator"])

BUFFER = 0.10

# rates: insidens episode per jiwa per minggu per segmen; multiplier per jenis bencana (absen = tidak dimasukkan)
KIT_ITEMS: List[Dict[str, Any]] = [
    {"medicine_name": "Oralit Sachet 200 ml", "form": "Sachet bubuk", "dosage_category": "Rehidrasi Oral", "unit": "Sachet",
     "pack_size": 10, "rates": {"balita": 0.04, "dewasa": 0.008, "lansia": 0.012}, "units_per_episode": 6, "min_qty": 50,
     "multiplier": {"karhutla": 1.0, "banjir": 3.0, "gempa": 1.5}, "target_group": "Semua (prioritas balita)",
     "clinical_note": "Pencegahan & koreksi dehidrasi diare; 1 sachet dalam 200 ml air matang."},
    {"medicine_name": "Parasetamol Sirup 120 mg/5 ml", "form": "Botol 60 ml", "dosage_category": "Pediatrik (Balita)", "unit": "Botol",
     "pack_size": 1, "rates": {"balita": 0.08}, "units_per_episode": 1, "min_qty": 10,
     "multiplier": {"karhutla": 1.5, "banjir": 1.3, "gempa": 1.0}, "target_group": "Balita",
     "clinical_note": "Demam & nyeri balita. Dosis 10–15 mg/kgBB tiap 4–6 jam."},
    {"medicine_name": "Parasetamol Tablet 500 mg", "form": "Strip 10 tablet", "dosage_category": "Dewasa & Geriatri", "unit": "Tablet",
     "pack_size": 10, "rates": {"dewasa": 0.06, "lansia": 0.08}, "units_per_episode": 10, "min_qty": 100,
     "multiplier": {"karhutla": 1.6, "banjir": 1.2, "gempa": 1.8}, "target_group": "Dewasa & lansia",
     "clinical_note": "Analgesik/antipiretik lini pertama. Maksimal 4.000 mg/hari."},
    {"medicine_name": "Zinc Tablet Dispersibel 20 mg", "form": "Strip 10 tablet", "dosage_category": "Pediatrik Diare", "unit": "Tablet",
     "pack_size": 10, "rates": {"balita": 0.04}, "units_per_episode": 10, "min_qty": 30,
     "multiplier": {"karhutla": 1.0, "banjir": 3.0, "gempa": 1.5}, "target_group": "Balita",
     "clinical_note": "Diberikan 10 hari berturut-turut bersama oralit pada diare balita."},
    {"medicine_name": "Salbutamol Inhaler 100 mcg", "form": "Canister 200 dosis", "dosage_category": "Respiratorik & Asma", "unit": "Canister",
     "pack_size": 1, "rates": {"balita": 0.004, "dewasa": 0.003, "lansia": 0.006}, "units_per_episode": 1, "min_qty": 5,
     "multiplier": {"karhutla": 4.0, "banjir": 1.0, "gempa": 1.2}, "target_group": "Penderita asma/PPOK (gunakan spacer untuk anak)",
     "clinical_note": "Pelega bronkospasme akut; kebutuhan melonjak saat paparan asap."},
    {"medicine_name": "Kassa Steril 16×16 cm", "form": "Box isi 10", "dosage_category": "Perawatan Luka", "unit": "Lembar",
     "pack_size": 10, "rates": {"balita": 0.008, "dewasa": 0.01, "lansia": 0.01}, "units_per_episode": 5, "min_qty": 50,
     "multiplier": {"karhutla": 0.5, "banjir": 2.0, "gempa": 8.0}, "target_group": "Semua",
     "clinical_note": "Balut luka; ganti tiap 24 jam atau bila basah/kotor."},
    {"medicine_name": "Povidon Iodin 10% 60 ml (Antiseptik)", "form": "Botol 60 ml", "dosage_category": "Antiseptik", "unit": "Botol",
     "pack_size": 1, "rates": {"balita": 0.008, "dewasa": 0.01, "lansia": 0.01}, "units_per_episode": 0.2, "min_qty": 5,
     "multiplier": {"karhutla": 0.5, "banjir": 2.0, "gempa": 8.0}, "target_group": "Semua",
     "clinical_note": "Dekontaminasi luka setelah dibersihkan dengan air bersih/NaCl."},
    {"medicine_name": "Air Mata Buatan (Tetes Mata 5 ml)", "form": "Botol tetes 5 ml", "dosage_category": "Oftalmologi", "unit": "Botol",
     "pack_size": 1, "rates": {"balita": 0.008, "dewasa": 0.01, "lansia": 0.012}, "units_per_episode": 1, "min_qty": 10,
     "multiplier": {"karhutla": 6.0, "banjir": 1.5, "gempa": 1.5}, "target_group": "Semua",
     "clinical_note": "Iritasi mata akibat asap/debu. Bilas mata dengan air bersih sebelum ditetes."},
    {"medicine_name": "Tablet Tambah Darah (Fe + Asam Folat)", "form": "Strip 10 tablet", "dosage_category": "Kesehatan Ibu", "unit": "Tablet",
     "pack_size": 10, "rates": {"hamil": 7.0}, "units_per_episode": 1, "min_qty": 30,
     "multiplier": {"karhutla": 1.0, "banjir": 1.0, "gempa": 1.0}, "target_group": "Ibu hamil",
     "clinical_note": "1 tablet/hari selama kehamilan; cegah anemia di pengungsian."},
    {"medicine_name": "Masker Respirator N95 / Partikulat", "form": "Box isi 20", "dosage_category": "Alat Pelindung Diri", "unit": "Pcs",
     "pack_size": 20, "rates": {"balita": 3.5, "dewasa": 1.0, "lansia": 3.5, "hamil": 2.5}, "units_per_episode": 1, "min_qty": 50,
     "multiplier": {"karhutla": 1.0}, "target_group": "Prioritas balita (masker anak), lansia, ibu hamil",
     "clinical_note": "Wajib filtrasi PM2.5 bagi kelompok rentan saat ISPU tidak sehat."},
    {"medicine_name": "Krim Mikonazol Nitrat 2%", "form": "Tube 10 g", "dosage_category": "Dermatologi Antijamur", "unit": "Tube",
     "pack_size": 1, "rates": {"balita": 0.01, "dewasa": 0.015, "lansia": 0.015}, "units_per_episode": 1, "min_qty": 10,
     "multiplier": {"banjir": 1.0}, "target_group": "Semua",
     "clinical_note": "Infeksi jamur kulit / kutu air akibat kontak air banjir."},
    {"medicine_name": "Perban Elastis 4 inci", "form": "Roll", "dosage_category": "Perawatan Trauma", "unit": "Roll",
     "pack_size": 1, "rates": {"balita": 0.004, "dewasa": 0.01, "lansia": 0.012}, "units_per_episode": 1, "min_qty": 10,
     "multiplier": {"gempa": 1.0}, "target_group": "Korban luka/fraktur",
     "clinical_note": "Fiksasi & imobilisasi sementara sebelum rujukan."},
]

DISASTER_NOTES = {
    "karhutla": "ISPA akibat asap umumnya iritasi/infeksi virus — antibiotik tidak termasuk kit rutin; resepkan hanya untuk pneumonia bakterial terdiagnosis.",
    "banjir": "Amankan rantai dingin (insulin, vaksin) dengan cold box bila listrik padam; distribusikan oralit + zinc ke semua posko dengan balita.",
    "gempa": "Prioritaskan perawatan luka & cek status imunisasi tetanus korban luka (siapkan ATS/TT di faskes rujukan).",
}


@router.post("/calculate-kit", response_model=PoskoKitResponse)
def calculate_posko_kit(req: PoskoKitRequest):
    """
    Hitung kebutuhan obat standar posko tanggap darurat berdasarkan jumlah pengungsi,
    komposisi kelompok rentan, durasi tinggal, dan jenis bencana.
    """
    total = req.total_refugees
    balita = round(total * req.balita_percentage / 100)
    lansia = round(total * req.elderly_percentage / 100)
    hamil = round(total * req.pregnant_percentage / 100)
    dewasa = max(0, total - balita - lansia)  # ibu hamil termasuk di segmen dewasa
    segments = {"balita": balita, "dewasa": dewasa, "lansia": lansia, "hamil": hamil}
    weeks = req.duration_days / 7

    items = []
    for it in KIT_ITEMS:
        mult = it["multiplier"].get(req.disaster_type)
        if mult is None:
            continue
        episodes = sum(segments[s] * r for s, r in it["rates"].items()) * weeks * mult
        if episodes <= 0:
            continue  # mis. tidak ada ibu hamil / balita
        qty = max(it["min_qty"], math.ceil(episodes * it["units_per_episode"] * (1 + BUFFER)))
        items.append(
            {
                "medicine_name": it["medicine_name"],
                "form": it["form"],
                "dosage_category": it["dosage_category"],
                "target_group": it["target_group"],
                "calculated_quantity": qty,
                "unit": it["unit"],
                "pack_size": it["pack_size"],
                "packs": math.ceil(qty / it["pack_size"]),
                "clinical_note": it["clinical_note"],
            }
        )

    person_days = total * req.duration_days
    return {
        "status": "success",
        "parameters": {
            "total_refugees": total,
            "balita_count": balita,
            "adult_count": dewasa,
            "elderly_count": lansia,
            "pregnant_count": hamil,
            "duration_days": req.duration_days,
            "disaster_type": req.disaster_type,
            "buffer_pct": int(BUFFER * 100),
        },
        "iehk_reference": {
            "standard": "WHO Interagency Emergency Health Kit 2024 (adaptasi)",
            "basic_module_coverage": "±1.000 orang × 3 bulan",
            "equivalent_basic_modules": round(person_days / (1000 * 90), 2),
        },
        "kit_items": items,
        "notes": [
            DISASTER_NOTES[req.disaster_type],
            f"Jumlah sudah termasuk buffer {int(BUFFER * 100)}% dan dibulatkan ke atas; sesuaikan dengan pola penyakit lapangan setelah 72 jam.",
        ],
    }
