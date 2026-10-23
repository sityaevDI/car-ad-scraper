import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ListingCard } from '../components/ListingCard'
import { Pagination } from '../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { ApiError } from '../lib/client'
import { formatDate, formatPrice } from '../lib/format'
import { listingsApi, type FollowedListingOut } from '../lib/listings'

const PAGE_SIZE = 20

function PriceChange({ item }: { item: FollowedListingOut }) {
  const { t } = useTranslation()
  const { listing, price_at_follow: priceAtFollow } = item
  if (priceAtFollow === null) return null
  const diff = listing.price - priceAtFollow
  if (diff === 0) return <span className="text-slate-500">{t('following.unchanged')}</span>
  const amount = formatPrice(Math.abs(diff), listing.currency)
  return diff < 0 ? (
    <span className="font-medium text-emerald-700">
      {t('following.dropped', { amount, was: formatPrice(priceAtFollow, listing.currency) })}
    </span>
  ) : (
    <span className="font-medium text-red-700">
      {t('following.rose', { amount, was: formatPrice(priceAtFollow, listing.currency) })}
    </span>
  )
}

export function FollowingPage() {
  const { t } = useTranslation()
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
      setActionError(err instanceof ApiError ? err.message : t('following.unfollowFailed'))
    } finally {
      setPendingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{t('following.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">
          {t('following.intro')}
        </p>
      </div>

      {actionError && <p className="text-sm text-red-600">{actionError}</p>}

      {query.isLoading && <LoadingState />}
      {query.isError && (
        <ErrorState
          message={query.error instanceof ApiError ? query.error.message : t('following.loadFailed')}
          onRetry={() => query.refetch()}
        />
      )}
      {query.isSuccess && query.data.items.length === 0 && (
        <EmptyState message={t('following.empty')} />
      )}

      {query.isSuccess && query.data.items.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {query.data.items.map((item) => (
              <div key={item.listing.id} className="space-y-1.5">
                <ListingCard listing={item.listing} />
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1 text-xs">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="text-slate-500">{t('following.since', { date: formatDate(item.followed_at) })}</span>
                    <PriceChange item={item} />
                  </div>
                  <button
                    type="button"
                    disabled={pendingId === item.listing.id}
                    onClick={() => handleUnfollow(item.listing.id)}
                    className="rounded-md border border-slate-300 px-2 py-1 font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                  >
                    {t('following.unfollow')}
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
