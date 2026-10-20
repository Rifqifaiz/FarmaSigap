"""
Mesin prediksi kunjungan ISPA mingguan berbasis Quantile Regression.

- Model: LightGBM (objective="quantile") bila terpasang, selain itu
  sklearn GradientBoostingRegressor(loss="quantile").
- Strategi multi-step "direct": satu model per horizon (+1, +2, +3 minggu)
  per kuantil (P10, P50, P90) -> 9 model.
- Target dimodelkan sebagai rasio terhadap kunjungan minggu terakhir (lag 1),
  sehingga model dapat dipakai lintas kabupaten dengan skala populasi berbeda.
- Data latih: simulasi sintetis surveilans ISPA-karhutla Kalimantan Barat
  (musim kemarau, titik panas, PM2.5, curah hujan) selama belum tersedia data
  riil SP2TP/SKDR. Ganti `simulate_training_data` dengan data historis riil
  untuk produksi.
- Jika model belum dilatih / gagal dimuat, dipakai fallback heuristik agar API
  tetap bisa diuji.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("farmasigap.ml")

QUANTILES = (0.1, 0.5, 0.9)
HORIZONS = (1, 2, 3)
MODEL_FILENAME = "ispa_quantile.joblib"
MODEL_VERSION = "ispa-qr-1.0"

# Populasi kabupaten/kota (pembulatan, dipakai sebagai fitur skala)
DISTRICT_POPULATION: Dict[str, int] = {
    "Kubu Raya": 610_000,
    "Kota Pontianak": 680_000,
    "Mempawah": 270_000,
    "Ketapang": 590_000,
    "Sanggau": 480_000,
}
# Proporsi lahan gambut rawan terbakar (relatif) untuk simulasi
_PEAT_FACTOR = {"Kubu Raya": 1.0, "Kota Pontianak": 0.35, "Mempawah": 0.8, "Ketapang": 1.1, "Sanggau": 0.6}
# Keparahan musim karhutla per tahun (2019 & 2023 tahun El Niño)
_FIRE_SEVERITY = {2017: 0.35, 2018: 0.7, 2019: 1.25, 2020: 0.3, 2021: 0.35, 2022: 0.4, 2023: 1.1, 2024: 0.55, 2025: 0.7}

FEATURES = [
    "log_pop",
    "target_week_sin",
    "target_week_cos",
    "pm25_avg",
    "pm25_max",
    "hotspots",
    "rainfall_mm",
    "lag1_per_100k",
    "lag2_ratio",
    "lag3_ratio",
    "lag4_ratio",
]


def normalize_district(name: str) -> str:
    n = name.strip().lower().replace("kabupaten", "").replace("kab.", "").strip()
    for key in DISTRICT_POPULATION:
        k = key.lower()
        if n == k or n == k.replace("kota ", "") or k in n:
            return key
    return name.strip()


def _week_angle(week: int) -> float:
    return 2 * math.pi * ((week - 1) % 52) / 52.0


def build_features(
    population: int,
    epi_week: int,
    horizon: int,
    pm25_avg: float,
    pm25_max: float,
    hotspots: float,
    rainfall_mm: float,
    lags: List[float],
) -> List[float]:
    """lags = [lag1 (minggu terakhir), lag2, lag3, lag4]."""
    lag1 = max(float(lags[0]), 1.0)
    target_week = (epi_week + horizon - 1) % 52 + 1
    ang = _week_angle(target_week)
    return [
        math.log(population),
        math.sin(ang),
        math.cos(ang),
        float(pm25_avg),
        float(pm25_max),
        float(hotspots),
        float(rainfall_mm),
        lag1 / population * 100_000,
        lags[1] / lag1,
        lags[2] / lag1,
        lags[3] / lag1,
    ]


# ---------------------------------------------------------------------------
# Simulasi data latih
# ---------------------------------------------------------------------------

def simulate_training_data(seed: int = 2026) -> Dict[str, np.ndarray]:
    """Bangkitkan deret mingguan sintetis per kabupaten lalu ubah ke baris supervised."""
    rng = np.random.default_rng(seed)
    X: Dict[int, List[List[float]]] = {h: [] for h in HORIZONS}
    y: Dict[int, List[float]] = {h: [] for h in HORIZONS}
    years_of_row: Dict[int, List[int]] = {h: [] for h in HORIZONS}

    for district, pop in DISTRICT_POPULATION.items():
        peat = _PEAT_FACTOR[district]
        weeks, years, pm_avg, pm_max, hot, rain, cases = [], [], [], [], [], [], []
        ar_noise = 0.0
        prev_pm = 20.0
        prev_hot = 0
        dryness = 0.0  # indeks kekeringan kumulatif (mirip Keetch-Byram), memicu persistensi titik panas
        for year, sev_base in _FIRE_SEVERITY.items():
            sev = sev_base * rng.uniform(0.85, 1.15)
            peak = rng.normal(38.0, 2.5)
            width = rng.uniform(6.0, 9.0)
            for w in range(1, 53):
                season = math.exp(-(((w - peak) / width) ** 2))
                r = max(0.0, 80 * (1 - 0.85 * season * min(sev, 1.2)) + rng.normal(0, 15))
                dryness = 0.75 * dryness + max(0.0, 1 - r / 50)
                lam = 1.0 + 0.4 * prev_hot + 28 * season * sev * peat * dryness
                h = rng.poisson(lam)
                pm = max(8.0, 14 + 1.6 * h + 0.3 * prev_pm + rng.normal(0, 7))
                pmx = pm * rng.uniform(1.4, 1.9)
                base = pop / 100_000 * 55 * (1 + 0.12 * math.cos(2 * math.pi * (w - 3) / 52))
                effect = 1 + 0.0045 * pm + 0.0022 * prev_pm
                ar_noise = 0.5 * ar_noise + rng.normal(0, 0.07)
                c = base * effect * math.exp(ar_noise)
                weeks.append(w)
                years.append(year)
                pm_avg.append(pm)
                pm_max.append(pmx)
                hot.append(h)
                rain.append(r)
                cases.append(c)
                prev_pm = pm
                prev_hot = h

        n = len(cases)
        for t in range(3, n - max(HORIZONS)):
            lags = [cases[t], cases[t - 1], cases[t - 2], cases[t - 3]]
            for hz in HORIZONS:
                X[hz].append(build_features(pop, weeks[t], hz, pm_avg[t], pm_max[t], hot[t], rain[t], lags))
                y[hz].append(cases[t + hz] / cases[t])
                years_of_row[hz].append(years[t])

    return {
        **{f"X{h}": np.asarray(X[h]) for h in HORIZONS},
        **{f"y{h}": np.asarray(y[h]) for h in HORIZONS},
        **{f"year{h}": np.asarray(years_of_row[h]) for h in HORIZONS},
    }


# ---------------------------------------------------------------------------
# Forecaster
# ---------------------------------------------------------------------------

@dataclass
class ForecastPoint:
    horizon_week: int
    epi_week: int
    p10: int
    p50: int
    p90: int


class ISPAForecaster:
    def __init__(self) -> None:
        self.models: Dict[str, Any] = {}
        self.backend: Optional[str] = None
        self.metrics: Dict[str, Any] = {}
        self.trained_at: Optional[str] = None
        self.n_training_rows: int = 0

    # -- status -------------------------------------------------------------
    @property
    def is_trained(self) -> bool:
        return len(self.models) == len(QUANTILES) * len(HORIZONS)

    @property
    def method(self) -> str:
        if not self.is_trained:
            return "heuristic_fallback"
        return "lightgbm_quantile" if self.backend == "lightgbm" else "sklearn_gbr_quantile"

    def info(self) -> Dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "method": self.method,
            "is_trained": self.is_trained,
            "backend": self.backend,
            "quantiles": list(QUANTILES),
            "horizons_weeks": list(HORIZONS),
            "features": FEATURES,
            "trained_at": self.trained_at,
            "n_training_rows": self.n_training_rows,
            "validation_metrics": self.metrics,
            "training_data": "Simulasi sintetis surveilans ISPA-karhutla Kalbar 2017-2025 (ganti dengan data SKDR/SP2TP riil)",
        }

    # -- training -----------------------------------------------------------
    def _make_estimator(self, q: float, prefer_lightgbm: bool):
        if prefer_lightgbm:
            try:
                from lightgbm import LGBMRegressor

                return "lightgbm", LGBMRegressor(
                    objective="quantile",
                    alpha=q,
                    n_estimators=350,
                    learning_rate=0.04,
                    num_leaves=15,
                    min_child_samples=25,
                    n_jobs=1,
                    subsample=0.8,
                    subsample_freq=1,
                    colsample_bytree=0.9,
                    verbose=-1,
                    random_state=42,
                )
            except Exception:  # pragma: no cover - lightgbm opsional
                logger.info("LightGBM tidak tersedia, memakai sklearn GradientBoostingRegressor")
        from sklearn.ensemble import GradientBoostingRegressor

        return "sklearn", GradientBoostingRegressor(
            loss="quantile", alpha=q, n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42
        )

    def _fit_all(self, data: Dict[str, np.ndarray], mask_fn, prefer_lightgbm: bool) -> Dict[str, Any]:
        models = {}
        for h in HORIZONS:
            X, y, yrs = data[f"X{h}"], data[f"y{h}"], data[f"year{h}"]
            m = mask_fn(yrs)
            for q in QUANTILES:
                backend, est = self._make_estimator(q, prefer_lightgbm)
                est.fit(X[m], y[m])
                models[f"h{h}_q{int(q * 100)}"] = est
                self.backend = backend
        return models

    def train(self, prefer_lightgbm: bool = True, seed: int = 2026) -> Dict[str, Any]:
        data = simulate_training_data(seed)
        holdout_year = max(_FIRE_SEVERITY)

        # 1) Validasi: latih tanpa tahun terakhir, evaluasi pada tahun terakhir
        val_models = self._fit_all(data, lambda yrs: yrs < holdout_year, prefer_lightgbm)
        metrics: Dict[str, Any] = {"holdout_year": holdout_year}
        for h in HORIZONS:
            X, y, yrs = data[f"X{h}"], data[f"y{h}"], data[f"year{h}"]
            m = yrs == holdout_year
            lag1 = np.exp(X[m][:, 0]) * X[m][:, 7] / 100_000  # rekonstruksi lag1 absolut
            actual = y[m] * lag1
            p10 = val_models[f"h{h}_q10"].predict(X[m]) * lag1
            p50 = val_models[f"h{h}_q50"].predict(X[m]) * lag1
            p90 = val_models[f"h{h}_q90"].predict(X[m]) * lag1
            lo, hi = np.minimum(p10, p90), np.maximum(p10, p90)
            metrics[f"horizon_{h}"] = {
                "mape_p50_pct": round(float(np.mean(np.abs(actual - p50) / actual) * 100), 1),
                "mae_p50_cases": round(float(np.mean(np.abs(actual - p50))), 1),
                "coverage_p10_p90_pct": round(float(np.mean((actual >= lo) & (actual <= hi)) * 100), 1),
                "n_rows": int(m.sum()),
            }

        # 2) Model produksi: latih ulang dengan seluruh data
        self.models = self._fit_all(data, lambda yrs: np.ones_like(yrs, dtype=bool), prefer_lightgbm)
        self.metrics = metrics
        self.trained_at = datetime.now().isoformat(timespec="seconds")
        self.n_training_rows = int(len(data["y1"]))
        logger.info("Model ISPA dilatih (%s), metrik: %s", self.backend, metrics)
        return self.info()

    # -- persistence --------------------------------------------------------
    def save(self, model_dir: Path) -> Path:
        import joblib

        model_dir.mkdir(parents=True, exist_ok=True)
        path = model_dir / MODEL_FILENAME
        joblib.dump(
            {
                "version": MODEL_VERSION,
                "models": self.models,
                "backend": self.backend,
                "metrics": self.metrics,
                "trained_at": self.trained_at,
                "n_training_rows": self.n_training_rows,
            },
            path,
        )
        return path

    def load(self, model_dir: Path) -> bool:
        path = model_dir / MODEL_FILENAME
        if not path.exists():
            return False
        try:
            import joblib

            blob = joblib.load(path)
            if blob.get("version") != MODEL_VERSION:
                logger.warning("Versi artefak model berbeda (%s), perlu dilatih ulang", blob.get("version"))
                return False
            self.models = blob["models"]
            self.backend = blob["backend"]
            self.metrics = blob["metrics"]
            self.trained_at = blob["trained_at"]
            self.n_training_rows = blob.get("n_training_rows", 0)
            return self.is_trained
        except Exception as exc:
            logger.warning("Gagal memuat model ISPA (%s), memakai fallback heuristik", exc)
            self.models = {}
            return False

    # -- prediction ---------------------------------------------------------
    def _heuristic(self, epi_week: int, pm25_avg, pm25_max, hotspots, rainfall_mm, lags) -> List[ForecastPoint]:
        """Fallback: tren tertimbang lag + elastisitas PM2.5, titik panas, dan curah hujan."""
        l1, l2, l3, l4 = [max(float(v), 0.0) for v in lags]
        level = 0.5 * l1 + 0.3 * l2 + 0.15 * l3 + 0.05 * l4
        trend = (l1 - l3) / 2.0  # perubahan rata-rata per minggu
        smoke = 1 + 0.0018 * max(pm25_avg - 35, 0) + 0.0006 * max(pm25_max - pm25_avg, 0) + 0.002 * hotspots
        rain_damp = 1 - min(rainfall_mm, 150) / 150 * 0.15
        points = []
        for h in HORIZONS:
            persistence = 0.7 ** (h - 1)  # tren & efek asap meluruh
            p50 = max((level + trend * h * persistence) * (1 + (smoke - 1) * persistence) * rain_damp, 0)
            spread = 0.12 + 0.07 * h
            points.append(
                ForecastPoint(h, (epi_week + h - 1) % 52 + 1, round(p50 * (1 - spread)), round(p50), round(p50 * (1 + spread * 1.4)))
            )
        return points

    def predict(
        self,
        kabupaten: str,
        epi_week: int,
        pm25_avg: float,
        pm25_max: float,
        hotspot_count: float,
        rainfall_mm: float,
        lags: List[float],
        population: Optional[int] = None,
    ) -> Dict[str, Any]:
        district = normalize_district(kabupaten)
        pop = population or DISTRICT_POPULATION.get(district, 500_000)

        if not self.is_trained or lags[0] <= 0:
            points = self._heuristic(epi_week, pm25_avg, pm25_max, hotspot_count, rainfall_mm, lags)
            clean = self._heuristic(epi_week, 25.0, 40.0, 2, rainfall_mm, lags)
            method = "heuristic_fallback"
        else:
            points = self._predict_model(pop, epi_week, pm25_avg, pm25_max, hotspot_count, rainfall_mm, lags)
            clean = self._predict_model(pop, epi_week, 25.0, 40.0, 2, rainfall_mm, lags)
            method = self.method

        return {
            "kabupaten": district,
            "population": pop,
            "method": method,
            "model_version": MODEL_VERSION,
            "forecasts": [p.__dict__ for p in points],
            # Skenario kontrafaktual udara bersih: estimasi kasus yang disebabkan asap
            "smoke_attributable_p50": [max(p.p50 - c.p50, 0) for p, c in zip(points, clean)],
        }

    def _predict_model(self, pop, epi_week, pm25_avg, pm25_max, hotspots, rainfall_mm, lags) -> List[ForecastPoint]:
        lag1 = max(float(lags[0]), 1.0)
        points = []
        for h in HORIZONS:
            feats = np.asarray([build_features(pop, epi_week, h, pm25_avg, pm25_max, hotspots, rainfall_mm, lags)])
            q = sorted(max(float(self.models[f"h{h}_q{int(qq * 100)}"].predict(feats)[0]), 0.0) * lag1 for qq in QUANTILES)
            points.append(ForecastPoint(h, (epi_week + h - 1) % 52 + 1, round(q[0]), round(q[1]), round(q[2])))
        return points


forecaster = ISPAForecaster()


def ensure_model(model_dir: Path, train_if_missing: bool, prefer_lightgbm: bool) -> None:
    """Muat artefak model; latih & simpan jika belum ada (dipanggil saat startup)."""
    if forecaster.load(model_dir):
        logger.info("Model ISPA dimuat dari %s (%s)", model_dir, forecaster.method)
        return
    if not train_if_missing:
        logger.info("Model ISPA belum dilatih, memakai fallback heuristik")
        return
    try:
        forecaster.train(prefer_lightgbm=prefer_lightgbm)
        forecaster.save(model_dir)
    except Exception as exc:  # pragma: no cover
        logger.exception("Pelatihan model ISPA gagal (%s), memakai fallback heuristik", exc)
        forecaster.models = {}
