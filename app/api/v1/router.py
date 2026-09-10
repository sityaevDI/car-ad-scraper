from fastapi import APIRouter

from app.api.v1 import auth, listings, notifications, saved_searches, scrape, search, vehicles

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(auth.me_router)
api_router.include_router(search.router)
api_router.include_router(listings.router)
api_router.include_router(vehicles.router)
api_router.include_router(scrape.router)
api_router.include_router(saved_searches.router)
api_router.include_router(notifications.router)
