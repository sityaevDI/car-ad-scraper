import { apiFetch } from './client'

export type NotificationType = 'new_match' | 'price_drop' | 'listing_removed' | 'market_change'

export interface NotificationOut {
  id: string
  type: NotificationType
  listing_id: string | null
  payload: Record<string, unknown> | null
  read_at: string | null
  created_at: string
}

export interface NotificationListOut {
  notifications: NotificationOut[]
  unread_count: number
}

export const notificationsApi = {
  list: () => apiFetch<NotificationListOut>('/api/v1/me/notifications'),
  markRead: (id: string) => apiFetch<NotificationOut>(`/api/v1/me/notifications/${id}/read`, { method: 'POST' }),
}
