"""Unit tests: password hashing and JWT round-trips."""
from __future__ import annotations

import pytest

from app.core import security


def test_password_hash_roundtrip():
    stored = security.hash_password("secret-123")
    assert security.verify_password("secret-123", stored)
    assert not security.verify_password("wrong", stored)


def test_password_hash_is_salted():
    assert security.hash_password("same") != security.hash_password("same")


def test_hash_format_includes_scheme_and_iterations():
    stored = security.hash_password("x")
    scheme, iterations, salt, digest = stored.split("$")
    assert scheme == "pbkdf2_sha256"
    assert int(iterations) > 0


def test_jwt_roundtrip():
    token = security.create_access_token("user-abc")
    payload = security.decode_token(token)
    assert payload["sub"] == "user-abc"
    assert payload["type"] == "access"


def test_jwt_rejects_garbage():
    with pytest.raises(Exception):
        security.decode_token("not-a-token")


def test_jwt_has_expiry():
    import time

    token = security.create_access_token("u")
    payload = security.decode_token(token)
    assert payload["exp"] > time.time()
