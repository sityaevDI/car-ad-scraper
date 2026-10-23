import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ApiError } from '../lib/client'
import { formatDate } from '../lib/format'
import { describeGrouping, describeQuery } from '../lib/search'
import { savedSearchesApi } from '../lib/savedSearches'
import { searchPathForSaved, viewFromSaved } from '../search/searchUrl'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'

export function SavedSearchesPage() {
  const { t } = useTranslation()
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
      setActionError(err instanceof ApiError ? err.message : t('savedSearches.updateFailed'))
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
      setActionError(err instanceof ApiError ? err.message : t('savedSearches.deleteFailed'))
    } finally {
      setPendingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{t('savedSearches.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">
          {t('savedSearches.intro')}
        </p>
      </div>

      {actionError && <p className="text-sm text-red-600">{actionError}</p>}

      {query.isLoading && <LoadingState />}
      {query.isError && <ErrorState message={t('savedSearches.loadFailed')} onRetry={() => query.refetch()} />}
      {query.isSuccess && query.data.length === 0 && (
        <EmptyState message={t('savedSearches.empty')} />
      )}

      {query.isSuccess && query.data.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">{t('savedSearches.name')}</th>
                <th className="px-4 py-2">{t('savedSearches.filters')}</th>
                <th className="px-4 py-2">{t('savedSearches.status')}</th>
                <th className="px-4 py-2">{t('savedSearches.lastRun')}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {query.data.map((saved) => (
                <tr key={saved.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-900">{saved.name}</td>
                  <td className="px-4 py-2 text-slate-600">
                    {describeQuery(saved.query)}
                    {saved.view_settings && (
                      <div className="text-xs text-slate-400">
                        {t('savedSearches.grouping', { value: describeGrouping(viewFromSaved(saved.view_settings).groupBy) })}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{saved.enabled ? t('savedSearches.active') : t('savedSearches.paused')}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {saved.last_run_at ? formatDate(saved.last_run_at) : t('savedSearches.neverRun')}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      to={searchPathForSaved(saved)}
                      className="text-xs font-medium text-slate-700 hover:underline"
                    >
                      {t('savedSearches.open')}
                    </Link>
                    <button
                      type="button"
                      disabled={pendingId === saved.id}
                      onClick={() => handleToggle(saved.id, saved.enabled)}
                      className="ml-3 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                    >
                      {saved.enabled ? t('savedSearches.pause') : t('savedSearches.resume')}
                    </button>
                    <button
                      type="button"
                      disabled={pendingId === saved.id}
                      onClick={() => handleDelete(saved.id)}
                      className="ml-2 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                    >
                      {t('savedSearches.delete')}
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
