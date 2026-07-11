from __future__ import annotations

import hashlib
import time

from starlette.testclient import TestClient


def test_request_id_is_echoed(client: TestClient):
    r = client.get("/v1/health", headers={"X-Request-Id": "req_xyz"})
    assert r.status_code == 200
    assert r.headers["x-request-id"] == "req_xyz"


def test_unauth_returns_standard_error_shape(client: TestClient):
    r = client.get("/v1/home")
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "auth_token_expired"
    assert "requestId" in err


def test_not_found_standard_shape(client: TestClient, auth_headers):
    r = client.get("/v1/practice-items/does_not_exist", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "practice_not_found"


def test_home_and_items(client: TestClient, auth_headers):
    assert client.get("/v1/home", headers=auth_headers).status_code == 200
    page = client.get("/v1/practice-items?limit=2", headers=auth_headers).json()
    assert len(page["items"]) == 2
    assert "nextCursor" in page


def test_evaluation_degrades_gracefully_without_model(client: TestClient, auth_headers):
    item = client.get("/v1/practice-items?limit=1&tag=juz30", headers=auth_headers).json()["items"][
        0
    ]
    sid = client.post(
        "/v1/practice-sessions", json={"practiceItemId": item["id"]}, headers=auth_headers
    ).json()["session"]["id"]

    uid = client.post(
        f"/v1/practice-sessions/{sid}/audio/chunks/init",
        json={"mimeType": "audio/wav"},
        headers=auth_headers,
    ).json()["upload"]["uploadId"]

    data = b"abcd" * 4
    for i in range(2):
        client.post(
            f"/v1/practice-sessions/{sid}/audio/chunks/{uid}",
            content=data,
            headers={
                **auth_headers,
                "X-Chunk-Index": str(i),
                "X-Chunk-Checksum-Sha256": hashlib.sha256(data).hexdigest(),
                "Content-Type": "application/octet-stream",
            },
        )
    final = hashlib.sha256(data * 2).hexdigest()
    comp = client.post(
        f"/v1/practice-sessions/{sid}/audio/chunks/{uid}/complete",
        json={"totalChunks": 2, "durationMs": 500, "finalChecksumSha256": final},
        headers=auth_headers,
    )
    assert comp.status_code == 200

    ev = client.post(f"/v1/practice-sessions/{sid}/evaluate", json={}, headers=auth_headers)
    assert ev.status_code == 201
    rid = ev.json()["evaluation"]["resultId"]

    time.sleep(0.8)  # let the background ASR task fail (model absent)
    result = client.get(f"/v1/evaluation-results/{rid}", headers=auth_headers).json()["result"]
    assert result["status"] == "failed"  # graceful, never a 500
