"""API v1 router aggregation."""
from fastapi import APIRouter

api_router = APIRouter()


def register_routers() -> None:
    from app.api.v1 import analysis, auth, cases, findings, graph, reports, sources, statements, system, verification, workspaces

    api_router.include_router(auth.router, tags=["auth"])
    api_router.include_router(workspaces.router, tags=["workspaces"])
    api_router.include_router(cases.router, tags=["cases"])
    api_router.include_router(sources.router, tags=["sources"])
    api_router.include_router(statements.router, tags=["statements"])
    api_router.include_router(analysis.router, tags=["analysis"])
    api_router.include_router(findings.router, tags=["findings"])
    api_router.include_router(verification.router, tags=["verification"])
    api_router.include_router(reports.router, tags=["reports"])
    api_router.include_router(graph.router, tags=["graph"])
    api_router.include_router(system.router, tags=["system"])


register_routers()
