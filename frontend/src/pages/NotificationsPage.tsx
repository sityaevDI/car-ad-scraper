import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { formatDate } from '../lib/format'
import { notificationsApi } from '../lib/notifications'
import { notificationDescription, notificationTitle } from '../notifications/format'

export function NotificationsPage() {
  const query = useQuery({ queryKey: ['notifications'], queryFn: notificationsApi.list })

  async function handleRead(id: string) {
    await notificationsApi.markRead(id)
    await query.refetch()
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Уведомления</h1>

      {query.isLoading && <LoadingState />}
      {query.isError && <ErrorState message="Не удалось загрузить уведомления" onRetry={() => query.refetch()} />}
      {query.isSuccess && query.data.notifications.length === 0 && <EmptyState message="Уведомлений пока нет" />}

      {query.isSuccess && query.data.notifications.length > 0 && (
        <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
          {query.data.notifications.map((notification) => {
            const content = (
              <div className="flex items-start justify-between gap-3 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">{notificationTitle(notification)}</p>
                  <p className="mt-0.5 text-sm text-slate-600">{notificationDescription(notification)}</p>
                  <p className="mt-1 text-xs text-slate-400">{formatDate(notification.created_at)}</p>
                </div>
                {!notification.read_at && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault()
                      handleRead(notification.id)
                    }}
                    className="shrink-0 rounded-full bg-slate-900 px-2 py-0.5 text-xs font-medium text-white hover:bg-slate-700"
                  >
                    Прочитано
                  </button>
                )}
              </div>
            )
            return notification.listing_id ? (
              <Link
                key={notification.id}
                to={`/listings/${notification.listing_id}`}
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
      )}
    </div>
  )
}
