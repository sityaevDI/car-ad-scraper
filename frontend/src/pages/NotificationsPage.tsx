import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { formatDate } from '../lib/format'
import type { NotificationOut } from '../lib/notifications'
import { notificationsApi } from '../lib/notifications'
import { groupNotificationsByDate, notificationDescription, notificationTitle } from '../notifications/format'

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

  async function handleRead(id: string) {
    await notificationsApi.markRead(id)
    await query.refetch()
  }

  async function handleDelete(id: string) {
    await notificationsApi.remove(id)
    await query.refetch()
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Уведомления</h1>

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
                const content = (
                  <div className="flex items-start justify-between gap-3 px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{notificationTitle(notification)}</p>
                      <p className="mt-0.5 text-sm text-slate-600">{notificationDescription(notification)}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatDate(notification.created_at)}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {!notification.read_at && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault()
                            handleRead(notification.id)
                          }}
                          className="rounded-full bg-slate-900 px-2 py-0.5 text-xs font-medium text-white hover:bg-slate-700"
                        >
                          Прочитано
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault()
                          handleDelete(notification.id)
                        }}
                        aria-label="Удалить уведомление"
                        title="Удалить"
                        className="rounded-full border border-slate-200 px-2 py-0.5 text-xs font-medium text-slate-500 hover:border-red-300 hover:bg-red-50 hover:text-red-600"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                )
                const linkTo = notificationLinkTo(notification)
                return linkTo ? (
                  <Link
                    key={notification.id}
                    to={linkTo}
                    className={notification.read_at ? 'block hover:bg-slate-50' : 'block bg-slate-50 hover:bg-slate-100'}
                  >
                    {content}
                  </Link>
                ) : (
                  <div key={notification.id} className={notification.read_at ? '' : 'bg-slate-50'}>
                    {content}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
    </div>
  )
}
