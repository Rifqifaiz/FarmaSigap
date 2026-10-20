"""Konfigurasi aplikasi (dibaca dari environment / file .env)."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FarmaSigap API"
    app_version: str = "1.1.0"

    # SQLite default; ganti ke PostgreSQL/PostGIS, mis.
    # postgresql+psycopg://user:pass@localhost:5432/farmasigap
    database_url: str = f"sqlite:///{BASE_DIR / 'farmasigap.db'}"

    # Seed data
    seed_on_startup: bool = True          # isi data contoh jika database kosong
    reset_db_on_startup: bool = False     # hapus & buat ulang semua tabel saat startup
    demo_reference_date: Optional[date] = None  # tanggal acuan data demo (default: hari ini)

    # Model ML
    model_dir: Path = BASE_DIR / "app" / "ml" / "artifacts"
    train_model_on_startup: bool = True   # latih model jika belum ada artefak tersimpan
    prefer_lightgbm: bool = True          # pakai LightGBM jika terpasang, selain itu sklearn GBR

    # Parameter bisnis
    active_disaster: str = "karhutla"
    active_district: str = "Kubu Raya"
    yellow_buffer_days: int = 7           # KUNING jika hari stok < lead time + buffer ini
    planning_horizon_days: int = 14       # horizon kebutuhan obat (2 minggu prediksi P90)
    donor_reserve_days: int = 14          # cadangan tambahan yang tetap disimpan Puskesmas donor
    courier_speed_kmh: float = 30.0
    handling_hours: float = 2.0

    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "null",  # halaman dibuka langsung dari file://
    ]
    # Izinkan localhost, domain railway.app, vercel.app, dan deployment cloud
    cors_origin_regex: Optional[str] = r"https?://(localhost|127\.0\.0\.1|.*\.railway\.app|.*\.up\.railway\.app|.*\.vercel\.app)(:\d+)?"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def reference_date(self) -> date:
        return self.demo_reference_date or date.today()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
