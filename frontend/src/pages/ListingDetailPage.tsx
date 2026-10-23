import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useCurrentUser } from '../auth/useCurrentUser'
import { ErrorState } from '../components/StateMessage'
import { StatusBadge } from '../components/StatusBadge'
import { optionLabel, type OptionGroup } from '../i18n'
import { ApiError } from '../lib/client'
import { formatDate, formatMileage, formatPrice } from '../lib/format'
import { listingsApi, type MarketComparisonOut } from '../lib/listings'
import { PriceScoreBadge } from '../components/PriceScoreBadge'
import { parseBackTarget } from '../search/searchUrl'

function tag(group: OptionGroup, value: string | null): string {
  return value ? optionLabel(group, value) : '—'
}

// Deviation scale spans ±30% around the market reference price; deviation_pct beyond that just
// pins to the edge. The zone coloring is a fixed visual gradient, not a literal readout of the
// admin-configurable deviation_market_band_pct/deviation_significant_band_pct thresholds (the
// frontend doesn't know those values) — the badge above the scale carries the actual `label`
// computed server-side against those thresholds.
const DEVIATION_SCALE_RANGE_PCT = 30

function PriceDeviationScale({ deviationPct }: { deviationPct: number }) {
  const { t } = useTranslation()
  const clamped = Math.max(-DEVIATION_SCALE_RANGE_PCT, Math.min(DEVIATION_SCALE_RANGE_PCT, deviationPct))
  const position = ((clamped + DEVIATION_SCALE_RANGE_PCT) / (2 * DEVIATION_SCALE_RANGE_PCT)) * 100

  return (
    <div>
      <div className="relative h-2 rounded-full">
        <div className="flex h-full w-full overflow-hidden rounded-full">
          <div className="w-1/5 bg-emerald-500" />
          <div className="w-1/5 bg-emerald-300" />
          <div className="w-1/5 bg-slate-300" />
          <div className="w-1/5 bg-amber-300" />
          <div className="w-1/5 bg-rose-500" />
        </div>
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-slate-900 shadow"
          style={{ left: `${position}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-400">
        <span>{t('listing.belowMarket')}</span>
        <span>{t('listing.market')}</span>
        <span>{t('listing.aboveMarket')}</span>
      </div>
    </div>
  )
}

function MarketComparisonSection({
  isLoading,
  comparison,
  currency,
}: {
  isLoading: boolean
  comparison: MarketComparisonOut | undefined
  currency: string
}) {
  const { t } = useTranslation()
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold text-slate-900">{t('listing.marketEstimate')}</h2>
      {isLoading ? (
        <div className="h-16 animate-pulse rounded-md bg-slate-100" />
      ) : !comparison?.market ? (
        <p className="text-sm text-slate-500">{t('listing.estimating')}</p>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs text-slate-400">{t('listing.estimatedPrice')}</p>
              <p className="text-lg font-semibold text-slate-900">
                {comparison.market.estimated_price !== null
                  ? formatPrice(comparison.market.estimated_price, currency)
                  : '—'}
              </p>
              {comparison.market.price_low !== null && comparison.market.price_high !== null && (
                <p className="text-xs text-slate-500">
                  {formatPrice(comparison.market.price_low, currency)} – {formatPrice(comparison.market.price_high, currency)}
                </p>
              )}
            </div>
            {comparison.price_score && <PriceScoreBadge priceScore={comparison.price_score} />}
          </div>

          {comparison.price_score && (
            <div>
              <PriceDeviationScale deviationPct={comparison.price_score.deviation_pct} />
              <p className="mt-1.5 text-xs text-slate-500">
                {t(comparison.price_score.deviation_pct >= 0 ? 'listing.deviationAbove' : 'listing.deviationBelow', {
                  pct: Math.abs(comparison.price_score.deviation_pct).toFixed(1),
                })}
              </p>
            </div>
          )}

          <p className="text-xs text-slate-400">
            {t('listing.confidenceLine', {
              confidence: t(`listing.confidence.${comparison.market.confidence}`),
              count: comparison.market.comparable_listings_count,
            })}
          </p>
        </div>
      )}
    </div>
  )
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
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user } = useCurrentUser()
  const [isTogglingFollow, setIsTogglingFollow] = useState(false)

  // The exact search this listing was opened from (see ListingCard). It arrives as `?from=` so it
  // survives being opened in a new tab, then is moved into this history entry's state and out of
  // the address bar — the state outlives a reload, the long encoded URL needn't. Opened from
  // anywhere else (notification, pasted link) there's no `from`, and "К поиску" is a plain "/".
  const fromParam = parseBackTarget(searchParams.get('from'))
  const fromState = parseBackTarget((location.state as { from?: string } | null)?.from ?? null)
  const backToSearch = fromParam ?? fromState ?? '/'

  const hasFromParam = searchParams.has('from')
  useEffect(() => {
    if (!hasFromParam) return
    const rest = new URLSearchParams(searchParams)
    rest.delete('from')
    navigate(
      { pathname: location.pathname, search: rest.size > 0 ? `?${rest}` : '' },
      { replace: true, state: fromParam ? { from: fromParam } : location.state },
    )
  }, [hasFromParam, searchParams, fromParam, location.pathname, location.state, navigate])

  const query = useQuery({
    queryKey: ['listing-history', id],
    queryFn: () => listingsApi.getHistory(id!),
    enabled: Boolean(id),
  })

  const marketQuery = useQuery({
    queryKey: ['listing-market-comparison', id],
    queryFn: () => listingsApi.getMarketComparison(id!),
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
            ? t('listing.notFound')
            : query.error instanceof ApiError
              ? query.error.message
              : t('listing.loadFailed')
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
      <Link to={backToSearch} className="text-sm font-medium text-slate-600 hover:underline">
        {t('listing.backToSearch')}
      </Link>

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-5 sm:flex-row">
          <div className="h-56 w-full shrink-0 overflow-hidden rounded-md bg-slate-100 sm:w-72">
            {listing.image_url ? (
              <img src={listing.image_url} alt={listing.title} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-sm text-slate-400">{t('common.noPhoto')}</div>
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
                    {listing.is_following ? t('listing.following') : t('listing.follow')}
                  </button>
                )}
              </div>
            </div>
            <p className="mt-1 text-2xl font-bold text-slate-900">{formatPrice(listing.price, listing.currency)}</p>

            <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
              <Field label={t('listing.make')} value={listing.make} />
              <Field label={t('listing.model')} value={listing.model} />
              <Field label={t('listing.year')} value={String(listing.production_year)} />
              <Field label={t('listing.mileage')} value={formatMileage(listing.mileage_km)} />
              <Field label={t('listing.fuel')} value={tag('fuel_type', listing.fuel_type)} />
              <Field label={t('listing.transmission')} value={tag('transmission', listing.transmission)} />
              <Field label={t('listing.body')} value={tag('body_type', listing.body_type)} />
              <Field label={t('listing.interior')} value={tag('interior_material', listing.interior_material)} />
              <Field label={t('listing.airCondition')} value={tag('air_condition', listing.air_condition)} />
              <Field label={t('listing.drive')} value={tag('drive_type', listing.drive_type)} />
              <Field label={t('listing.engineVolume')} value={listing.engine_volume_cc ? t('listing.ccUnit', { value: listing.engine_volume_cc }) : '—'} />
              <Field label={t('listing.power')} value={listing.power_hp ? t('listing.hpUnit', { value: listing.power_hp }) : '—'} />
              <Field label={t('listing.seats')} value={listing.seats ?? '—'} />
              <Field label={t('listing.location')} value={listing.location ?? '—'} />
              <Field label={t('listing.firstSeen')} value={formatDate(listing.first_seen_at)} />
              <Field label={t('listing.lastUpdated')} value={formatDate(listing.last_checked_at)} />
            </dl>

            <a
              href={listing.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-block text-sm font-medium text-slate-700 hover:underline"
            >
              {t('listing.openSource')}
            </a>
          </div>
        </div>
      </div>

      <MarketComparisonSection
        isLoading={marketQuery.isLoading}
        comparison={marketQuery.data}
        currency={listing.currency}
      />

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">{t('listing.history')}</h2>
        {sortedSnapshots.length === 0 ? (
          <p className="text-sm text-slate-500">{t('listing.noHistory')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs text-slate-400">
                  <th className="py-1.5 pr-4 font-medium">{t('listing.date')}</th>
                  <th className="py-1.5 pr-4 font-medium">{t('listing.price')}</th>
                  <th className="py-1.5 pr-4 font-medium">{t('listing.mileage')}</th>
                  <th className="py-1.5 font-medium">{t('listing.title')}</th>
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
