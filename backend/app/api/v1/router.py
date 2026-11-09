from fastapi import APIRouter

from app.api.v1 import content, health, public

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(public.router)
api_router.include_router(content.router)
