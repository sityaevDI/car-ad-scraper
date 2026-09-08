import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ListingCard } from '../components/ListingCard'
import { Pagination } from '../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { SuccessText } from '../components/AuthCard'
import { ApiError } from '../lib/client'
import type { GroupField, SearchQuery } from '../lib/search'
import { DEFAULT_GROUP_BY, searchApi } from '../lib/search'
import { PAGE_SIZE } from '../search/constants'
import { GroupCard } from '../search/GroupCard'
import { SearchFilters } from '../search/SearchFilters'
import { ViewControls } from '../search/ViewControls'

export function SearchPage() {
  const location = useLocation()
  const justRegistered = Boolean((location.state as { justRegistered?: boolean } | null)?.justRegistered)

  const [draftQuery, setDraftQuery] = useState<SearchQuery>({})
  const [appliedQuery, setAppliedQuery] = useState<SearchQuery>({})
  const [groupBy, setGroupBy] = useState<GroupField[]>(DEFAULT_GROUP_BY)
  const [minGroupCount, setMinGroupCount] = useState<number | null>(null)
  const [sort, setSort] = useState('count_desc')
  const [page, setPage] = useState(1)

  const isGrouped = groupBy.length > 0

  const query = useQuery({
    queryKey: ['search', appliedQuery, groupBy, minGroupCount, sort, page],
    queryFn: () =>
      searchApi.search({
        query: appliedQuery,
        group_by: isGrouped ? groupBy : null,
        min_group_count: isGrouped ? minGroupCount : null,
        sort,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })

  function handleGroupByChange(next: GroupField[]) {
    const wasGrouped = groupBy.length > 0
    const willBeGrouped = next.length > 0
    setGroupBy(next)
    setPage(1)
    if (wasGrouped !== willBeGrouped) {
      setSort(willBeGrouped ? 'count_desc' : 'first_seen_desc')
    }
  }

  const total = isGrouped ? (query.data?.total_groups ?? 0) : (query.data?.total_listings ?? 0)
  const isEmpty = !query.isLoading && !query.isError && total === 0

  return (
    <div className="space-y-4">
      {justRegistered && (
        <SuccessText>Аккаунт создан. Проверьте почту и подтвердите email, чтобы получить полный доступ.</SuccessText>
      )}

      <SearchFilters
        value={draftQuery}
        onChange={setDraftQuery}
        isSubmitting={query.isFetching}
        onSubmit={() => {
          setAppliedQuery(draftQuery)
          setPage(1)
        }}
      />

      <ViewControls
        groupBy={groupBy}
        onGroupByChange={handleGroupByChange}
        sort={sort}
        onSortChange={(next) => {
          setSort(next)
          setPage(1)
        }}
        minGroupCount={minGroupCount}
        onMinGroupCountChange={(next) => {
          setMinGroupCount(next)
          setPage(1)
        }}
      />

      {query.isLoading ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          message={query.error instanceof ApiError ? query.error.message : 'Не удалось загрузить результаты'}
          onRetry={() => query.refetch()}
        />
      ) : isEmpty ? (
        <EmptyState message="Ничего не найдено — попробуйте ослабить фильтры" />
      ) : isGrouped ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {query.data?.groups?.map((group, i) => (
            <GroupCard key={i} group={group} baseQuery={appliedQuery} groupBy={groupBy} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {query.data?.listings?.map((listing) => <ListingCard key={listing.id} listing={listing} />)}
        </div>
      )}

      {!query.isLoading && !query.isError && !isEmpty && (
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      )}
    </div>
  )
}
