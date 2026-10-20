"""
Hazard-to-Drug Engine: memetakan jenis bencana -> penyakit dominan -> obat prioritas.

Parameter kuantifikasi per obat (proporsi kasus yang mendapat obat & unit per kasus)
disimpan pada kolom `Medicine.disaster_params` agar dapat diubah apoteker tanpa
mengubah kode.
"""

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Medicine

ANTIBIOTIC_KARHUTLA_NOTE = (
    "ISPA akibat asap karhutla umumnya berupa iritasi/inflamasi saluran napas dan infeksi virus, "
    "sehingga TIDAK memerlukan antibiotik. Antibiotik hanya diberikan bila terdiagnosis "
    "pneumonia bakterial sekunder."
)

DISASTER_PROFILES: Dict[str, Dict[str, Any]] = {
    "karhutla": {
        "label": "Kebakaran Hutan dan Lahan (Karhutla) & Kabut Asap",
        "hazard_indicators": [
            "PM2.5 / ISPU (KLHK)",
            "Titik panas NASA FIRMS (VIIRS/MODIS)",
            "Curah hujan & hari tanpa hujan (BMKG)",
            "Arah & kecepatan angin",
        ],
        "dominant_diseases": [
            {"name": "ISPA (Infeksi Saluran Pernapasan Akut)", "icd10": "J00–J06", "note": "Lonjakan 1–3 minggu setelah PM2.5 naik"},
            {"name": "Eksaserbasi asma / PPOK", "icd10": "J45, J44.1", "note": "Paling rentan: anak, lansia, penderita asma"},
            {"name": "Iritasi mata / konjungtivitis iritan", "icd10": "H10.1–H10.3", "note": "Paparan partikel jelaga"},
            {"name": "Pneumonia bakterial sekunder", "icd10": "J13–J18", "note": "Minoritas kasus; satu-satunya indikasi antibiotik"},
        ],
        "vulnerable_groups": ["Balita", "Lansia", "Ibu hamil", "Penderita asma/PPOK & penyakit jantung"],
        "pharmacy_notes": [
            ANTIBIOTIC_KARHUTLA_NOTE,
            "Salbutamol inhaler/nebulizer adalah pelega lini pertama bronkospasme akibat asap.",
            "Masker N95 diprioritaskan untuk kelompok rentan yang beraktivitas di luar ruang saat ISPU tidak sehat.",
            "Siagakan tabung oksigen di UGD untuk kasus sesak berat.",
        ],
    },
    "banjir": {
        "label": "Banjir & Genangan",
        "hazard_indicators": ["Tinggi muka air", "Curah hujan ekstrem (BMKG)", "Luas genangan", "Jumlah pengungsi"],
        "dominant_diseases": [
            {"name": "Diare akut", "icd10": "A09", "note": "Air bersih & sanitasi terganggu"},
            {"name": "Leptospirosis", "icd10": "A27", "note": "Paparan air tercemar urin tikus"},
            {"name": "Penyakit kulit (dermatitis, infeksi jamur)", "icd10": "L30, B35–B36", "note": "Kontak air banjir berkepanjangan"},
            {"name": "ISPA", "icd10": "J00–J06", "note": "Kepadatan pengungsian"},
        ],
        "vulnerable_groups": ["Balita", "Lansia", "Ibu hamil", "Pasien penyakit kronis"],
        "pharmacy_notes": [
            "Oralit + Zinc 10 hari adalah tata laksana diare balita.",
            "Doksisiklin profilaksis leptospirosis hanya untuk kelompok paparan tinggi sesuai arahan dinkes.",
            "Saat pemadaman listrik, segera pindahkan insulin & vaksin ke cold box dengan ice pack.",
        ],
    },
    "gempa": {
        "label": "Gempa Bumi",
        "hazard_indicators": ["Magnitudo & intensitas (BMKG)", "Kerusakan faskes", "Jumlah korban luka", "Jumlah pengungsi"],
        "dominant_diseases": [
            {"name": "Luka & trauma jaringan lunak", "icd10": "T14", "note": "Fase akut 0–7 hari"},
            {"name": "Fraktur", "icd10": "T14.2", "note": "Butuh imobilisasi & rujukan"},
            {"name": "Tetanus (risiko)", "icd10": "A35", "note": "Luka kotor/terkontaminasi"},
            {"name": "ISPA & diare di pengungsian", "icd10": "J00–J06, A09", "note": "Fase pascabencana"},
        ],
        "vulnerable_groups": ["Korban luka", "Lansia", "Balita", "Penyandang disabilitas"],
        "pharmacy_notes": [
            "Perawatan luka: kassa steril, antiseptik, perban elastis menjadi kebutuhan terbesar fase akut.",
            "Pastikan ketersediaan ATS/Tetanus toksoid sesuai status imunisasi korban luka.",
            "Jaga kesinambungan terapi pasien kronis (TB, ARV, insulin, antihipertensi).",
        ],
    },
}

SUPPORTED_DISASTERS = list(DISASTER_PROFILES)


def disaster_param(medicine: Medicine, disaster: str) -> Dict[str, Any]:
    return (medicine.disaster_params or {}).get(disaster, {})


def medicines_for_disaster(db: Session, disaster: str, priority_only: bool = False) -> List[Medicine]:
    meds = db.scalars(select(Medicine).order_by(Medicine.id)).all()
    out = []
    for m in meds:
        p = disaster_param(m, disaster)
        if not p:
            continue
        if priority_only and not p.get("priority"):
            continue
        out.append(m)
    return out


def build_mapping(db: Session, disaster: str) -> Dict[str, Any]:
    profile = DISASTER_PROFILES[disaster]
    meds = medicines_for_disaster(db, disaster)
    medicine_rows = []
    for m in meds:
        p = disaster_param(m, disaster)
        medicine_rows.append(
            {
                "medicine_id": m.id,
                "name": m.name,
                "category": m.category,
                "form": m.form,
                "unit": m.unit,
                "priority": bool(p.get("priority")),
                "restricted": bool(p.get("restricted")),
                "indication": p.get("indication", ""),
                "proportion_treated": p.get("proportion_treated", 0.0),
                "units_per_case": p.get("units_per_case", 0.0),
                "is_antibiotic": m.is_antibiotic,
                "pharmacy_note": m.pharmacy_note,
            }
        )
    medicine_rows.sort(key=lambda r: (not r["priority"], r["restricted"], r["name"]))
    return {
        "disaster_type": disaster,
        **profile,
        "medicines": medicine_rows,
    }
