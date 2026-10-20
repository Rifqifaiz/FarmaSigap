# PROMPT UNTUK CLAUDE CODE (BACKEND FARMASIGAP)
> **Petunjuk Penggunaan:**
> Buka terminal di folder `backend/`, lalu jalankan `claude` (Claude Code) dan masukkan prompt di bawah ini untuk mengimplementasikan backend FastAPI FarmaSigap secara menyeluruh.

---

```markdown
Anda adalah Senior Backend & Machine Learning Engineer yang bertugas membangun sistem backend untuk platform **FarmaSigap** (Platform Prediktif Berbasis AI & Big Data untuk Antisipasi Kebutuhan dan Distribusi Obat pada Situasi Bencana di Indonesia).

### 1. Konteks & Dokumen Acuan
Proyek ini didasarkan pada Proposal Inovasi FarmaSigap (Fakultas Farmasi UI 2026).
Fokus implementasi tahap 1: Skenario Karhutla (Kebakaran Hutan dan Lahan) dan lonjakan kasus ISPA di Kalimantan Barat (Kabupaten Kubu Raya / Pontianak), dengan 7 Puskesmas:
- PKM A: Sungai Raya (Terdampak langsung asap karhutla, stok kritis)
- PKM B: Rasau Jaya (Fasilitas surplus)
- PKM C: Sungai Kakap
- PKM D: Sungai Ambawang
- PKM E: Kuala Mandor B
- PKM F: Teluk Pakedai
- PKM G: Terentang

### 2. Tech Stack Backend
- Framework: Python 3.10+ dengan FastAPI + Pydantic v2 + Uvicorn
- Database: SQLite dengan SQLAlchemy (atau PostgreSQL/PostGIS siap konfigurasi via `.env`)
- AI/ML Model: Scikit-learn / LightGBM untuk Regresi Kuantil (Quantile Regression: P10, P50, P90)
- CORS Middleware aktif untuk frontend (http://localhost:3000, http://127.0.0.1:5500, http://localhost:5173, atau file://)

### 3. Modul & Formula Bisnis yang Wajib Dibuat
1. **Hazard-to-Drug Engine**:
   - Memetakan jenis bencana (Karhutla, Banjir, Gempa) ke penyakit dominan dan obat prioritas.
   - Skenario Karhutla: ISPA, eksaserbasi asma/PPOK, iritasi mata. Obat prioritas: Salbutamol inhaler/nebulizer, Parasetamol tablet, Air mata buatan (tetes mata), Tabung oksigen, Masker N95.
   - Catatan farmasi: ISPA akibat asap karhutla adalah iritasi/inflamasi dan infeksi virus, umumnya TIDAK memerlukan antibiotik (kecuali pneumonia bakterial sekunder terdiagnosis).
2. **Formula Kebutuhan Obat & Hari Stok Tersisa**:
   - Kebutuhan obat (unit) = Prediksi kasus (P90) × Proporsi kasus yang mendapat obat × Unit per kasus
   - Hari Stok Tersisa = Stok saat ini ÷ Prediksi konsumsi harian
   - Status Indikator:
     * MERAH (Kritis): Hari stok tersisa < Waktu tunggu pengiriman (lead time)
     * KUNING (Waspada): Hari stok tersisa < (Waktu tunggu pengiriman + 7 hari)
     * HIJAU (Aman): Hari stok tersisa >= (Waktu tunggu pengiriman + 7 hari)
3. **Model Prediksi Kasus ISPA (LightGBM / Gradient Boosting Quantile Regression)**:
   - Endpoint: `POST /api/predict/ispa`
   - Input: Kabupaten, minggu epidemiologi, PM2.5 rata-rata/maksimum, jumlah titik panas (hotspots), curah hujan, kunjungan ISPA lag 1-4 minggu.
   - Output: Prediksi 3 minggu ke depan dengan batas bawah (P10), nilai median (P50), dan batas atas untuk safety stock (P90).
   - Sediakan fallback heuristik prediktif jika model belum dilatih (agar API langsung bisa dites).
4. **Mesin Usulan Redistribusi Obat (Surplus-to-Deficit)**:
   - Endpoint: `GET /api/redistribution/suggestions` & `POST /api/redistribution/action`
   - Algoritma mencocokkan Puskesmas yang kritis (misal PKM Sungai Raya defisit Salbutamol) dengan Puskesmas terdekat yang surplus (PKM Rasau Jaya memiliki surplus 350 unit, dialokasikan 60 unit, jarak 12.4 km).
   - Endpoint aksi untuk Apoteker IFK: Setujui (Approve) atau Tolak (Reject) dengan pencatatan audit log (nama apoteker, timestamp, alasan).
5. **Kalkulator Kit Posko Pengungsian (Adaptasi WHO IEHK 2024)**:
   - Endpoint: `POST /api/posko/calculate-kit`
   - Input: Jumlah pengungsi, proporsi balita (%), lansia (%), ibu hamil (%), durasi tinggal (hari).
   - Output: Daftar kebutuhan obat standar posko tanggap darurat (Oralit, Parasetamol sirup/tablet, Zinc, Salbutamol, Kassa, Antiseptik, Tetes mata).
6. **Pencocok Donasi Obat (WHO Medicine Donation Guidelines)**:
   - Endpoint: `POST /api/donation/match`
   - Input: Daftar obat donasi (nama obat, jumlah, tanggal kedaluwarsa / ED, asal donatur).
   - Validasi:
     * Cek kesesuaian dengan formularium bencana aktif.
     * Cek ED: Beri flag MERAH jika ED < 6 bulan, KUNING jika 6-12 bulan, HIJAU jika > 12 bulan.

### 4. Struktur Folder Backend yang Diharapkan
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app & routing
│   ├── config.py            # Settings (.env support)
│   ├── database.py          # SQLAlchemy engine & session
│   ├── models.py            # ORM Models (Puskesmas, Inventory, Alerts, AuditLog)
│   ├── schemas.py           # Pydantic schemas (Request & Response)
│   ├── mock_data.py         # Seed data 7 PKM Kalbar, titik panas, dan stok
│   ├── ml/
│   │   ├── __init__.py
│   │   └── ispa_model.py    # Quantile regression prediction engine
│   └── routers/
│       ├── __init__.py
│       ├── hazard.py        # /api/hazard
│       ├── inventory.py     # /api/inventory (Puskesmas stock & days remaining)
│       ├── prediction.py    # /api/predict
│       ├── redistribution.py# /api/redistribution
│       ├── posko.py         # /api/posko
│       └── donation.py      # /api/donation
├── requirements.txt
├── .env.example
└── README.md
```

Tolong implementasikan file-file tersebut secara lengkap, tanpa placeholder yang rusak, lengkapi dengan seed data bawaan saat startup agar frontend bisa langsung mengonsumsi API, dan pastikan server bisa langsung dijalankan dengan:
`uvicorn app.main:app --reload --port 8000`
```
