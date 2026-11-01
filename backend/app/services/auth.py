"""Authentication services: registration and login (JWT issued by core.security)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.services import audit


def register(db: Session, *, email: str, password: str, display_name: str, actor=None) -> User:
    existing = db.scalar(select(User).where(User.email == email.lower().strip()))
    if existing is not None:
        # Auto-provisioned inactive placeholders (via member invitations) can be claimed.
        if not existing.is_active and email.lower().strip() == existing.email:
            existing.password_hash = hash_password(password)
            existing.display_name = display_name or existing.display_name
            existing.is_active = True
            db.commit()
            return existing
        raise ConflictError("An account with this email already exists.")
    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        display_name=display_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def login(db: Session, *, email: str, password: str) -> str:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password.")
    return create_access_token(user.id)


def user_by_email(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None:
        raise UnauthorizedError("Invalid email or password.")
    return user
