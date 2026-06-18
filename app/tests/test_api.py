"""API + web UI smoke tests using FastAPI's TestClient (SQLite-backed)."""

from fastapi.testclient import TestClient

from meeting_intel.api.main import app

client = TestClient(app)


def _upload(name="meeting.wav", title="My Meeting", content=b"RIFFfake"):
    return client.post(
        "/api/meetings",
        files={"file": (name, content, "audio/wav")},
        data={"title": title},
    )


def test_upload_creates_queued_meeting():
    r = _upload()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    mid = body["id"]

    detail = client.get(f"/api/meetings/{mid}").json()
    assert detail["title"] == "My Meeting"
    assert detail["source"] == "upload"


def test_upload_rejects_bad_extension():
    r = client.post(
        "/api/meetings",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"title": "x"},
    )
    assert r.status_code == 400


def test_list_meetings():
    _upload(title="One")
    _upload(title="Two")
    rows = client.get("/api/meetings").json()
    titles = [m["title"] for m in rows]
    assert "One" in titles and "Two" in titles


def test_downloads_work_even_without_results():
    mid = _upload(title="Doc Test").json()["id"]
    minutes = client.get(f"/api/meetings/{mid}/minutes.md")
    transcript = client.get(f"/api/meetings/{mid}/transcript.md")
    assert minutes.status_code == 200
    assert "Doc Test" in minutes.text
    assert transcript.status_code == 200
    assert "attachment" in minutes.headers.get("content-disposition", "")


def test_delete_meeting():
    mid = _upload(title="To Delete").json()["id"]
    r = client.delete(f"/api/meetings/{mid}")
    assert r.status_code == 200
    assert client.get(f"/api/meetings/{mid}").status_code == 404


def test_get_missing_returns_404():
    assert client.get("/api/meetings/doesnotexist").status_code == 404


def test_index_page_renders():
    r = client.get("/")
    assert r.status_code == 200
    assert "Meeting Intelligence" in r.text
    assert "no data leaves your network" in r.text.lower()


def test_detail_page_renders():
    mid = _upload(title="Detail Page").json()["id"]
    r = client.get(f"/meetings/{mid}")
    assert r.status_code == 200
    assert "Detail Page" in r.text


def test_healthz_reports_db_true():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] is True
    assert "ollama" in body
