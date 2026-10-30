from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.projects import router as projects_router
from app.api.v1.research import router as research_router
from app.api.v1.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(analytics_router)
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(projects_router)
api_router.include_router(research_router)
api_router.include_router(reports_router)