"""Pydantic v2 schemas (request & response)."""

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

DisasterType = Literal["karhutla", "banjir", "gempa"]
StockStatus = Literal["merah", "kuning", "hijau"]


# ---------------------------------------------------------------- Hazard ----
class DiseaseInfo(BaseModel):
    name: str
    icd10: str
    note: str


class HazardMedicine(BaseModel):
    medicine_id: str
    name: str
    category: str
    form: str
    unit: str
    priority: bool
    restricted: bool
    indication: str
    proportion_treated: float
    units_per_case: float
    is_antibiotic: bool
    pharmacy_note: str


class HazardMappingResponse(BaseModel):
    disaster_type: DisasterType
    label: str
    hazard_indicators: List[str]
    dominant_diseases: List[DiseaseInfo]
    vulnerable_groups: List[str]
    pharmacy_notes: List[str]
    medicines: List[HazardMedicine]


class HazardMappingRequest(BaseModel):
    disaster_type: DisasterType = "karhutla"


# ------------------------------------------------------------- Inventory ----
class MedicineStock(BaseModel):
    id: str
    puskesmas_id: str
    puskesmas_name: str
    medicine_id: str
    medicine_name: str
    category: str
    form: str
    unit: str
    priority: bool
    restricted: bool
    current_stock: int
    predicted_cases_p90: float = Field(description="Prediksi kasus P90 PKM selama horizon perencanaan")
    proportion_treated: float
    units_per_case: float
    need_14_days: int = Field(description="Kebutuhan = kasus P90 × proporsi × unit per kasus")
    planning_horizon_days: int
    daily_consumption_forecast: float
    days_remaining: float = Field(description="Stok ÷ konsumsi harian (999 = tidak ada konsumsi terprediksi)")
    lead_time_days: int
    safe_threshold_days: int
    status: StockStatus
    shortfall_units: int
    reorder_to_safe_units: int
    note: str
    updated_at: Optional[str] = None


class InventoryResponse(BaseModel):
    status: str = "success"
    puskesmas_id: str
    puskesmas: str
    lead_time_days: int
    disaster_type: DisasterType
    formula: Dict[str, str]
    data: List[MedicineStock]


class StockUpdateRequest(BaseModel):
    current_stock: int = Field(..., ge=0)
    updated_by: str = Field(..., min_length=3, examples=["Apt. Rian Pratama, S.Farm"])
    reason: Optional[str] = Field(None, examples=["Stock opname mingguan"])


class StockCalcRequest(BaseModel):
    """Kalkulator formula mandiri (tanpa database)."""

    current_stock: float = Field(..., ge=0, examples=[40])
    lead_time_days: float = Field(..., gt=0, examples=[4])
    predicted_cases_p90: float = Field(..., ge=0, description="Prediksi kasus P90 selama horizon", examples=[420])
    proportion_treated: float = Field(..., ge=0, le=1, examples=[0.15])
    units_per_case: float = Field(..., ge=0, examples=[1])
    horizon_days: int = Field(14, gt=0)


class StockCalcResponse(BaseModel):
    need_units: float
    daily_consumption_forecast: float
    days_remaining: float
    status: StockStatus
    thresholds: Dict[str, float]


# ------------------------------------------------------------ Prediction ----
class ISPAPredictRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kabupaten": "Kubu Raya",
                "epi_week": 43,
                "pm25_avg": 184.5,
                "pm25_max": 312.0,
                "hotspot_count": 48,
                "rainfall_mm": 6.0,
                "ispa_lag_1": 810,
                "ispa_lag_2": 740,
                "ispa_lag_3": 680,
                "ispa_lag_4": 510,
            }
        }
    )

    kabupaten: str = Field("Kubu Raya", description="Nama kabupaten/kota")
    epi_week: int = Field(..., ge=1, le=53, description="Minggu epidemiologi data terakhir (lag 1)")
    pm25_avg: float = Field(..., ge=0, description="Rata-rata PM2.5 mingguan (µg/m³)")
    pm25_max: float = Field(..., ge=0, description="PM2.5 maksimum mingguan (µg/m³)")
    hotspot_count: int = Field(..., ge=0, description="Jumlah titik panas (NASA FIRMS)")
    rainfall_mm: float = Field(..., ge=0, description="Curah hujan mingguan (mm)")
    ispa_lag_1: int = Field(..., ge=0, description="Kunjungan ISPA minggu terakhir")
    ispa_lag_2: int = Field(..., ge=0)
    ispa_lag_3: int = Field(..., ge=0)
    ispa_lag_4: int = Field(..., ge=0)
    population: Optional[int] = Field(None, gt=0, description="Populasi (opsional, jika kabupaten tidak dikenal)")

    @model_validator(mode="after")
    def _check_pm(self):
        if self.pm25_max < self.pm25_avg:
            raise ValueError("pm25_max tidak boleh lebih kecil dari pm25_avg")
        return self


