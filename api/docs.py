"""OpenAPI / Swagger metadata: app description and tag descriptions."""

from __future__ import annotations

DESCRIPTION = """\
**Sobat Ngaji backend** — serves auth, profile, practice items/sessions, audio
upload, evaluation, and insights for the Quran-recitation practice app, wrapping
the wav2vec2 / sherpa-onnx ASR engine.

### Base URL
All REST endpoints are under `/v1`. Realtime runs over WebSocket at
`/v1/realtime/practice-sessions/{sessionId}?token=<realtimeToken>` (not listed
below — see the backend spec).

### Authentication
All endpoints **except** `POST /v1/auth/{signup,login,refresh,logout}` require:

```
Authorization: Bearer <accessToken>
```

> **Dev stub auth:** passwords are not verified; sign in as the seeded dev user
> `alya@sobat.ngaji` with any password. Access tokens are HMAC-signed
> (`itsdangerous`) and short-lived; refresh tokens are hashed at rest.

### Standard headers
Send `X-Request-Id: <uuid>` on requests (one is generated if omitted); every
response echoes it. Optional: `X-Client-Platform`, `X-Client-Version`.

### Error shape
Every error uses this shape (codes & HTTP statuses are fixed — see the backend
spec `§4`):

```json
{
  "error": {
    "code": "audio_unprocessable",
    "message": "...",
    "requestId": "req_...",
    "details": {}
  }
}
```

### AI results are advisory
Evaluation output is labeled **`evaluasi awal`** (initial assessment) — never an
absolute ruling on Qur'an recitation correctness.
"""

TAGS = [
    {"name": "auth", "description": "Signup, login, current user, token refresh, logout."},
    {"name": "profile", "description": "User identity, learning summary, and preferences."},
    {"name": "home", "description": "Daily Qira, greeting, weekly snapshot, recommendation."},
    {"name": "practice-items", "description": "Curated verses and letter drills to practice."},
    {"name": "practice-sessions", "description": "Practice sessions and history."},
    {"name": "audio", "description": "Simple multipart and chunked audio upload."},
    {"name": "evaluation", "description": "Request recitation evaluation and read its result."},
    {"name": "insights", "description": "Weekly insight, letter mastery, practice history."},
    {"name": "reference-audio", "description": "Private, auth-gated reference recitation audio."},
    {"name": "health", "description": "Service health check."},
]
