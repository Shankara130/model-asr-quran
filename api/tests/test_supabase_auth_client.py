import httpx
import pytest

from api.core.errors import ApiError
from api.services import supabase_auth


class FailingAsyncClient:
    def __init__(self, *, error, **_kwargs):
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, *_args, **_kwargs):
        raise self.error

    async def post(self, *_args, **_kwargs):
        raise self.error


def _client(monkeypatch, error):
    monkeypatch.setattr(supabase_auth, "supabase_auth_enabled", lambda: True)
    monkeypatch.setattr(supabase_auth.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(supabase_auth.settings, "supabase_anon_key", "anon-test-key")
    monkeypatch.setattr(supabase_auth.settings, "supabase_service_role_key", None)
    monkeypatch.setattr(
        supabase_auth.httpx,
        "AsyncClient",
        lambda **kwargs: FailingAsyncClient(error=error, **kwargs),
    )
    return supabase_auth.SupabaseAuthClient()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("dns unavailable"),
        httpx.ConnectTimeout("auth timeout"),
    ],
)
async def test_get_user_maps_network_failure_to_service_unavailable(monkeypatch, error):
    client = _client(monkeypatch, error)

    with pytest.raises(ApiError) as exc:
        await client.get_user("access-token")

    assert exc.value.code == "auth_service_unavailable"
    assert exc.value.status == 503


@pytest.mark.asyncio
async def test_login_maps_network_failure_to_service_unavailable(monkeypatch):
    client = _client(monkeypatch, httpx.ConnectError("dns unavailable"))

    with pytest.raises(ApiError) as exc:
        await client.sign_in_with_password(email="reader@example.test", password="secret")

    assert exc.value.code == "auth_service_unavailable"
    assert exc.value.status == 503


@pytest.mark.asyncio
async def test_logout_maps_network_failure_to_service_unavailable(monkeypatch):
    client = _client(monkeypatch, httpx.ConnectTimeout("auth timeout"))

    with pytest.raises(ApiError) as exc:
        await client.logout("access-token")

    assert exc.value.code == "auth_service_unavailable"
    assert exc.value.status == 503
