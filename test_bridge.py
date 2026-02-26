from fastapi.testclient import TestClient
import amica_alice_bridge as bridge
import time

client = TestClient(bridge.app)

HEADERS = {"x-bridge-api-key": bridge.BRIDGE_API_KEY}


def test_health():
    r = client.get("/health", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    print("health:", data)


def test_open_url_action_flow():
    # Request an open_url action
    payload = {"kind": "open_url", "args": {"url": "http://example.com"}}
    r = client.post("/action/request", json=payload, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "action_id" in data
    action_id = data["action_id"]
    print("action_id:", action_id)

    # Confirm the action
    r2 = client.post("/action/confirm", json={"action_id": action_id, "ok": True}, headers=HEADERS)
    assert r2.status_code == 200
    print("confirm response:", r2.json())


if __name__ == '__main__':
    test_health()
    test_open_url_action_flow()
    print("Tests completed")
