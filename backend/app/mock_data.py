"""
Seed data FarmaSigap – skenario Karhutla & lonjakan ISPA Kabupaten Kubu Raya, Kalimantan Barat.
Berdasarkan Proposal Inovasi FarmaSigap (Fakultas Farmasi UI 2026).

Catatan: angka adalah data demo yang dibuat realistis, BUKAN data surveilans riil.
"""

import logging
import math
from datetime import datetime, time, timedelta
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FireHotspot, HazardObservation, Inventory, ISPAWeeklyCase, Medicine, Puskesmas, RoadDistance

logger = logging.getLogger("farmasigap.seed")

PUSKESMAS_LIST: List[Dict[str, Any]] = [
    {"id": "PKM-A", "code": "A", "name": "Puskesmas Sungai Raya", "lat": -0.0682, "lng": 109.3871, "lead_time_days": 4,
     "population_served": 48200, "vulnerability_score": 0.88, "smoke_exposure_weight": 1.6,
     "description": "Terdampak langsung asap karhutla lahan gambut Parit Baru; stok obat respirasi kritis."},
    {"id": "PKM-B", "code": "B", "name": "Puskesmas Rasau Jaya", "lat": -0.2141, "lng": 109.3512, "lead_time_days": 3,
     "population_served": 29400, "vulnerability_score": 0.42, "smoke_exposure_weight": 0.8,
     "description": "Fasilitas surplus; buffer obat respirasi aman."},
    {"id": "PKM-C", "code": "C", "name": "Puskesmas Sungai Kakap", "lat": -0.0821, "lng": 109.1824, "lead_time_days": 4,
     "population_served": 36100, "vulnerability_score": 0.55, "smoke_exposure_weight": 1.0,
     "description": "Wilayah pesisir barat, paparan asap sedang."},
    {"id": "PKM-D", "code": "D", "name": "Puskesmas Sungai Ambawang", "lat": -0.0125, "lng": 109.4312, "lead_time_days": 3,
     "population_served": 41800, "vulnerability_score": 0.72, "smoke_exposure_weight": 1.4,
     "description": "Dekat klaster titik panas semak belukar Ambawang."},
    {"id": "PKM-E", "code": "E", "name": "Puskesmas Kuala Mandor B", "lat": 0.0531, "lng": 109.4128, "lead_time_days": 5,
     "population_served": 21500, "vulnerability_score": 0.61, "smoke_exposure_weight": 1.1,
     "description": "Akses jalan terbatas, waktu kirim lebih lama."},
    {"id": "PKM-F", "code": "F", "name": "Puskesmas Teluk Pakedai", "lat": -0.3218, "lng": 109.2814, "lead_time_days": 5,
     "population_served": 19800, "vulnerability_score": 0.35, "smoke_exposure_weight": 0.7,
     "description": "Paparan asap rendah; surplus parasetamol."},
    {"id": "PKM-G", "code": "G", "name": "Puskesmas Terentang", "lat": -0.4120, "lng": 109.5210, "lead_time_days": 6,
     "population_served": 16700, "vulnerability_score": 0.31, "smoke_exposure_weight": 0.6,
     "description": "Wilayah hulu, akses sungai; stok aman."},
]

# Jarak tempuh jalan yang diketahui Instalasi Farmasi (km). Pasangan lain diestimasi haversine × faktor jalan.
ROAD_DISTANCES = [("PKM-A", "PKM-B", 12.4), ("PKM-A", "PKM-D", 9.6), ("PKM-B", "PKM-F", 21.8), ("PKM-D", "PKM-F", 28.6)]


def _kp(priority, proportion, units, indication, restricted=False):
    return {"priority": priority, "proportion_treated": proportion, "units_per_case": units, "indication": indication, "restricted": restricted}


