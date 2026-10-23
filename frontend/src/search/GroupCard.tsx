import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ListingCard } from '../components/ListingCard'
import { Pagination } from '../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { formatMileage, formatPrice } from '../lib/format'
import { ApiError } from '../lib/client'
import type { GroupField, ListingGroupOut, SearchQuery } from '../lib/search'
import { FLAT_SORT_OPTIONS, searchApi, sortLabel } from '../lib/search'
import { DRILL_DOWN_PAGE_SIZE } from './constants'
import { buildDrillDownQuery } from './drillDown'

export function GroupCard({
  group,
  baseQuery,
  groupBy,
  from,
}: {
  group: ListingGroupOut
  baseQuery: SearchQuery
  groupBy: GroupField[]
  from: string
}) {
  const { t } = useTranslation()
  const [isExpanded, setIsExpanded] = useState(false)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState('first_seen_desc')

  const drillDownQuery = buildDrillDownQuery(baseQuery, groupBy, group.group)

  const query = useQuery({
    queryKey: ['search', 'drilldown', drillDownQuery, sort, page],
    queryFn: () =>
      searchApi.search({
        query: drillDownQuery,
        group_by: null,
        sort,
        page,
        page_size: DRILL_DOWN_PAGE_SIZE,
      }),
    enabled: isExpanded,
    placeholderData: keepPreviousData,
  })

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{group.label}</h3>
          <p className="mt-0.5 text-xs text-slate-500">{t('search.listingsCount', { count: group.count })}</p>
        </div>
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="shrink-0 rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
        >
          {isExpanded ? t('search.hide') : t('search.show')}
        </button>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-600">
        <div>
          <dt className="text-slate-400">{t('search.price')}</dt>
          <dd>
            {formatPrice(group.price_min, group.currency)} – {formatPrice(group.price_max, group.currency)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">{t('search.year')}</dt>
          <dd>
            {group.year_min} – {group.year_max}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">{t('search.mileage')}</dt>
          <dd>
            {formatMileage(group.mileage_min)} – {formatMileage(group.mileage_max)}
          </dd>
        </div>
      </dl>

      {isExpanded && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <div className="mb-3 flex justify-end">
            <label className="flex items-center gap-1.5 text-xs text-slate-700">
              {t('search.sortLabel')}
              <select
                className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                value={sort}
                onChange={(e) => {
                  setSort(e.target.value)
                  setPage(1)
                }}
              >
                {FLAT_SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {sortLabel(option.value)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {query.isLoading ? (
            <LoadingState />
          ) : query.isError ? (
            <ErrorState
              message={query.error instanceof ApiError ? query.error.message : t('search.loadListingsFailed')}
              onRetry={() => query.refetch()}
            />
          ) : !query.data?.listings || query.data.listings.length === 0 ? (
            <EmptyState message={t('search.groupEmpty')} />
          ) : (
            <>
              <div className="space-y-3">
                {query.data.listings.map((listing) => (
                  <ListingCard key={listing.id} listing={listing} from={from} />
                ))}
              </div>
              <Pagination page={page} pageSize={DRILL_DOWN_PAGE_SIZE} total={query.data.total_listings} onPageChange={setPage} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
