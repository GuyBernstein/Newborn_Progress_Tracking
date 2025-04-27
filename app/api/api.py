from fastapi import APIRouter

from app.api.endpoints import auth, babies, media, progress

api_router = APIRouter()

# Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Baby management endpoints
api_router.include_router(babies.router, prefix="/babies", tags=["babies"])

# Progress tracking endpoints (nested under babies)
api_router.include_router(progress.router, prefix="/babies", tags=["progress"])

# Media management endpoints (nested under babies)
api_router.include_router(media.router, prefix="/babies", tags=["media"])