# disaster_params: proporsi kasus (ISPA untuk karhutla) yang mendapat obat & unit per kasus
MEDICINES: List[Dict[str, Any]] = [
    {"id": "MED-SAL-INH", "name": "Salbutamol Inhaler 100 mcg", "category": "Bronkodilator / Asma", "form": "Canister 200 dosis",
     "unit": "Canister", "aliases": "salbutamol,albuterol,salbutamol inhaler,albuterol inhaler,ventolin inhaler,salbutamol mdi",
     "disaster_params": {"karhutla": _kp(True, 0.15, 1, "Eksaserbasi asma/PPOK & bronkospasme akibat asap")},
     "pharmacy_note": "Pelega lini pertama; edukasi teknik inhalasi + spacer untuk anak."},
    {"id": "MED-SAL-NEB", "name": "Salbutamol Nebul 2,5 mg/2,5 ml", "category": "Bronkodilator / Asma", "form": "Ampul nebulizer",
     "unit": "Ampul", "aliases": "salbutamol nebul,salbutamol neb,ventolin nebul,albuterol neb",
     "disaster_params": {"karhutla": _kp(True, 0.05, 6, "Serangan asma sedang-berat di UGD")},
     "pharmacy_note": "Untuk nebulisasi di UGD/puskesmas rawat inap."},
    {"id": "MED-PCT-TAB", "name": "Parasetamol Tablet 500 mg", "category": "Analgesik / Antipiretik", "form": "Strip 10 tablet",
     "unit": "Tablet", "aliases": "parasetamol,paracetamol,parasetamol tablet,paracetamol tablet,acetaminophen,panadol,sanmol tablet,parasetamol 500",
     "disaster_params": {"karhutla": _kp(True, 0.55, 10, "Demam, nyeri kepala, nyeri tenggorokan ISPA"),
                         "banjir": _kp(True, 0.4, 10, "Demam & nyeri"), "gempa": _kp(True, 0.6, 10, "Nyeri pascatrauma")},
     "pharmacy_note": "Dosis dewasa 500–1000 mg tiap 4–6 jam, maksimal 4 g/hari."},
    {"id": "MED-PCT-SYR", "name": "Parasetamol Sirup 120 mg/5 ml", "category": "Analgesik / Antipiretik", "form": "Botol 60 ml",
     "unit": "Botol", "aliases": "parasetamol sirup,paracetamol syrup,parasetamol syr,sanmol sirup,tempra",
     "disaster_params": {"karhutla": _kp(True, 0.18, 1, "Demam ISPA pada balita"), "banjir": _kp(True, 0.15, 1, "Demam balita"),
                         "gempa": _kp(False, 0.1, 1, "Demam balita")},
     "pharmacy_note": "10–15 mg/kgBB tiap 4–6 jam."},
    {"id": "MED-AMB", "name": "Air Mata Buatan (Tetes Mata 5 ml)", "category": "Pelumas Mata / Iritasi", "form": "Botol tetes 5 ml",
     "unit": "Botol", "aliases": "air mata buatan,artificial tears,tetes mata,cendo lyteers,insto,carboxymethylcellulose",
     "disaster_params": {"karhutla": _kp(True, 0.15, 1, "Iritasi mata akibat partikel jelaga")},
     "pharmacy_note": "Bilas mata dengan air bersih sebelum ditetes."},
    {"id": "MED-O2", "name": "Tabung Oksigen Medis 1 m³ (Refill)", "category": "Terapi Oksigen", "form": "Tabung + regulator",
     "unit": "Tabung", "aliases": "oksigen,oxygen,tabung oksigen,o2",
     "disaster_params": {"karhutla": _kp(True, 0.008, 1, "Sesak napas berat / hipoksemia"), "gempa": _kp(False, 0.005, 1, "Trauma berat")},
     "pharmacy_note": "Siagakan di UGD 24 jam; pastikan regulator & humidifier tersedia."},
    {"id": "MED-N95", "name": "Masker Respirator N95 / Partikulat", "category": "Alat Pelindung Diri", "form": "Box isi 20",
     "unit": "Pcs", "aliases": "masker n95,n95,respirator,masker partikulat,kn95",
     "disaster_params": {"karhutla": _kp(True, 1.0, 2, "Proteksi PM2.5 pasien & kelompok rentan")},
     "pharmacy_note": "Prioritas balita (masker anak), lansia, ibu hamil & penderita asma."},
    {"id": "MED-ORS", "name": "Oralit Sachet 200 ml", "category": "Rehidrasi Cairan", "form": "Sachet bubuk",
     "unit": "Sachet", "aliases": "oralit,ors,oral rehydration,garam rehidrasi",
     "disaster_params": {"karhutla": _kp(False, 0.03, 3, "Dehidrasi di posko"), "banjir": _kp(True, 0.35, 6, "Diare akut"),
                         "gempa": _kp(False, 0.1, 6, "Diare di pengungsian")},
     "pharmacy_note": "Larutkan 1 sachet dalam 200 ml air matang; buang setelah 24 jam."},
    {"id": "MED-ZINC", "name": "Zinc Tablet Dispersibel 20 mg", "category": "Suplemen Diare Anak", "form": "Strip 10 tablet",
     "unit": "Tablet", "aliases": "zinc,zink,zinc sulfate,zinc dispersible",
     "disaster_params": {"banjir": _kp(True, 0.2, 10, "Diare balita (10 hari)"), "gempa": _kp(False, 0.05, 10, "Diare balita")},
     "pharmacy_note": "10 hari berturut-turut walau diare sudah berhenti."},
    {"id": "MED-AMX", "name": "Amoksisilin Kapsul 500 mg", "category": "Antibiotik", "form": "Strip 10 kapsul", "unit": "Kapsul",
     "is_antibiotic": True, "aliases": "amoksisilin,amoxicillin,amoxilin,amoxsan",
     "disaster_params": {"karhutla": _kp(False, 0.03, 15, "HANYA pneumonia bakterial sekunder terdiagnosis", restricted=True),
                         "banjir": _kp(False, 0.05, 15, "Infeksi bakteri terdiagnosis", restricted=True),
                         "gempa": _kp(False, 0.08, 15, "Profilaksis/terapi luka terinfeksi", restricted=True)},
     "pharmacy_note": "Antibiotik bukan terapi rutin ISPA akibat asap; resepkan hanya bila ada indikasi bakteri."},
    {"id": "MED-DOXY", "name": "Doksisiklin Kapsul 100 mg", "category": "Antibiotik", "form": "Strip 10 kapsul", "unit": "Kapsul",
     "is_antibiotic": True, "aliases": "doksisiklin,doxycycline,doxycyclin",
     "disaster_params": {"banjir": _kp(False, 0.05, 10, "Profilaksis leptospirosis kelompok paparan tinggi", restricted=True)},
     "pharmacy_note": "Kontraindikasi ibu hamil & anak < 8 tahun."},
    {"id": "MED-MIC", "name": "Krim Mikonazol Nitrat 2%", "category": "Antijamur Topikal", "form": "Tube 10 g", "unit": "Tube",
     "aliases": "mikonazol,miconazole,daktarin,krim antijamur",
     "disaster_params": {"banjir": _kp(True, 0.15, 1, "Infeksi jamur kulit / kutu air")},
     "pharmacy_note": "Oles 2×/hari, jaga kulit tetap kering."},
    {"id": "MED-POV", "name": "Povidon Iodin 10% 60 ml", "category": "Antiseptik", "form": "Botol 60 ml", "unit": "Botol",
     "aliases": "povidon iodin,povidone iodine,betadine,antiseptik",
     "disaster_params": {"gempa": _kp(True, 0.3, 1, "Antiseptik luka"), "banjir": _kp(False, 0.05, 1, "Luka terkontaminasi")},
     "pharmacy_note": "Bersihkan luka dengan NaCl/air bersih sebelum antiseptik."},
    {"id": "MED-KASSA", "name": "Kassa Steril 16×16 cm", "category": "Perawatan Luka", "form": "Box isi 10", "unit": "Lembar",
     "aliases": "kassa,kasa,gauze,kassa steril",
     "disaster_params": {"gempa": _kp(True, 0.4, 10, "Balut luka trauma"), "banjir": _kp(False, 0.05, 5, "Luka ringan")},
     "pharmacy_note": "Ganti balutan tiap 24 jam atau bila basah."},
    {"id": "MED-ELAST", "name": "Perban Elastis 4 inci", "category": "Perawatan Luka", "form": "Roll", "unit": "Roll",
     "aliases": "perban elastis,elastic bandage,verban,bandage",
     "disaster_params": {"gempa": _kp(True, 0.2, 1, "Imobilisasi & fiksasi")},
     "pharmacy_note": "Jangan terlalu kencang; cek sirkulasi distal."},
]

