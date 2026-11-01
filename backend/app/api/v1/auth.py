"""Authentication endpoints: register and login."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain.schemas import AuthResponse, LoginRequest, RegisterRequest, UserRead
from app.schemas.common import ok
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_payload(token: str, user) -> dict:
    return {
        "token": token,
        "token_type": "bearer",
        "user": UserRead(
            id=user.id, email=user.email, display_name=user.display_name, is_active=user.is_active
        ).model_dump(),
    }


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register(
        db, email=payload.email, password=payload.password, display_name=payload.display_name
    )
    token = auth_service.login(db, email=user.email, password=payload.password)
    return ok(_auth_payload(token, user), "Registration successful.", status_code=201)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    token = auth_service.login(db, email=payload.email, password=payload.password)
    user = auth_service.user_by_email(db, payload.email)
    return ok(_auth_payload(token, user), "Login successful.")
