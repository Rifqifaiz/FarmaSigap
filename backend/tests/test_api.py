from datetime import date

from app.ml.ispa_model import ISPAForecaster
from app.routers.donation import expiry_flag
from app.services.stock import classify_status, days_of_stock, medicine_need_units

PHARMACIST = "Apt. Rian Pratama, S.Farm"


# ------------------------------------------------------------- formula ----
def test_need_and_days_formula():
    assert medicine_need_units(420, 0.15, 1) == 63
    assert days_of_stock(40, 12.8) == 40 / 12.8


def test_status_thresholds():
    assert classify_status(3.9, 4) == "merah"
    assert classify_status(4.0, 4) == "kuning"
    assert classify_status(10.9, 4) == "kuning"
    assert classify_status(11.0, 4) == "hijau"


def test_expiry_flags():
    today = date(2026, 10, 20)
    assert expiry_flag(date(2026, 10, 1), today)[0] == "merah"   # sudah kedaluwarsa
    assert expiry_flag(date(2027, 4, 19), today)[0] == "merah"   # < 6 bulan
    assert expiry_flag(date(2027, 4, 20), today)[0] == "kuning"  # tepat 6 bulan
    assert expiry_flag(date(2027, 10, 20), today)[0] == "kuning" # tepat 12 bulan
    assert expiry_flag(date(2027, 10, 21), today)[0] == "hijau"  # > 12 bulan


def test_heuristic_fallback_when_untrained():
    f = ISPAForecaster()
    res = f.predict("Kubu Raya", 43, 184.5, 312, 48, 6, [810, 740, 680, 510])
    assert res["method"] == "heuristic_fallback"
    for p in res["forecasts"]:
        assert p["p10"] <= p["p50"] <= p["p90"]


# ----------------------------------------------------------------- API ----
def test_root_and_health(client):
    assert client.get("/").json()["status"] == "online"
    assert client.get("/health").json()["status"] == "ok"


def test_inventory_pkm_a_is_critical(client):
    r = client.get("/api/inventory/priority-medicines", params={"puskesmas_id": "PKM-A"})
    assert r.status_code == 200
    rows = {m["medicine_id"]: m for m in r.json()["data"]}
    sal = rows["MED-SAL-INH"]
    assert sal["status"] == "merah"
    assert sal["days_remaining"] < sal["lead_time_days"]
    expected_need = sal["predicted_cases_p90"] * sal["proportion_treated"] * sal["units_per_case"]
    assert abs(sal["need_14_days"] - expected_need) <= 1


def test_inventory_unknown_pkm(client):
    assert client.get("/api/inventory/priority-medicines", params={"puskesmas_id": "PKM-Z"}).status_code == 404


def test_predict_ispa(client):
    body = {"kabupaten": "Kubu Raya", "epi_week": 43, "pm25_avg": 184.5, "pm25_max": 312, "hotspot_count": 48,
            "rainfall_mm": 6, "ispa_lag_1": 810, "ispa_lag_2": 740, "ispa_lag_3": 680, "ispa_lag_4": 510}
    d = client.post("/api/predict/ispa", json=body).json()
    assert len(d["forecasts"]) == 3
    for p in d["forecasts"]:
        assert p["p10"] <= p["p50"] <= p["p90"]


def test_ispa_trend_and_legacy_alias(client):
    d = client.get("/api/predict/ispa-trend").json()
    assert sum(1 for p in d["data"] if not p["is_actual"]) == 3
    assert client.get("/api/prediction/ispa-trend").status_code == 200


def test_redistribution_b_to_a_salbutamol(client):
    data = client.get("/api/redistribution/suggestions", params={"status": "pending"}).json()["data"]
    s = next(x for x in data if x["medicine_id"] == "MED-SAL-INH" and x["to_puskesmas_id"] == "PKM-A")
    assert s["from_puskesmas_id"] == "PKM-B"
    assert s["distance_km"] == 12.4
    assert s["snapshot"]["donor_surplus"] == 350


