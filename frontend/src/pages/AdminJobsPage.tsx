import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { ApiError, type ScrapeJobStatus, scrapeApi } from '../lib/api'

const STATUS_OPTIONS: { value: ScrapeJobStatus | ''; label: string }[] = [
  { value: '', label: 'Все статусы' },
  { value: 'pending', label: 'В очереди' },
  { value: 'running', label: 'Выполняется' },
  { value: 'completed', label: 'Завершено' },
  { value: 'partial', label: 'Частично' },
  { value: 'failed', label: 'Ошибка' },
  { value: 'cancelled', label: 'Отменено' },
]

const RETRYABLE = new Set<ScrapeJobStatus>(['failed', 'cancelled'])
const CANCELLABLE = new Set<ScrapeJobStatus>(['pending', 'running'])

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU')
}

export function AdminJobsPage() {
  const [statusFilter, setStatusFilter] = useState<ScrapeJobStatus | ''>('')
  const [make, setMake] = useState('')
  const [maxPages, setMaxPages] = useState(5)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [pendingActionId, setPendingActionId] = useState<string | null>(null)

  const jobsQuery = useQuery({
    queryKey: ['admin', 'scrape-jobs', statusFilter],
    queryFn: () => scrapeApi.listJobs(statusFilter || undefined),
  })

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    setFormError(null)
    setIsSubmitting(true)
    try {
      await scrapeApi.createJob('polovniautomobili', make || undefined, maxPages)
      setMake('')
      await jobsQuery.refetch()
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Не удалось создать задачу')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleCancel(id: string) {
    setPendingActionId(id)
    try {
      await scrapeApi.cancelJob(id)
      await jobsQuery.refetch()
    } finally {
      setPendingActionId(null)
    }
  }

  async function handleRetry(id: string) {
    setPendingActionId(id)
    try {
      await scrapeApi.retryJob(id)
      await jobsQuery.refetch()
    } finally {
      setPendingActionId(null)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Задачи парсинга</h1>
        <p className="mt-1 text-sm text-slate-600">Создание и управление задачами сбора объявлений.</p>
      </div>

      <form onSubmit={handleCreate} className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-900">Новая задача</h2>
        {formError && <p className="mb-3 text-sm text-red-600">{formError}</p>}
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="job-source">
              Источник
            </label>
            <select
              id="job-source"
              disabled
              value="polovniautomobili"
              className="rounded-md border border-slate-300 bg-slate-50 px-3 py-1.5 text-sm text-slate-700"
            >
              <option value="polovniautomobili">Polovni Automobili</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="job-make">
              Марка (опционально)
            </label>
            <input
              id="job-make"
              value={make}
              onChange={(e) => setMake(e.target.value)}
              placeholder="Skoda"
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="job-max-pages">
              Макс. страниц
            </label>
            <input
              id="job-max-pages"
              type="number"
              min={1}
              max={50}
              value={maxPages}
              onChange={(e) => setMaxPages(Number(e.target.value))}
              className="w-24 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {isSubmitting ? 'Создаём…' : 'Запустить'}
          </button>
        </div>
      </form>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-slate-900">Все задачи</h2>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ScrapeJobStatus | '')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {jobsQuery.isLoading && <LoadingState />}
        {jobsQuery.isError && <ErrorState message="Не удалось загрузить задачи" onRetry={() => jobsQuery.refetch()} />}
        {jobsQuery.isSuccess && jobsQuery.data.length === 0 && <EmptyState message="Задач пока нет" />}

        {jobsQuery.isSuccess && jobsQuery.data.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Тип</th>
                  <th className="px-4 py-2">Статус</th>
                  <th className="px-4 py-2">Начало</th>
                  <th className="px-4 py-2">Конец</th>
                  <th className="px-4 py-2">Ошибка</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {jobsQuery.data.map((job) => (
                  <tr key={job.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-2 text-slate-700">{job.job_type}</td>
                    <td className="px-4 py-2 text-slate-700">{job.status}</td>
                    <td className="px-4 py-2 text-slate-500">{formatTimestamp(job.started_at)}</td>
                    <td className="px-4 py-2 text-slate-500">{formatTimestamp(job.finished_at)}</td>
                    <td className="px-4 py-2 max-w-xs truncate text-slate-500">
                      {job.error ? JSON.stringify(job.error) : '—'}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {CANCELLABLE.has(job.status) && (
                        <button
                          type="button"
                          disabled={pendingActionId === job.id}
                          onClick={() => handleCancel(job.id)}
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                        >
                          Отменить
                        </button>
                      )}
                      {RETRYABLE.has(job.status) && (
                        <button
                          type="button"
                          disabled={pendingActionId === job.id}
                          onClick={() => handleRetry(job.id)}
                          className="ml-2 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                        >
                          Повторить
                        </button>
                      )}
                    </td>
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
