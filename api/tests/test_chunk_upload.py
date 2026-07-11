from __future__ import annotations

import hashlib

from starlette.testclient import TestClient


def _new_session(client, auth_headers) -> tuple[str, str]:
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
    return sid, uid


def _part(client, auth_headers, sid, uid, index, data) -> int:
    return client.post(
        f"/v1/practice-sessions/{sid}/audio/chunks/{uid}",
        content=data,
        headers={
            **auth_headers,
            "X-Chunk-Index": str(index),
            "X-Chunk-Checksum-Sha256": hashlib.sha256(data).hexdigest(),
            "Content-Type": "application/octet-stream",
        },
    ).status_code


def test_idempotent_chunk_reupload(client: TestClient, auth_headers):
    sid, uid = _new_session(client, auth_headers)
    data = b"abcd" * 4
    assert _part(client, auth_headers, sid, uid, 0, data) == 200
    # same index + same checksum => idempotent success
    assert _part(client, auth_headers, sid, uid, 0, data) == 200


def test_checksum_mismatch_rejected(client: TestClient, auth_headers):
    sid, uid = _new_session(client, auth_headers)
    data = b"abcd" * 4
    status = client.post(
        f"/v1/practice-sessions/{sid}/audio/chunks/{uid}",
        content=data,
        headers={
            **auth_headers,
            "X-Chunk-Index": "0",
            "X-Chunk-Checksum-Sha256": hashlib.sha256(b"different").hexdigest(),
            "Content-Type": "application/octet-stream",
        },
    ).status_code
    assert status == 400  # audio_upload_failed


def test_missing_chunk_on_complete(client: TestClient, auth_headers):
    sid, uid = _new_session(client, auth_headers)
    data = b"abcd" * 4
    _part(client, auth_headers, sid, uid, 0, data)  # only chunk 0
    r = client.post(
        f"/v1/practice-sessions/{sid}/audio/chunks/{uid}/complete",
        json={"totalChunks": 2, "durationMs": 500},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "audio_chunk_missing"


def test_complete_assembles_and_marks_uploaded(client: TestClient, auth_headers):
    sid, uid = _new_session(client, auth_headers)
    data = b"abcd" * 4
    _part(client, auth_headers, sid, uid, 0, data)
    _part(client, auth_headers, sid, uid, 1, data)
    final = hashlib.sha256(data * 2).hexdigest()
    r = client.post(
        f"/v1/practice-sessions/{sid}/audio/chunks/{uid}/complete",
        json={"totalChunks": 2, "durationMs": 800, "finalChecksumSha256": final},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["audio"]["status"] == "uploaded"
