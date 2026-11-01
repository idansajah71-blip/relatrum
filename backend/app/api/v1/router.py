"""API v1 router aggregation."""
from fastapi import APIRouter

api_router = APIRouter()


def register_routers() -> None:
    from app.api.v1 import system

    api_router.include_router(system.router, tags=["system"])


register_routers()
