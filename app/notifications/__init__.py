"""Notification creation (app/notifications/service.py), in-app read/list API
(app/api/v1/notifications.py) and email delivery (app/notifications/delivery.py). The actual
events — NEW_MATCH from saved searches, PRICE_DROP from follows — are generated from the scrape
pipeline in app/notifications/matching.py (issue #26).
"""
