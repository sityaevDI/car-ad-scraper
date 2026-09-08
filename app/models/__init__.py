"""Import every model module so `Base.metadata` (and Alembic autogenerate) sees all tables."""

from app.models.source import Source
from app.models.vehicle import Generation
from app.models.listing import Listing, ListingStatus
from app.models.snapshot import ListingSnapshot
from app.models.user import User
from app.models.saved_search import SavedSearch
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.notification import Notification, NotificationType
from app.models.subscription import SubscriptionPlan, UserSubscription

__all__ = [
    "Source",
    "Generation",
    "Listing",
    "ListingStatus",
    "ListingSnapshot",
    "User",
    "SavedSearch",
    "ScrapeJob",
    "ScrapeJobStatus",
    "ScrapeJobType",
    "Notification",
    "NotificationType",
    "SubscriptionPlan",
    "UserSubscription",
]
