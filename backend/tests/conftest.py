import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="farmasigap-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["DEMO_REFERENCE_DATE"] = "2026-10-20"
os.environ["RESET_DB_ON_STARTUP"] = "true"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
