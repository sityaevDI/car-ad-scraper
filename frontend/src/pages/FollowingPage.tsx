import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ListingCard } from '../components/ListingCard'
import { Pagination } from '../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { ApiError } from '../lib/client'
import { formatDate, formatPrice } from '../lib/format'
import { listingsApi, type FollowedListingOut } from '../lib/listings'

const PAGE_SIZE = 20

function PriceChange({ item }: { item: FollowedListingOut }) {
  const { listing, price_at_follow: priceAtFollow } = item
  if (priceAtFollow === null) return null
  const diff = listing.price - priceAtFollow
  if (diff === 0) return <span className="text-slate-500">цена не менялась</span>
  const amount = formatPrice(Math.abs(diff), listing.currency)
  return diff < 0 ? (
    <span className="font-medium text-emerald-700">
      ↓ подешевело на {amount} (было {formatPrice(priceAtFollow, listing.currency)})
    </span>
  ) : (
    <span className="font-medium text-red-700">
      ↑ подорожало на {amount} (было {formatPrice(priceAtFollow, listing.currency)})
    </span>
  )
}

export function FollowingPage() {
  const [page, setPage] = useState(1)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['following', page],
    queryFn: () => listingsApi.listFollowing(page, PAGE_SIZE),
  })

  async function handleUnfollow(listingId: string) {
    setPendingId(listingId)
    setActionError(null)
    try {
      await listingsApi.unfollow(listingId)
      // Removing the last item of a page other than the first would otherwise leave an empty page.
      if (page > 1 && query.data?.items.length === 1) {
        setPage(page - 1)
      } else {
        await query.refetch()
      }
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Не удалось убрать объявление из отслеживаемых')
    } finally {
      setPendingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Отслеживаемые объявления</h1>
        <p className="mt-1 text-sm text-slate-600">
          Когда цена отслеживаемого объявления снижается, приходит уведомление. Снятые с публикации объявления
          остаются в списке, пока вы не уберёте их сами.
        </p>
      </div>

      {actionError && <p className="text-sm text-red-600">{actionError}</p>}

      {query.isLoading && <LoadingState />}
      {query.isError && (
        <ErrorState
          message={query.error instanceof ApiError ? query.error.message : 'Не удалось загрузить отслеживаемые объявления'}
          onRetry={() => query.refetch()}
        />
      )}
      {query.isSuccess && query.data.items.length === 0 && (
        <EmptyState message="Пока нет отслеживаемых объявлений — нажмите «Отслеживать цену» на странице объявления." />
      )}

      {query.isSuccess && query.data.items.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {query.data.items.map((item) => (
              <div key={item.listing.id} className="space-y-1.5">
                <ListingCard listing={item.listing} />
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1 text-xs">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="text-slate-500">с {formatDate(item.followed_at)}</span>
                    <PriceChange item={item} />
                  </div>
                  <button
                    type="button"
                    disabled={pendingId === item.listing.id}
                    onClick={() => handleUnfollow(item.listing.id)}
                    className="rounded-md border border-slate-300 px-2 py-1 font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                  >
                    Перестать отслеживать
                  </button>
                </div>
              </div>
            ))}
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPageChange={setPage} />
        </>
      )}
    </div>
  )
}
