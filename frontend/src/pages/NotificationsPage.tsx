import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { ApiError } from '../lib/client'
import { formatDate, formatPrice } from '../lib/format'
import type { NotificationOut } from '../lib/notifications'
import { notificationsApi } from '../lib/notifications'
import {
  groupNotificationsByDate,
  notificationDescription,
  notificationNewListingsCount,
  notificationNewListingsPreview,
  notificationTitle,
} from '../notifications/format'

function notificationLinkTo(notification: NotificationOut): string | null {
  if (notification.listing_id) return `/listings/${notification.listing_id}`
  if (
    notification.type === 'new_match' &&
    !notification.saved_search_deleted &&
    typeof notification.payload?.saved_search_id === 'string'
  ) {
    return `/saved-searches/${notification.payload.saved_search_id}`
  }
  return null
}

export function NotificationsPage() {
  const query = useQuery({ queryKey: ['notifications'], queryFn: notificationsApi.list })
  // Tracks the notification currently being read/deleted so its buttons can be disabled — without
  // this, a slow request let a user fire the same delete several times before the list refetched.
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  async function handleRead(id: string) {
    setPendingId(id)
    setActionError(null)
    try {
      await notificationsApi.markRead(id)
      await query.refetch()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Не удалось отметить уведомление прочитанным')
    } finally {
      setPendingId(null)
    }
  }

  async function handleDelete(id: string) {
    setPendingId(id)
    setActionError(null)
    try {
      await notificationsApi.remove(id)
      await query.refetch()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Не удалось удалить уведомление')
    } finally {
      setPendingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Уведомления</h1>

      {actionError && <p className="text-sm text-red-600">{actionError}</p>}

      {query.isLoading && <LoadingState />}
      {query.isError && <ErrorState message="Не удалось загрузить уведомления" onRetry={() => query.refetch()} />}
      {query.isSuccess && query.data.notifications.length === 0 && <EmptyState message="Уведомлений пока нет" />}

      {query.isSuccess &&
        query.data.notifications.length > 0 &&
        groupNotificationsByDate(query.data.notifications).map((group) => (
          <div key={group.label} className="space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{group.label}</h2>
            <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {group.items.map((notification) => {
                const linkTo = notificationLinkTo(notification)
                const isPending = pendingId === notification.id
                const newListings = notificationNewListingsPreview(notification)
                const newListingsTotal = notificationNewListingsCount(notification)
                const textBlock = (
                  <>
                    <p className="text-sm font-medium text-slate-900">{notificationTitle(notification)}</p>
                    <p className="mt-0.5 text-sm text-slate-600">{notificationDescription(notification)}</p>
                    <p className="mt-1 text-xs text-slate-400">{formatDate(notification.created_at)}</p>
                  </>
                )
                return (
                  <div key={notification.id} className={notification.read_at ? '' : 'bg-slate-50'}>
                    <div className="flex items-start justify-between gap-3 px-4 py-3">
                      {linkTo ? (
                        <Link to={linkTo} className="min-w-0 flex-1 hover:underline">
                          {textBlock}
                        </Link>
                      ) : (
                        <div className="min-w-0 flex-1">{textBlock}</div>
                      )}
                      <div className="flex shrink-0 items-center gap-2">
                        {!notification.read_at && (
                          <button
                            type="button"
                            disabled={isPending}
                            onClick={() => handleRead(notification.id)}
                            className="rounded-full bg-slate-900 px-2 py-0.5 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                          >
                            Прочитано
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={isPending}
                          onClick={() => handleDelete(notification.id)}
                          aria-label="Удалить уведомление"
                          title="Удалить"
                          className="rounded-full border border-slate-200 px-2 py-0.5 text-xs font-medium text-slate-500 hover:border-red-300 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                    {/* Which specific listings are behind the count above — otherwise a grouped
                        NEW_MATCH notification gives no way to tell what actually changed. */}
                    {newListings.length > 0 && (
                      <ul className="space-y-1 border-t border-slate-100 px-4 py-2 pl-6">
                        {newListings.map((item) => (
                          <li key={item.id} className="list-disc text-xs text-slate-600">
                            <Link to={`/listings/${item.id}`} className="hover:text-slate-900 hover:underline">
                              {item.title} — {formatPrice(item.price, item.currency)}
                            </Link>
                          </li>
                        ))}
                        {newListingsTotal > newListings.length && (
                          <li className="list-disc text-xs text-slate-400">
                            и ещё {newListingsTotal - newListings.length}
                          </li>
                        )}
                      </ul>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
    </div>
  )
}