# Target hari stok awal per Puskesmas (skenario minggu ini). Stok = target hari × konsumsi harian
# terprediksi saat seed, sehingga status Merah/Kuning/Hijau mengikuti narasi proposal.
TARGET_DAYS = {
    "PKM-A": {"MED-SAL-INH": 3.1, "MED-SAL-NEB": 5.5, "MED-PCT-TAB": 3.6, "MED-PCT-SYR": 9.0, "MED-AMB": 9.5, "MED-O2": 8.4, "MED-N95": 24.9, "MED-ORS": 30.3, "MED-AMX": 40},
    "PKM-B": {"MED-SAL-INH": None, "MED-SAL-NEB": 35, "MED-PCT-TAB": 30, "MED-PCT-SYR": 28, "MED-AMB": 30, "MED-O2": 25, "MED-N95": 40, "MED-ORS": 45, "MED-AMX": 60},
    "PKM-C": {"MED-SAL-INH": 8.0, "MED-SAL-NEB": 12, "MED-PCT-TAB": 10.2, "MED-PCT-SYR": 14, "MED-AMB": 13, "MED-O2": 9, "MED-N95": 20, "MED-ORS": 30, "MED-AMX": 45},
    "PKM-D": {"MED-SAL-INH": 6.5, "MED-SAL-NEB": 2.8, "MED-PCT-TAB": 2.4, "MED-PCT-SYR": 7, "MED-AMB": 12, "MED-O2": 11, "MED-N95": 18, "MED-ORS": 28, "MED-AMX": 35},
    "PKM-E": {"MED-SAL-INH": 8.5, "MED-SAL-NEB": 10.5, "MED-PCT-TAB": 13, "MED-PCT-SYR": 15, "MED-AMB": 9, "MED-O2": 14, "MED-N95": 22, "MED-ORS": 30, "MED-AMX": 40},
    "PKM-F": {"MED-SAL-INH": 32, "MED-SAL-NEB": 30, "MED-PCT-TAB": 60, "MED-PCT-SYR": 35, "MED-AMB": 28, "MED-O2": 22, "MED-N95": 36, "MED-ORS": 40, "MED-AMX": 55},
    "PKM-G": {"MED-SAL-INH": 28.4, "MED-SAL-NEB": 25, "MED-PCT-TAB": 26, "MED-PCT-SYR": 27, "MED-AMB": 24, "MED-O2": 20, "MED-N95": 30, "MED-ORS": 35, "MED-AMX": 50},
}
SALBUTAMOL_SURPLUS_PKM_B = 350  # Puskesmas Rasau Jaya: surplus 350 canister di atas cadangan aman
# Stok absolut untuk obat yang tidak dikonsumsi pada skenario karhutla
STATIC_STOCK = {"MED-ZINC": 400, "MED-DOXY": 200, "MED-MIC": 60, "MED-POV": 40, "MED-KASSA": 500, "MED-ELAST": 30}

