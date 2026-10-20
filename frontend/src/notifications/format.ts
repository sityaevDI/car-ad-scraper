import i18n from '../i18n'
import type { NewMatchListingPreview, NotificationOut } from '../lib/notifications'

export function notificationTitle(notification: NotificationOut): string {
  if (notification.type === 'new_match') {
    const payload = notification.payload ?? {}
    const name = typeof payload.saved_search_name === 'string' ? payload.saved_search_name : null
    return name ? `«${name}»` : i18n.t('notifications.types.new_match')
  }
  return i18n.t(`notifications.types.${notification.type}`, { defaultValue: notification.type })
}

export type NotificationDateBucket = 'today' | 'yesterday' | 'week' | 'earlier'

function notificationDateBucket(createdAt: string): NotificationDateBucket {
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const daysAgo = Math.floor((startOfDay(new Date()) - startOfDay(new Date(createdAt))) / 86_400_000)
  if (daysAgo <= 0) return 'today'
  if (daysAgo === 1) return 'yesterday'
  if (daysAgo <= 7) return 'week'
  return 'earlier'
}

// Groups an already created_at-desc-sorted list into date buckets for the notifications page,
// preserving each bucket's relative order.
export function groupNotificationsByDate<T extends { created_at: string }>(
  notifications: T[],
): { label: string; items: T[] }[] {
  const buckets = new Map<NotificationDateBucket, T[]>()
  for (const notification of notifications) {
    const bucket = notificationDateBucket(notification.created_at)
    const items = buckets.get(bucket)
    if (items) items.push(notification)
    else buckets.set(bucket, [notification])
  }
  return (['today', 'yesterday', 'week', 'earlier'] as const)
    .filter((bucket) => buckets.has(bucket))
    .map((bucket) => ({ label: i18n.t(`notifications.buckets.${bucket}`), items: buckets.get(bucket)! }))
}

function isNewMatchListingPreview(value: unknown): value is NewMatchListingPreview {
  if (!value || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  return typeof v.id === 'string' && typeof v.title === 'string' && typeof v.price === 'number'
}

// The specific new listings behind a NEW_MATCH notification's count, so a saved search matching
// several listings at once shows *which* ones — a bare "N new" count doesn't say what changed.
// Capped server-side (app/notifications/matching.py::_NEW_LISTINGS_PREVIEW_LIMIT); the remainder
// beyond this list is only reflected in payload.new_listings_count.
export function notificationNewListingsPreview(notification: NotificationOut): NewMatchListingPreview[] {
  if (notification.type !== 'new_match') return []
  const raw = notification.payload?.new_listings
  if (!Array.isArray(raw)) return []
  return raw.filter(isNewMatchListingPreview)
}

export function notificationNewListingsCount(notification: NotificationOut): number {
  const count = notification.payload?.new_listings_count
  return typeof count === 'number' ? count : 0
}

export function notificationDescription(notification: NotificationOut): string {
  const payload = notification.payload ?? {}
  const title = typeof payload.listing_title === 'string' ? payload.listing_title : null

  switch (notification.type) {
    case 'new_match': {
      const count = typeof payload.new_listings_count === 'number' ? payload.new_listings_count : 0
      const updatedCount = typeof payload.updated_listings_count === 'number' ? payload.updated_listings_count : 0
      const description = typeof payload.query_description === 'string' ? payload.query_description : ''
      const parts = [i18n.t('notifications.newCount', { count })]
      if (updatedCount > 0) parts.push(i18n.t('notifications.updated', { count: updatedCount }))
      if (notification.saved_search_deleted) parts.push(i18n.t('notifications.searchDeleted'))
      return `${parts.join(', ')}${description ? ` — ${description}` : ''}`
    }
    case 'price_drop':
      return title
        ? `${title}: ${payload.previous_price ?? '?'} → ${payload.current_price ?? '?'} ${payload.currency ?? ''}`.trim()
        : i18n.t('notifications.priceDrop')
    case 'listing_removed':
      return title ? i18n.t('notifications.noLongerAvailable', { title }) : i18n.t('notifications.removed')
    case 'market_change':
      return typeof payload.description === 'string' ? payload.description : i18n.t('notifications.marketChange')
    default:
      return ''
  }
}
