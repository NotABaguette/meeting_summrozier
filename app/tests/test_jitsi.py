import httpx
from fastapi.testclient import TestClient

from meeting_intel.api.main import app
from meeting_intel.config import Settings

client = TestClient(app)


def test_jitsi_domain_and_enabled():
    assert Settings(jitsi_server_url="https://meet.x.com/").jitsi_domain == "meet.x.com"
    assert Settings(jitsi_server_url="meet.x.com").jitsi_domain == "meet.x.com"
    s = Settings(jitsi_server_url="")
    assert s.jitsi_domain == "" and s.jitsi_enabled is False
    assert Settings(jitsi_server_url="https://meet.x.com").jitsi_enabled is True


def test_meet_launcher_renders():
    r = client.get("/meet")
    assert r.status_code == 200
    assert "Start or join a meeting" in r.text


def test_meet_room_requires_jitsi_configured():
    # JITSI_SERVER_URL is unset in tests -> hosted meeting is unavailable.
    r = client.get("/meet/SomeRoom")
    assert r.status_code == 503


def test_jitsi_join_proxies_to_bot(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"session_id": "abc", "state": "starting"}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(httpx, "post", fake_post)
    r = client.post("/api/jitsi/join", json={"room": "WeeklySync"})
    assert r.status_code == 200
    assert r.json()["session_id"] == "abc"
    assert captured["url"].endswith("/join")
    assert captured["json"]["room"] == "WeeklySync"


def test_jitsi_join_handles_bot_down(monkeypatch):
    def boom(url, json=None, timeout=None):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "post", boom)
    r = client.post("/api/jitsi/join", json={"room": "X"})
    assert r.status_code == 502
