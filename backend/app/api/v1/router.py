from fastapi import APIRouter

from app.api.v1 import admin, admin_media, auth, content, health, public

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(public.router)
api_router.include_router(content.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(admin_media.router)
