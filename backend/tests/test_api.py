import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["UPLOAD_DIR"] = "test_uploads"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import Base, engine  # noqa: E402

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def signup_and_token(email="editor@example.com"):
    res = client.post("/api/auth/signup", json={"email": email, "password": "strongpass1"})
    assert res.status_code == 201
    return res.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_signup_and_login():
    signup_and_token()
    res = client.post("/api/auth/login", data={"username": "editor@example.com", "password": "strongpass1"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_wrong_password_rejected():
    signup_and_token()
    res = client.post("/api/auth/login", data={"username": "editor@example.com", "password": "wrongpass"})
    assert res.status_code == 401


def test_project_crud_is_scoped_to_owner():
    token_a = signup_and_token("a@example.com")
    token_b = signup_and_token("b@example.com")
    project = client.post("/api/projects", json={"name": "Wedding edit"}, headers=auth(token_a)).json()

    assert len(client.get("/api/projects", headers=auth(token_a)).json()) == 1
    assert client.get("/api/projects", headers=auth(token_b)).json() == []
    assert client.delete(f"/api/projects/{project['id']}", headers=auth(token_b)).status_code == 404


def test_upload_tag_search_and_version():
    token = signup_and_token()
    project = client.post("/api/projects", json={"name": "Reel"}, headers=auth(token)).json()

    res = client.post(
        f"/api/projects/{project['id']}/clips",
        files={"file": ("beach_sunset.mp4", b"fakevideo", "video/mp4")},
        headers=auth(token),
    )
    assert res.status_code == 201
    clip = res.json()

    client.post(f"/api/clips/{clip['id']}/tags", json={"name": "Outdoor"}, headers=auth(token))
    found = client.get(f"/api/projects/{project['id']}/clips?tag=outdoor", headers=auth(token)).json()
    assert len(found) == 1

    searched = client.get(f"/api/projects/{project['id']}/clips?q=sunset", headers=auth(token)).json()
    assert len(searched) == 1

    v = client.post(f"/api/clips/{clip['id']}/versions", json={"note": "Color graded"}, headers=auth(token))
    assert v.status_code == 201
    assert v.json()["number"] == 1


def test_rejects_unsupported_file_type():
    token = signup_and_token()
    project = client.post("/api/projects", json={"name": "Docs"}, headers=auth(token)).json()
    res = client.post(
        f"/api/projects/{project['id']}/clips",
        files={"file": ("notes.exe", b"x", "application/octet-stream")},
        headers=auth(token),
    )
    assert res.status_code == 400