class ISPAForecastWeek(BaseModel):
    horizon_week: int
    epi_week: int
    p10: int
    p50: int
    p90: int
    week_start: Optional[str] = None


class ISPAPredictResponse(BaseModel):
    status: str = "success"
    kabupaten: str
    population: int
    method: str
    model_version: str
    forecasts: List[ISPAForecastWeek]
    smoke_attributable_p50: List[int]
    interpretation: str


class ISPAForecastPoint(BaseModel):
    week_label: str
    week_start: str
    is_actual: bool
    actual_cases: Optional[int] = None
    p10_cases: Optional[int] = None
    p50_cases: Optional[int] = None
    p90_cases: Optional[int] = None


# -------------------------------------------------------- Redistribution ----
class RedistributionSuggestion(BaseModel):
    id: str
    from_puskesmas_id: str
    from_puskesmas_name: str
    to_puskesmas_id: str
    to_puskesmas_name: str
    medicine_id: str
    medicine_name: str
    medicine_category: str
    unit: str
    quantity: int
    distance_km: float
    estimated_delivery_hours: int
    priority: StockStatus
    rationale: str
    snapshot: Dict[str, Any]
    status: Literal["pending", "approved", "rejected", "superseded"]
    created_at: str
    action_by: Optional[str] = None
    action_at: Optional[str] = None
    action_reason: Optional[str] = None


class RedistributionActionRequest(BaseModel):
    suggestion_id: str = Field(..., examples=["REDIST-2026-001"])
    action: Literal["approve", "reject"]
    pharmacist_name: str = Field(..., min_length=3, examples=["Apt. Rian Pratama, S.Farm"])
    reason: Optional[str] = Field(None, description="Alasan keputusan (wajib untuk reject)")
    notes: Optional[str] = Field(None, description="Alias lama untuk `reason`")

    @property
    def effective_reason(self) -> Optional[str]:
        return self.reason or self.notes


class AuditLogEntry(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    pharmacist: str
    reason: str
    details: Dict[str, Any]
    timestamp: str


# ----------------------------------------------------------------- Posko ----
class PoskoKitRequest(BaseModel):
    total_refugees: int = Field(..., gt=0, le=200_000, examples=[500])
    balita_percentage: float = Field(15.0, ge=0, le=100)
    elderly_percentage: float = Field(12.0, ge=0, le=100)
    pregnant_percentage: float = Field(3.0, ge=0, le=100)
    duration_days: int = Field(14, gt=0, le=180)
    disaster_type: DisasterType = "karhutla"

    @model_validator(mode="after")
    def _check_pct(self):
        if self.balita_percentage + self.elderly_percentage + self.pregnant_percentage > 100:
            raise ValueError("Total proporsi balita + lansia + ibu hamil tidak boleh melebihi 100%")
        return self


class PoskoKitItem(BaseModel):
    medicine_name: str
    form: str
    dosage_category: str
    target_group: str
    calculated_quantity: int
    unit: str
    pack_size: int
    packs: int
    clinical_note: str


class PoskoKitResponse(BaseModel):
    status: str = "success"
    parameters: Dict[str, Any]
    iehk_reference: Dict[str, Any]
    kit_items: List[PoskoKitItem]
    notes: List[str]


# -------------------------------------------------------------- Donation ----
class DonationItem(BaseModel):
    medicine_name: str = Field(..., min_length=2, examples=["Salbutamol Inhaler 100 mcg"])
    quantity: int = Field(..., gt=0, examples=[120])
    unit: str = Field("Unit", examples=["Canister"])
    expiry_date: date = Field(..., examples=["2027-11-30"])
    donor_source: str = Field("Tidak disebutkan", examples=["NGO Peduli Sehat"])


class DonationMatchRequest(BaseModel):
    disaster_type: DisasterType = "karhutla"
    items: List[DonationItem] = Field(..., min_length=1)


class DonationMatchResult(BaseModel):
    medicine_name: str
    quantity: int
    unit: str
    expiry_date: str
    donor_source: str
    months_to_expiry: int
    expiry_status: StockStatus
    expiry_reason: str
    matched_medicine_id: Optional[str] = None
    matched_medicine_name: Optional[str] = None
    relevance_status: Literal["prioritas_tinggi", "diterima", "terbatas", "tidak_relevan"]
    relevance_reason: str
    decision: Literal["TERIMA", "TERIMA_BERSYARAT", "TOLAK"]
    recommendation: str
    allocation_suggestion: Optional[str] = None
    # kompatibilitas field lama
    reason: str


class DonationMatchResponse(BaseModel):
    status: str = "success"
    disaster_type: DisasterType
    evaluated_at: str
    total_evaluated: int
    summary: Dict[str, int]
    results: List[DonationMatchResult]
