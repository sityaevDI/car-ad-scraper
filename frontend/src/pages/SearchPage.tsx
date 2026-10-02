import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { useCurrentUser } from '../auth/useCurrentUser'
import { ListingCard } from '../components/ListingCard'
import { Pagination } from '../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { SuccessText } from '../components/AuthCard'
import { ApiError } from '../lib/client'
import type { GroupField, SearchQuery } from '../lib/search'
import { searchApi } from '../lib/search'
import { savedSearchesApi } from '../lib/savedSearches'
import { PAGE_SIZE } from '../search/constants'
import { GroupCard } from '../search/GroupCard'
import type { SearchState, ViewSettings } from '../search/searchUrl'
import {
  DEFAULT_VIEW,
  defaultSort,
  encodeSearchState,
  hasActiveFilters,
  isDefaultView,
  parseSearchParams,
  searchPathForState,
  viewToSaved,
} from '../search/searchUrl'
import { SearchFilters } from '../search/SearchFilters'
import { ViewControls } from '../search/ViewControls'
import { clearViewPreferences, loadViewPreferences, saveViewPreferences } from '../search/viewPreferences'

export function SearchPage() {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const justRegistered = Boolean((location.state as { justRegistered?: boolean } | null)?.justRegistered)
  const { user } = useCurrentUser()

  // The URL is the source of truth for what's being searched. The saved view preference only fills
  // in when the URL doesn't spell out a view; it's re-read on every parse (not once per mount) so
  // a click on the logo ("/") right after changing the grouping still picks up the new choice.
  const searchString = searchParams.toString()
  const state = useMemo(() => parseSearchParams(searchParams, loadViewPreferences()), [searchParams])
  const { query: appliedQuery, groupBy, minGroupCount, sort, page } = state
  const isGrouped = groupBy.length > 0
  const searchPath = searchPathForState(state)

  // Rewrite a partial or hand-edited URL (e.g. a bare "/", which relies on the saved view) into its
  // canonical, fully explicit form, so links taken from it later mean the same thing.
  useEffect(() => {
    const canonical = encodeSearchState(state).toString()
    if (canonical !== searchString) setSearchParams(canonical, { replace: true, state: location.state })
  }, [state, searchString, setSearchParams, location.state])

  const [draftQuery, setDraftQuery] = useState<SearchQuery>(appliedQuery)
  // Re-seed the draft when the applied filters change from outside the form (browser back/forward,
  // a saved-search link, the logo) — but not on view-only changes, which would eat unsubmitted edits.
  const filtersKey = JSON.stringify(appliedQuery)
  const [seededFiltersKey, setSeededFiltersKey] = useState(filtersKey)
  if (seededFiltersKey !== filtersKey) {
    setSeededFiltersKey(filtersKey)
    setDraftQuery(appliedQuery)
  }

  const [saveName, setSaveName] = useState('')
  const [isSavingSearch, setIsSavingSearch] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Pushes a history entry for new results (filters, paging) so Back steps through searches, and
  // replaces for view tweaks (grouping/sort) so toggling a few checkboxes doesn't bury Back.
  function goTo(next: SearchState, { replace }: { replace: boolean }) {
    const params = encodeSearchState(next).toString()
    setSearchParams(params, { replace: replace || params === searchString, state: location.state })
  }

  function changeView(next: Partial<ViewSettings>) {
    const view: ViewSettings = { groupBy, minGroupCount, sort, ...next }
    saveViewPreferences(view)
    goTo({ ...state, ...view, page: 1 }, { replace: true })
  }

  function handleGroupByChange(next: GroupField[]) {
    const wasGrouped = groupBy.length > 0
    const willBeGrouped = next.length > 0
    changeView({
      groupBy: next,
      ...(wasGrouped !== willBeGrouped && { sort: defaultSort(willBeGrouped) }),
    })
  }

  function handleResetView() {
    clearViewPreferences()
    goTo({ ...state, ...DEFAULT_VIEW, page: 1 }, { replace: true })
  }

  function handleResetFilters() {
    setDraftQuery({})
    setSaveSuccess(false)
    goTo({ ...state, query: {}, page: 1 }, { replace: false })
  }

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

  const total = isGrouped ? (query.data?.total_groups ?? 0) : (query.data?.total_listings ?? 0)
  const isEmpty = !query.isLoading && !query.isError && total === 0

  async function handleSaveSearch(event: React.FormEvent) {
    event.preventDefault()
    setSaveError(null)
    setIsSavingSearch(true)
    try {
      await savedSearchesApi.create(saveName, appliedQuery, viewToSaved(state))
      setSaveName('')
      setSaveSuccess(true)
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Не удалось сохранить поиск')
    } finally {
      setIsSavingSearch(false)
    }
  }

  return (
    <div className="space-y-4">
      {justRegistered && (
        <SuccessText>Аккаунт создан. Проверьте почту и подтвердите email, чтобы получить полный доступ.</SuccessText>
      )}

      <SearchFilters
        value={draftQuery}
        onChange={setDraftQuery}
        isSubmitting={query.isFetching}
        canReset={hasActiveFilters(draftQuery) || hasActiveFilters(appliedQuery)}
        onReset={handleResetFilters}
        onSubmit={() => {
          setSaveSuccess(false)
          goTo({ ...state, query: draftQuery, page: 1 }, { replace: false })
        }}
      />

      {user && (
        <form onSubmit={handleSaveSearch} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
          <input
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="Название сохранённого поиска"
            required
            className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={isSavingSearch}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            {isSavingSearch ? 'Сохраняем…' : 'Сохранить поиск с фильтрами и группировкой'}
          </button>
          {saveError && <span className="text-sm text-red-600">{saveError}</span>}
          {saveSuccess && !saveError && <span className="text-sm text-emerald-600">Сохранено ✓</span>}
        </form>
      )}

      <ViewControls
        groupBy={groupBy}
        onGroupByChange={handleGroupByChange}
        sort={sort}
        onSortChange={(next) => changeView({ sort: next })}
        minGroupCount={minGroupCount}
        onMinGroupCountChange={(next) => changeView({ minGroupCount: next })}
        canReset={!isDefaultView(state)}
        onReset={handleResetView}
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
          {/* The URL is part of the key so GroupCard remounts and collapses whenever the filters,
              grouping, sort or page change, instead of staying expanded across unrelated results. */}
          {query.data?.groups?.map((group, i) => (
            <GroupCard
              key={`${searchString}-${i}`}
              group={group}
              baseQuery={appliedQuery}
              groupBy={groupBy}
              from={searchPath}
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {query.data?.listings?.map((listing) => <ListingCard key={listing.id} listing={listing} from={searchPath} />)}
        </div>
      )}

      {!query.isLoading && !query.isError && !isEmpty && (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={(next) => goTo({ ...state, page: next }, { replace: false })}
        />
      )}
    </div>
  )
}
