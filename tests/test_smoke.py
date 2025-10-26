# === FILE: tests/test_smoke.py
from app import auth as auth_module
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import User  # matcher app/auth.py

# ---- Override auth: returnér en "leader" test-bruger ----


def require_role_override(roles):
    def _dep():
        # matcher constructor: User(user_id: int, role: str)
        return User(user_id=1, role="leader")
    return _dep


# Registrér overrides inden TestClient oprettes
app.dependency_overrides[auth_module.require_role] = require_role_override

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def seed_once():
    client.post("/admin/clear-demo-data")
    r = client.post("/admin/seed-demo-data")
    assert r.status_code == 200
    yield


def test_children_list():
    r = client.get("/children")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_exercises_exist():
    r = client.get("/exercises/all")
    assert r.status_code == 200
    ex = r.json()
    assert any(e["domain"] == "rim" for e in ex)


def test_thresholds_exist():
    r = client.get("/thresholds")
    assert r.status_code == 200
    th = r.json()
    assert any(t["domain"] == "ordforraad" for t in th)


def test_progress_post_and_get():
    child = client.get("/children").json()[0]
    cid = child["id"]

    payload = [
        {"domain": "rim", "score": 50, "color": "green"},
        {"domain": "ordforraad", "score": 42, "color": "yellow"},
    ]
    r_post = client.post(f"/children/{cid}/progress", json=payload)
    assert r_post.status_code == 200
    assert isinstance(r_post.json(), list)
    assert len(r_post.json()) == 2

    r_get = client.get(f"/children/{cid}/progress")
    assert r_get.status_code == 200
    rows = r_get.json()
    assert isinstance(rows, list)
    assert any(row["domain"] == "rim" for row in rows)
