"""Route and workflow tests against a temporary database."""

import io
import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import app as app_module  # noqa: E402
import db  # noqa: E402
import vision  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A Flask test client backed by a throw-away database."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.sqlite3")
    monkeypatch.setattr(app_module, "PHOTOS", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir(parents=True, exist_ok=True)
    db.init_db(tmp_path / "t.sqlite3")
    app_module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app_module.app.test_client() as c:
        yield c


def _photo(kind="bag", colour="blue", seed=1):
    """A fresh in-memory JPEG upload tuple for the Flask test client."""
    img = vision.make_sample(colour, kind, seed=seed)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return io.BytesIO(buf.tobytes()), "item.jpg"


def register(c, email="alice@college.edu"):
    return c.post("/register", data={
        "name": "Alice T", "email": email, "password": "shadow123",
        "department": "CSE",
    }, follow_redirects=True)


def test_index_and_browse_are_public(client):
    assert client.get("/").status_code == 200
    assert client.get("/browse").status_code == 200


def test_dashboard_requires_login(client):
    r = client.get("/dashboard")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_register_logs_in(client):
    r = register(client)
    assert b"Signed in" in r.data or b"Account created" in r.data
    assert client.get("/dashboard").status_code == 200


def test_short_password_rejected(client):
    r = client.post("/register", data={
        "name": "Bob", "email": "b@college.edu", "password": "123",
        "department": "CSE"}, follow_redirects=True)
    assert b"at least 6 characters" in r.data


def test_upload_creates_item_with_descriptor(client):
    register(client)
    r = client.post("/report", data={
        "type": "lost", "title": "Blue bag", "category": "Bag",
        "description": "blue", "place": "Canteen", "seen_on": "2026-11-01",
        "photo": _photo(),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200
    with app_module.app.app_context():
        conn = db.connect(app_module.DB_PATH)
        row = conn.execute("SELECT * FROM items").fetchone()
        assert row["title"] == "Blue bag"
        assert row["descriptor"] and len(row["descriptor"]) == vision.BINS * 4


def test_upload_requires_a_photo(client):
    register(client)
    r = client.post("/report", data={
        "type": "lost", "title": "No photo", "category": "Bag",
    }, follow_redirects=True)
    assert b"Attach a photograph" in r.data


def test_claim_flow_end_to_end(client):
    register(client, "finder@college.edu")
    client.post("/report", data={
        "type": "found", "title": "Found bag", "category": "Bag",
        "place": "Lab", "photo": _photo(seed=2),
    }, content_type="multipart/form-data", follow_redirects=True)
    client.get("/logout")

    register(client, "owner@college.edu")
    client.post("/report", data={
        "type": "lost", "title": "Lost bag", "category": "Bag",
        "place": "Canteen", "photo": _photo(seed=1),
    }, content_type="multipart/form-data", follow_redirects=True)

    with app_module.app.app_context():
        conn = db.connect(app_module.DB_PATH)
        lost = conn.execute("SELECT id FROM items WHERE type='lost'").fetchone()["id"]
        found = conn.execute("SELECT id FROM items WHERE type='found'").fetchone()["id"]

    r = client.post(f"/claim/{lost}/{found}", follow_redirects=True)
    assert r.status_code == 200
    with app_module.app.app_context():
        conn = db.connect(app_module.DB_PATH)
        claim = conn.execute("SELECT * FROM claims").fetchone()
        assert claim["status"] == "pending"
        assert claim["receiver_id"] != claim["sender_id"]


def test_cannot_claim_own_report(client):
    register(client)
    client.post("/report", data={
        "type": "found", "title": "Mine", "category": "Bag",
        "photo": _photo()}, content_type="multipart/form-data", follow_redirects=True)
    with app_module.app.app_context():
        conn = db.connect(app_module.DB_PATH)
        item = conn.execute("SELECT id, student_id FROM items").fetchone()
    r = client.post(f"/claim/{item['id']}/{item['id']}", follow_redirects=True)
    assert b"cannot claim your own" in r.data


def test_wrong_password_is_rejected(client):
    register(client, "carol@college.edu")
    client.get("/logout")
    r = client.post("/login", data={"email": "carol@college.edu",
                                   "password": "wrong"}, follow_redirects=True)
    assert b"Wrong e-mail" in r.data


def test_404_page(client):
    assert client.get("/item/9999").status_code == 404


def test_missing_instance_directory_is_recreated(client, tmp_path, monkeypatch):
    """A wiped data directory must not 500: the app recreates it on first use."""
    fresh = tmp_path / "scratch" / "nested"
    monkeypatch.setattr(app_module, "DB_PATH", fresh / "sf.sqlite3")
    monkeypatch.setattr(app_module, "PHOTOS", fresh / "uploads")
    assert not fresh.exists()
    assert client.get("/").status_code == 200
    assert (fresh / "sf.sqlite3").exists()
