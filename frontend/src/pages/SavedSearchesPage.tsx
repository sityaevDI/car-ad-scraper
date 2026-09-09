import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../lib/client'
import { formatDate } from '../lib/format'
import type { SearchQuery } from '../lib/search'
import { savedSearchesApi } from '../lib/savedSearches'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'

function describeQuery(query: SearchQuery): string {
  const parts: string[] = []
  if (query.make) parts.push(String(query.make))
  if (Array.isArray(query.models) && query.models.length) parts.push((query.models as string[]).join('/'))
  if (query.year_min || query.year_max) parts.push(`${query.year_min ?? '…'}–${query.year_max ?? '…'}`)
  if (query.price_min || query.price_max) parts.push(`€${query.price_min ?? '…'}–${query.price_max ?? '…'}`)
  return parts.length ? parts.join(', ') : 'Все объявления'
}

export function SavedSearchesPage() {
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const query = useQuery({ queryKey: ['saved-searches'], queryFn: savedSearchesApi.list })

  async function handleToggle(id: string, enabled: boolean) {
    setPendingId(id)
    setActionError(null)
    try {
      await savedSearchesApi.update(id, { enabled: !enabled })
      await query.refetch()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Не удалось изменить сохранённый поиск')
    } finally {
      setPendingId(null)
    }
  }

  async function handleDelete(id: string) {
    setPendingId(id)
    setActionError(null)
    try {
      await savedSearchesApi.remove(id)
      await query.refetch()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Не удалось удалить сохранённый поиск')
    } finally {
      setPendingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Сохранённые поиски</h1>
        <p className="mt-1 text-sm text-slate-600">
          Каждый активный поиск автоматически обновляется, а о новых и подешевевших объявлениях приходит
          уведомление.
        </p>
      </div>

      {actionError && <p className="text-sm text-red-600">{actionError}</p>}

      {query.isLoading && <LoadingState />}
      {query.isError && <ErrorState message="Не удалось загрузить сохранённые поиски" onRetry={() => query.refetch()} />}
      {query.isSuccess && query.data.length === 0 && (
        <EmptyState message="Пока нет сохранённых поисков — сохраните текущие фильтры на странице поиска." />
      )}

      {query.isSuccess && query.data.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Название</th>
                <th className="px-4 py-2">Фильтры</th>
                <th className="px-4 py-2">Статус</th>
                <th className="px-4 py-2">Последний запуск</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {query.data.map((saved) => (
                <tr key={saved.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-900">{saved.name}</td>
                  <td className="px-4 py-2 text-slate-600">{describeQuery(saved.query)}</td>
                  <td className="px-4 py-2 text-slate-700">{saved.enabled ? 'активен' : 'приостановлен'}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {saved.last_run_at ? formatDate(saved.last_run_at) : 'ещё не запускался'}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      to="/"
                      state={{ savedQuery: saved.query }}
                      className="text-xs font-medium text-slate-700 hover:underline"
                    >
                      Открыть в поиске
                    </Link>
                    <button
                      type="button"
                      disabled={pendingId === saved.id}
                      onClick={() => handleToggle(saved.id, saved.enabled)}
                      className="ml-3 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                    >
                      {saved.enabled ? 'Приостановить' : 'Возобновить'}
                    </button>
                    <button
                      type="button"
                      disabled={pendingId === saved.id}
                      onClick={() => handleDelete(saved.id)}
                      className="ml-2 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
