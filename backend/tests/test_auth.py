from app.core.security import decrypt, encrypt, token_hash
from tests.conftest import sign_in


async def test_register_login_refresh_rotation_replay_logout(client):
    headers = await sign_in(client)
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["role"] == "admin"
    assert "password_hash" not in me.text
    old = client.cookies.get("akh_refresh")
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    rotated = client.cookies.get("akh_refresh")
    assert rotated != old
    replay = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"akh_refresh={old}"})
    assert replay.status_code == 401
    family = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"akh_refresh={rotated}"})
    assert family.status_code == 401
    await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "correct horse battery staple"},
    )
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_auth_validation_redacts_input_and_blocks_bad_origin(client):
    response = await client.post(
        "/api/v1/auth/register", json={"email": "wrong", "password": "secret"}
    )
    assert response.status_code == 422
    assert '"secret"' not in response.text
    assert (await client.get("/api/v1/chatbots")).status_code == 401
    headers = await sign_in(client, "member@example.com")
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["role"] == "user"
    assert (
        await client.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.example"})
    ).status_code == 403
    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "absent@example.com", "password": "a long wrong password"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"


def test_encryption_and_token_hash():
    cipher = encrypt("my-private-key")
    assert "my-private-key" not in cipher
    assert decrypt(cipher) == "my-private-key"
    assert token_hash("refresh") != "refresh"