# Riwayat 12 minggu Kabupaten Kubu Raya (minggu terakhir = minggu berjalan)
ISPA_HISTORY = [
    # cases, pm25_avg, pm25_max, hotspots, rainfall_mm
    (352, 22.0, 35.0, 1, 64.0),
    (340, 25.0, 41.0, 2, 58.0),
    (361, 31.0, 52.0, 3, 49.0),
    (348, 38.0, 63.0, 5, 41.0),
    (372, 44.0, 72.0, 7, 36.0),
    (389, 58.0, 95.0, 10, 30.0),
    (405, 72.0, 118.0, 14, 24.0),
    (420, 86.0, 141.0, 18, 19.0),
    (510, 112.0, 188.0, 26, 14.0),
    (680, 148.0, 246.0, 38, 9.0),
    (740, 162.0, 271.0, 42, 8.0),
    (810, 184.5, 312.0, 48, 6.0),
]

FIRE_HOTSPOTS = [
    {"name": "Titik Panas Lahan Gambut Parit Baru", "lat": -0.092, "lng": 109.412, "confidence_pct": 92, "land_type": "Lahan Gambut"},
    {"name": "Titik Panas Semak Belukar Ambawang", "lat": -0.051, "lng": 109.438, "confidence_pct": 88, "land_type": "Semak Belukar"},
    {"name": "Titik Panas Lahan Terbuka Rasau Jaya", "lat": -0.185, "lng": 109.382, "confidence_pct": 74, "land_type": "Lahan Terbuka"},
    {"name": "Titik Panas Gambut Kuala Dua", "lat": -0.128, "lng": 109.401, "confidence_pct": 81, "land_type": "Lahan Gambut"},
    {"name": "Titik Panas Perkebunan Sungai Kakap", "lat": -0.064, "lng": 109.226, "confidence_pct": 69, "land_type": "Perkebunan"},
]