def test_approve_moves_stock_and_logs_audit(client):
    data = client.get("/api/redistribution/suggestions", params={"status": "pending"}).json()["data"]
    s = next(x for x in data if x["medicine_id"] == "MED-SAL-INH" and x["to_puskesmas_id"] == "PKM-A")

    def stock(pkm):
        rows = client.get("/api/inventory/priority-medicines", params={"puskesmas_id": pkm}).json()["data"]
        return next(m for m in rows if m["medicine_id"] == "MED-SAL-INH")["current_stock"]

    a0, b0 = stock("PKM-A"), stock("PKM-B")
    r = client.post("/api/redistribution/action", json={"suggestion_id": s["id"], "action": "approve", "pharmacist_name": PHARMACIST})
    assert r.status_code == 200, r.text
    assert r.json()["audit_log"]["pharmacist"] == PHARMACIST
    assert stock("PKM-A") == a0 + s["quantity"]
    assert stock("PKM-B") == b0 - s["quantity"]

    # tidak bisa diproses dua kali
    r2 = client.post("/api/redistribution/action", json={"suggestion_id": s["id"], "action": "reject", "pharmacist_name": PHARMACIST, "reason": "uji ulang"})
    assert r2.status_code == 409

    logs = client.get("/api/redistribution/audit-logs").json()["data"]
    assert any(l["entity_id"] == s["id"] and l["action"] == "approve" for l in logs)


def test_reject_requires_reason(client):
    pending = client.get("/api/redistribution/suggestions", params={"status": "pending"}).json()["data"]
    sid = pending[0]["id"]
    r = client.post("/api/redistribution/action", json={"suggestion_id": sid, "action": "reject", "pharmacist_name": PHARMACIST})
    assert r.status_code == 422
    r = client.post("/api/redistribution/action", json={"suggestion_id": sid, "action": "reject", "pharmacist_name": PHARMACIST, "reason": "Stok donor dipakai posko lokal"})
    assert r.status_code == 200
    assert r.json()["mutation"]["status"] == "rejected"


def test_posko_kit(client):
    d = client.post("/api/posko/calculate-kit", json={"total_refugees": 500, "duration_days": 14, "disaster_type": "karhutla"}).json()
    names = " ".join(i["medicine_name"] for i in d["kit_items"])
    for expected in ("Oralit", "Parasetamol Sirup", "Parasetamol Tablet", "Zinc", "Salbutamol", "Kassa", "Povidon", "Tetes Mata"):
        assert expected in names
    assert client.post("/api/posko/calculate-kit", json={"total_refugees": 100, "balita_percentage": 70, "elderly_percentage": 40}).status_code == 422


def test_donation_match(client):
    items = [
        {"medicine_name": "Salbutamol Inhaler 100 mcg", "quantity": 120, "unit": "Canister", "expiry_date": "2027-11-30"},
        {"medicine_name": "Amoksisilin 500 mg", "quantity": 500, "unit": "Kapsul", "expiry_date": "2028-04-15"},
        {"medicine_name": "Parasetamol Tablet 500 mg", "quantity": 300, "unit": "Tablet", "expiry_date": "2026-11-20"},
    ]
    d = client.post("/api/donation/match", json={"disaster_type": "karhutla", "items": items}).json()
    sal, amx, pct = d["results"]
    assert (sal["expiry_status"], sal["relevance_status"], sal["decision"]) == ("hijau", "prioritas_tinggi", "TERIMA")
    assert amx["relevance_status"] == "terbatas"
    assert (pct["expiry_status"], pct["decision"]) == ("merah", "TOLAK")
    # body berupa array langsung tetap diterima
    assert client.post("/api/donation/match", json=items).status_code == 200


def test_stock_update_creates_audit(client):
    r = client.put("/api/inventory/PKM-C/MED-AMB", json={"current_stock": 500, "updated_by": PHARMACIST, "reason": "Penerimaan IFK"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "hijau"
