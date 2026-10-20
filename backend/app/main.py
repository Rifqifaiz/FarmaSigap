import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal, init_db
from app.ml.ispa_model import ensure_model, forecaster
from app.mock_data import seed_database
from app.routers import donation, hazard, inventory, posko, prediction, redistribution
from app.services.redistribution import generate_suggestions
from app.services.stock import sync_alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("farmasigap")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(reset=settings.reset_db_on_startup)
    # Model harus siap sebelum seed, karena stok awal dihitung dari konsumsi terprediksi
    ensure_model(settings.model_dir, settings.train_model_on_startup, settings.prefer_lightgbm)
    if settings.seed_on_startup:
        with SessionLocal() as db:
            if seed_database(db):
                generate_suggestions(db)
                sync_alerts(db)
    logger.info("FarmaSigap API siap — model: %s", forecaster.method)
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Platform Prediktif Berbasis AI & Big Data untuk Antisipasi Kebutuhan dan Distribusi Obat "
        "pada Situasi Bencana di Indonesia. Fokus tahap 1: Karhutla & lonjakan ISPA Kabupaten Kubu Raya, Kalimantan Barat."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hazard.router)
app.include_router(inventory.router)
app.include_router(prediction.router)
app.include_router(prediction.legacy_router)
app.include_router(redistribution.router)
app.include_router(posko.router)
app.include_router(donation.router)


@app.get("/", tags=["Health"])
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and FRONTEND_DIR.exists():
        return RedirectResponse("/app/")
    return {
        "platform": "FarmaSigap",
        "description": "Disaster Medicine Anticipation & Predictive Supply Chain API",
        "status": "online",
        "version": settings.app_version,
        "docs_url": "/docs",
        "dashboard_url": "/app/" if FRONTEND_DIR.exists() else None,
        "active_disaster": settings.active_disaster,
        "active_district": settings.active_district,
        "model": forecaster.method,
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "model_trained": forecaster.is_trained}


# Sajikan dasbor frontend dari backend yang sama: http://localhost:8000/app/
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/app", include_in_schema=False)
    def _app_redirect():
        return RedirectResponse("/app/")


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
