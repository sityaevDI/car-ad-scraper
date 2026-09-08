from fastapi import APIRouter

from app.api.v1 import listings, search, vehicles

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(search.router)
api_router.include_router(listings.router)
api_router.include_router(vehicles.router)
