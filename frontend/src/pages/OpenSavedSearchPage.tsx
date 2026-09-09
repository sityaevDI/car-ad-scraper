import { useQuery } from '@tanstack/react-query'
import { Navigate, useParams } from 'react-router-dom'
import { ErrorState } from '../components/StateMessage'
import { ApiError } from '../lib/client'
import { savedSearchesApi } from '../lib/savedSearches'

// Landing point for the "N new listings" email link (app/notifications/delivery.py) — loads the
// saved search then hands its query off to SearchPage via router state, same as the "Открыть в
// поиске" link on SavedSearchesPage.
export function OpenSavedSearchPage() {
  const { id } = useParams<{ id: string }>()

  const query = useQuery({
    queryKey: ['saved-search', id],
    queryFn: () => savedSearchesApi.get(id!),
    enabled: Boolean(id),
  })

  if (query.isLoading) {
    return <div className="h-40 animate-pulse rounded-lg border border-slate-200 bg-slate-100" />
  }

  if (query.isError) {
    return (
      <ErrorState
        message={
          query.error instanceof ApiError && query.error.status === 404
            ? 'Сохранённый поиск не найден'
            : 'Не удалось открыть сохранённый поиск'
        }
        onRetry={() => query.refetch()}
      />
    )
  }

  return <Navigate to="/" state={{ savedQuery: query.data!.query }} replace />
}
