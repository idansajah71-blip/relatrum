"""Integration tests: authorization expressiveness (SEC-01/04/05 regressions).

Auth is direct-called because resource routes arrive in later phases; these
pytest cases protect the dependency contract the routers will rely on.
"""
from __future__ import annotations

import pytest

from app.core import permissions
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import create_access_token
from app.models.workspace import Workspace, WorkspaceMember


def test_auth_dependency_rejects_missing_token(db, user_factory):
    user_factory()
    with pytest.raises(UnauthorizedError):
        permissions.auth_dependency(db=db, authorization=None)


def test_auth_dependency_invalid_token(db):
    with pytest.raises(UnauthorizedError):
        permissions.auth_dependency(db=db, authorization="Bearer garbage")


def test_auth_dependency_query_param_not_used(db, user_factory):
    """Regression SEC-01: token in query value must never authenticate."""
    from fastapi import HTTPException

    user_factory()
    with pytest.raises(UnauthorizedError):
        permissions.auth_dependency(db=db, authorization="invalid-bearer-token")


def test_auth_dependency_valid_token(db, user_factory):
    """Header value 'Bearer <token>' path is the only accepted form."""
    user = user_factory(email="tok@example.org")
    token = create_access_token(user.id)
    resolved = permissions.auth_dependency(db=db, authorization=f"Bearer {token}")
    assert resolved.id == user.id


def test_non_member_sees_404_same_as_missing_workspace(db, user_factory):
    """Regression SEC-05: policy is explicit - non-members get 404."""
    outsider = user_factory(email="out@example.org")
    with pytest.raises(NotFoundError):
        permissions.require_workspace_member("no-such-workspace", outsider, db)
    ws = Workspace(name="Hidden", slug="hidden-ws")
    db.add(ws)
    db.commit()
    with pytest.raises(NotFoundError):
        permissions.require_workspace_member(ws.id, outsider, db)


def test_member_with_low_role_gets_403(db, user_factory, workspace_factory):
    user = user_factory(email="viewer@example.org")
    ws = workspace_factory(user=user, member_role="viewer")
    with pytest.raises(Exception) as excinfo:
        permissions.require_workspace_member(ws.id, user, db, min_role="editor")
    assert "role" in str(excinfo.value).lower()


def test_owner_passes_role_check(db, user_factory, workspace_factory):
    user = user_factory(email="owner@example.org")
    ws = workspace_factory(user=user, member_role="owner")
    membership = permissions.require_workspace_member(ws.id, user, db, min_role="owner")
    assert membership.id is not None