def _alert_level(pm25: float, hotspots: int) -> str:
    if pm25 > 150 or hotspots >= 40:
        return "SIAGA DARURAT KARHUTLA"
    if pm25 > 55 or hotspots >= 15:
        return "WASPADA KARHUTLA"
    return "NORMAL"


def seed_database(db: Session) -> bool:
    """Isi database dengan data demo jika masih kosong. Mengembalikan True bila seed dilakukan."""
    if db.scalar(select(func.count()).select_from(Puskesmas)):
        return False

    from app.services.forecasting import ispu_category

    ref = settings.reference_date
    this_monday = ref - timedelta(days=ref.weekday())

    for p in PUSKESMAS_LIST:
        db.add(Puskesmas(district=settings.active_district, **p))
    for m in MEDICINES:
        db.add(Medicine(**m))
    db.flush()
    for a, b, km in ROAD_DISTANCES:
        db.add(RoadDistance(from_puskesmas_id=a, to_puskesmas_id=b, distance_km=km))

    n = len(ISPA_HISTORY)
    for i, (cases, pm_avg, pm_max, hot, rain) in enumerate(ISPA_HISTORY):
        week_start = this_monday - timedelta(weeks=n - 1 - i)
        db.add(
            ISPAWeeklyCase(
                district=settings.active_district,
                week_start=week_start,
                epi_week=week_start.isocalendar()[1],
                cases=cases,
                pm25_avg=pm_avg,
                pm25_max=pm_max,
                hotspot_count=hot,
                rainfall_mm=rain,
            )
        )
        is_current = i == n - 1
        observed = datetime.combine(ref, time(12, 45)) if is_current else datetime.combine(week_start + timedelta(days=6), time(12, 0))
        db.add(
            HazardObservation(
                district=settings.active_district,
                observed_at=observed,
                alert_level=_alert_level(pm_avg, hot),
                pm25_avg=pm_avg,
                pm25_max=pm_max,
                ispu_category=ispu_category(pm_avg),
                hotspot_count=hot,
                rainfall_mm=rain,
                wind_direction="Tenggara ke Barat Laut",
                wind_speed_kmh=14.2 if is_current else 10.0 + i * 0.3,
            )
        )
    for h in FIRE_HOTSPOTS:
        db.add(FireHotspot(detected_at=datetime.combine(ref, time(2, 30)), **h))
    db.flush()

    # Stok awal dihitung dari konsumsi harian terprediksi (butuh model & riwayat di atas)
    from app.services.stock import compute_metrics

    for pkm_id in TARGET_DAYS:
        for med_id in list(TARGET_DAYS[pkm_id]) + list(STATIC_STOCK):
            db.add(Inventory(puskesmas_id=pkm_id, medicine_id=med_id, current_stock=STATIC_STOCK.get(med_id, 0)))
    db.flush()

    pkm_lead = {p["id"]: p["lead_time_days"] for p in PUSKESMAS_LIST}
    for m in compute_metrics(db):
        target = TARGET_DAYS.get(m["puskesmas_id"], {}).get(m["medicine_id"], "absent")
        if target == "absent":
            continue
        daily = m["daily_consumption_forecast"]
        inv = db.scalar(select(Inventory).where(Inventory.puskesmas_id == m["puskesmas_id"], Inventory.medicine_id == m["medicine_id"]))
        if target is None:  # surplus eksplisit Puskesmas B
            reserve_days = pkm_lead[m["puskesmas_id"]] + settings.yellow_buffer_days + settings.donor_reserve_days
            inv.current_stock = math.ceil(daily * reserve_days) + SALBUTAMOL_SURPLUS_PKM_B
        else:
            inv.current_stock = max(1, round(daily * target))
    db.commit()
    logger.info("Seed data FarmaSigap selesai (%d Puskesmas, %d obat)", len(PUSKESMAS_LIST), len(MEDICINES))
    return True
