# FarmaSigap Backend Service

Backend API untuk platform **FarmaSigap**: Platform Prediktif Berbasis AI & Big Data untuk Antisipasi Kebutuhan dan Distribusi Obat pada Situasi Bencana di Indonesia. Fokus tahap 1: Karhutla & lonjakan ISPA di Kabupaten Kubu Raya, Kalimantan Barat (7 puskesmas, Puskesmas A–G).

Stack: FastAPI · Pydantic v2 · SQLAlchemy 2 (SQLite, siap PostgreSQL/PostGIS) · LightGBM / scikit-learn (Quantile Regression P10/P50/P90).

## Menjalankan

```bash
cd backend
python3 -m venv venv            # Python 3.10+
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Saat startup pertama, server akan:
1. membuat tabel SQLite (`backend/farmasigap.db`),
2. melatih model ISPA (±2 detik) lalu menyimpannya di `app/ml/artifacts/`,
3. mengisi seed data (7 Puskesmas, katalog obat, riwayat ISPA 12 minggu, titik panas, stok), lalu menghitung usulan redistribusi dan alert.

Alamat penting:
- Dasbor web: http://localhost:8000/app/ (frontend disajikan langsung oleh backend)
- Swagger: http://localhost:8000/docs · ReDoc: http://localhost:8000/redoc

Frontend juga bisa dibuka langsung dari `frontend/index.html` atau Live Server (port 5500). CORS sudah mengizinkan `file://` dan semua port localhost. Jika backend mati, frontend otomatis memakai data mock bawaan.

**Reset data demo:** hentikan server, hapus `farmasigap.db`, lalu jalankan ulang (atau set `RESET_DB_ON_STARTUP=true`).

**Test:** `pytest -q` (memakai database sementara, tidak menyentuh `farmasigap.db`).

## Konfigurasi

Salin `.env.example` menjadi `.env`. Variabel utama: `DATABASE_URL`, `SEED_ON_STARTUP`, `RESET_DB_ON_STARTUP`, `DEMO_REFERENCE_DATE`, `TRAIN_MODEL_ON_STARTUP`, `PREFER_LIGHTGBM`, `YELLOW_BUFFER_DAYS`, `PLANNING_HORIZON_DAYS`, `DONOR_RESERVE_DAYS`, `CORS_ORIGINS`.

## Formula bisnis

| Besaran | Rumus |
|---|---|
| Kebutuhan obat (unit) | Prediksi kasus P90 × proporsi kasus yang mendapat obat × unit per kasus |
| Konsumsi harian | Kebutuhan selama horizon (14 hari) ÷ 14 |
| Hari stok tersisa | Stok saat ini ÷ konsumsi harian |
| MERAH | Hari stok < lead time |
| KUNING | Hari stok < lead time + 7 hari |
| HIJAU | Hari stok ≥ lead time + 7 hari |

Prediksi kasus per Puskesmas = prediksi P90 kabupaten × porsi Puskesmas (populasi × bobot paparan asap ÷ total 7 Puskesmas). Proporsi dan unit per kasus tiap obat disimpan di `Medicine.disaster_params` (lihat `app/mock_data.py`).

**Redistribusi:** penerima adalah Puskesmas MERAH/KUNING, dengan kebutuhan sebesar jumlah yang diperlukan agar stok kembali ke ambang HIJAU. Donor adalah Puskesmas HIJAU, dan surplusnya = stok − konsumsi × (lead time + 7 + 14 hari cadangan). Donor dicocokkan mulai dari yang terdekat, memakai jarak jalan bila tersedia (mis. Rasau Jaya → Sungai Raya 12,4 km), selain itu haversine × 1,3. Mutasi yang menambah kurang dari 1 hari stok dilewati. Persetujuan memindahkan stok dan dicatat di audit log. Penolakan wajib menyertakan alasan.

## Endpoint

| Metode | Path | Fungsi |
|---|---|---|
| GET | `/api/hazard/types` | Jenis bencana yang didukung |
| GET | `/api/hazard/mapping/{karhutla\|banjir\|gempa}` | Hazard-to-Drug: penyakit dominan, obat prioritas, catatan farmasi |
| POST | `/api/hazard/drug-mapping` | Sama dengan di atas (body `{disaster_type}`) |
| GET | `/api/hazard/telemetry` | PM2.5/ISPU, titik panas, curah hujan, status siaga |
| GET | `/api/hazard/hotspots` | Klaster titik panas NASA FIRMS |
| GET | `/api/hazard/puskesmas` | 7 Puskesmas + status stok terburuk |
| GET | `/api/inventory/priority-medicines?puskesmas_id=PKM-A` | Kebutuhan, hari stok, status per obat |
| GET | `/api/inventory/summary` · `/api/inventory/all` | Ringkasan per Puskesmas · seluruh inventori |
| PUT | `/api/inventory/{pkm}/{obat}` | Perbarui stok (dicatat di audit log) |
| POST | `/api/inventory/calculate` | Kalkulator formula tanpa database |
| GET | `/api/inventory/alerts` | Alert MERAH/KUNING |
| POST | `/api/predict/ispa` | Prediksi ISPA 3 minggu (P10/P50/P90) |
| GET | `/api/predict/ispa-trend` | Data grafik aktual + prediksi (alias lama: `/api/prediction/ispa-trend`) |
| GET | `/api/predict/model-info` · POST `/api/predict/train` | Status/metrik model · latih ulang |
| GET | `/api/redistribution/suggestions` | Usulan mutasi surplus → defisit |
| POST | `/api/redistribution/generate` | Hitung ulang usulan (+ kebutuhan yang perlu pengadaan Instalasi Farmasi) |
| POST | `/api/redistribution/action` | Approve/reject oleh apoteker Instalasi Farmasi |
| GET | `/api/redistribution/audit-logs` | Riwayat audit |
| POST | `/api/posko/calculate-kit` | Kit obat posko (adaptasi WHO IEHK 2024) |
| POST | `/api/donation/match` | Validasi donasi (formularium + flag ED) |
| GET | `/api/donation/formulary` | Formularium bencana aktif |

## Catatan model

Model dilatih dengan **data simulasi sintetis** surveilans ISPA-karhutla Kalbar 2017–2025, karena data SKDR/SP2TP riil belum tersedia. Metrik validasi (holdout 2025: MAPE P50 ±6–8%, cakupan P10–P90 ±72%) hanya menggambarkan kinerja pada data simulasi, bukan akurasi lapangan. Untuk produksi, ganti `simulate_training_data()` di `app/ml/ispa_model.py` dengan data historis riil. Bila model belum dilatih atau gagal dimuat, API otomatis memakai fallback heuristik.

Seed data adalah data demo yang dibuat realistis, bukan data riil.

## Struktur

```
backend/
├── app/
│   ├── main.py, config.py, database.py, models.py, schemas.py, mock_data.py
│   ├── ml/ispa_model.py          # Quantile regression + fallback heuristik
│   ├── services/                 # hazard_drug, forecasting, stock, redistribution
│   └── routers/                  # hazard, inventory, prediction, redistribution, posko, donation
├── tests/                        # pytest
├── requirements.txt, .env.example
```
