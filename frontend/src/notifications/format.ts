import type { NotificationOut } from '../lib/notifications'

const TYPE_LABELS: Record<NotificationOut['type'], string> = {
  new_match: 'Новые объявления',
  price_drop: 'Цена снижена',
  listing_removed: 'Объявление снято',
  market_change: 'Изменение рынка',
}

// Mirrors app/notifications/delivery.py::_new_listings_phrase.
function pluralizeListings(count: number): string {
  if (count % 10 === 1 && count % 100 !== 11) return 'объявление'
  if (count % 10 >= 2 && count % 10 <= 4 && !(count % 100 >= 12 && count % 100 <= 14)) return 'объявления'
  return 'объявлений'
}

export function notificationTitle(notification: NotificationOut): string {
  if (notification.type === 'new_match') {
    const payload = notification.payload ?? {}
    const name = typeof payload.saved_search_name === 'string' ? payload.saved_search_name : null
    return name ? `«${name}»` : TYPE_LABELS.new_match
  }
  return TYPE_LABELS[notification.type] ?? notification.type
}

export function notificationDescription(notification: NotificationOut): string {
  const payload = notification.payload ?? {}
  const title = typeof payload.listing_title === 'string' ? payload.listing_title : null

  switch (notification.type) {
    case 'new_match': {
      const count = typeof payload.new_listings_count === 'number' ? payload.new_listings_count : 0
      const description = typeof payload.query_description === 'string' ? payload.query_description : ''
      return `${count} ${pluralizeListings(count)}${description ? ` — ${description}` : ''}`
    }
    case 'price_drop':
      return title
        ? `${title}: ${payload.previous_price ?? '?'} → ${payload.current_price ?? '?'} ${payload.currency ?? ''}`.trim()
        : 'Цена снижена'
    case 'listing_removed':
      return title ? `${title} больше не доступно` : 'Объявление снято с публикации'
    case 'market_change':
      return typeof payload.description === 'string' ? payload.description : 'Изменение на рынке'
    default:
      return ''
  }
}
