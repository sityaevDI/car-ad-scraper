"""Import every model module so `Base.metadata` (and Alembic autogenerate) sees all tables."""

from app.models.listing import Listing, ListingStatus
from app.models.notification import Notification, NotificationType
from app.models.saved_search import SavedSearch
from app.models.scheduled_scrape import ScheduledScrape
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.snapshot import ListingSnapshot
from app.models.source import Source
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.user import User
from app.models.vehicle import Generation

__all__ = [
    "Source",
    "Generation",
    "Listing",
    "ListingStatus",
    "ListingSnapshot",
    "User",
    "SavedSearch",
    "ScheduledScrape",
    "ScrapeJob",
    "ScrapeJobStatus",
    "ScrapeJobType",
    "Notification",
    "NotificationType",
    "SubscriptionPlan",
    "UserSubscription",
]
