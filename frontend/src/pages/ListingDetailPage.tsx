import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useCurrentUser } from '../auth/useCurrentUser'
import { ErrorState } from '../components/StateMessage'
import { StatusBadge } from '../components/StatusBadge'
import { ApiError } from '../lib/client'
import { formatDate, formatMileage, formatPrice } from '../lib/format'
import { listingsApi } from '../lib/listings'
import { BODY_TYPE_OPTIONS, FUEL_TYPE_OPTIONS, TRANSMISSION_OPTIONS } from '../search/constants'

const TAG_LABELS = new Map<string, string>(
  [...FUEL_TYPE_OPTIONS, ...TRANSMISSION_OPTIONS, ...BODY_TYPE_OPTIONS].map((o) => [o.value, o.label]),
)

function tag(value: string | null): string {
  if (!value) return '—'
  return TAG_LABELS.get(value) ?? value
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="text-sm text-slate-800">{value}</dd>
    </div>
  )
}

export function ListingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useCurrentUser()
  const [isTogglingFollow, setIsTogglingFollow] = useState(false)

  const query = useQuery({
    queryKey: ['listing-history', id],
    queryFn: () => listingsApi.getHistory(id!),
    enabled: Boolean(id),
  })

  async function handleToggleFollow() {
    if (!id || !query.data) return
    setIsTogglingFollow(true)
    try {
      if (query.data.listing.is_following) {
        await listingsApi.unfollow(id)
      } else {
        await listingsApi.follow(id)
      }
      await query.refetch()
    } finally {
      setIsTogglingFollow(false)
    }
  }

  if (query.isLoading) {
    return <div className="h-96 animate-pulse rounded-lg border border-slate-200 bg-slate-100" />
  }

  if (query.isError) {
    return (
      <ErrorState
        message={
          query.error instanceof ApiError && query.error.status === 404
            ? 'Объявление не найдено'
            : query.error instanceof ApiError
              ? query.error.message
              : 'Не удалось загрузить объявление'
        }
        onRetry={() => query.refetch()}
      />
    )
  }

  const { listing, snapshots } = query.data!
  const sortedSnapshots = [...snapshots].sort(
    (a, b) => new Date(b.captured_at).getTime() - new Date(a.captured_at).getTime(),
  )

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm font-medium text-slate-600 hover:underline">
        ← К поиску
      </Link>

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-5 sm:flex-row">
          <div className="h-56 w-full shrink-0 overflow-hidden rounded-md bg-slate-100 sm:w-72">
            {listing.image_url ? (
              <img src={listing.image_url} alt={listing.title} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-sm text-slate-400">Нет фото</div>
            )}
          </div>

          <div className="flex-1">
            <div className="flex items-start justify-between gap-3">
              <h1 className="text-lg font-semibold text-slate-900">{listing.title}</h1>
              <div className="flex shrink-0 items-center gap-2">
                <StatusBadge status={listing.status} />
                {user && (
                  <button
                    type="button"
                    onClick={handleToggleFollow}
                    disabled={isTogglingFollow}
                    className={
                      listing.is_following
                        ? 'rounded-md border border-slate-300 bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50'
                        : 'rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50'
                    }
                  >
                    {listing.is_following ? 'Отслеживается ✓' : 'Отслеживать цену'}
                  </button>
                )}
              </div>
            </div>
            <p className="mt-1 text-2xl font-bold text-slate-900">{formatPrice(listing.price, listing.currency)}</p>

            <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
              <Field label="Марка" value={listing.make} />
              <Field label="Модель" value={listing.model} />
              <Field label="Год" value={String(listing.production_year)} />
              <Field label="Пробег" value={formatMileage(listing.mileage_km)} />
              <Field label="Топливо" value={tag(listing.fuel_type)} />
              <Field label="КПП" value={tag(listing.transmission)} />
              <Field label="Кузов" value={tag(listing.body_type)} />
              <Field label="Объём двигателя" value={listing.engine_volume_cc ? `${listing.engine_volume_cc} см³` : '—'} />
              <Field label="Мощность" value={listing.power_hp ? `${listing.power_hp} л.с.` : '—'} />
              <Field label="Локация" value={listing.location ?? '—'} />
              <Field label="Впервые замечено" value={formatDate(listing.first_seen_at)} />
              <Field label="Последнее обновление" value={formatDate(listing.last_checked_at)} />
            </dl>

            <a
              href={listing.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-block text-sm font-medium text-slate-700 hover:underline"
            >
              Открыть на источнике ↗
            </a>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">История изменений</h2>
        {sortedSnapshots.length === 0 ? (
          <p className="text-sm text-slate-500">Изменений пока не зафиксировано.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs text-slate-400">
                  <th className="py-1.5 pr-4 font-medium">Дата</th>
                  <th className="py-1.5 pr-4 font-medium">Цена</th>
                  <th className="py-1.5 pr-4 font-medium">Пробег</th>
                  <th className="py-1.5 font-medium">Заголовок</th>
                </tr>
              </thead>
              <tbody>
                {sortedSnapshots.map((snapshot) => (
                  <tr key={snapshot.id} className="border-b border-slate-100 last:border-0">
                    <td className="py-1.5 pr-4 text-slate-600">{formatDate(snapshot.captured_at)}</td>
                    <td className="py-1.5 pr-4 text-slate-800">{formatPrice(snapshot.price, listing.currency)}</td>
                    <td className="py-1.5 pr-4 text-slate-600">{formatMileage(snapshot.mileage_km)}</td>
                    <td className="py-1.5 truncate text-slate-600">{snapshot.title}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
