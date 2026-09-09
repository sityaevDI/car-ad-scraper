import type { NotificationOut } from '../lib/notifications'

const TYPE_LABELS: Record<NotificationOut['type'], string> = {
  new_match: 'Новое совпадение',
  price_drop: 'Цена снижена',
  listing_removed: 'Объявление снято',
  market_change: 'Изменение рынка',
}

export function notificationTitle(notification: NotificationOut): string {
  return TYPE_LABELS[notification.type] ?? notification.type
}

export function notificationDescription(notification: NotificationOut): string {
  const payload = notification.payload ?? {}
  const title = typeof payload.listing_title === 'string' ? payload.listing_title : null

  switch (notification.type) {
    case 'new_match':
      return title ? `${title} — ${payload.listing_price ?? ''} ${payload.currency ?? ''}`.trim() : 'Новое объявление'
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
