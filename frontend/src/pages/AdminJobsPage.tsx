import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import {
  ApiError,
  type ScrapeJobStats,
  type ScrapeJobStatus,
  type ScrapeJobType,
  type ScrapeRateLimitOut,
  scrapeApi,
} from '../lib/api'
import { describeQuery, type SearchQuery } from '../lib/search'

const STATUS_OPTIONS: { value: ScrapeJobStatus | ''; label: string }[] = [
  { value: '', label: 'Все статусы' },
  { value: 'pending', label: 'В очереди' },
  { value: 'running', label: 'Выполняется' },
  { value: 'completed', label: 'Завершено' },
  { value: 'partial', label: 'Частично' },
  { value: 'failed', label: 'Ошибка' },
  { value: 'cancelled', label: 'Отменено' },
]

// Only types the pipeline actually gives distinct behavior to are offered here — the rest
// (listing_refresh, saved_search_refresh, market_refresh) are declared on the backend for later
// phases but aren't wired into run_scrape yet, so scheduling them would silently behave like a
// plain search.
const SCHEDULABLE_JOB_TYPES: { value: ScrapeJobType; label: string; hint: string }[] = [
  { value: 'search', label: 'Поиск по фильтру', hint: 'Обновляет объявления, попадающие под фильтр ниже.' },
  {
    value: 'full_source_refresh',
    label: 'Полное обновление источника',
    hint: 'Обходит источник целиком (без фильтра) и помечает пропавшие объявления как REMOVED.',
  },
]

const JOB_TYPE_LABELS: Record<ScrapeJobType, string> = {
  search: 'Поиск по фильтру',
  full_source_refresh: 'Полное обновление источника',
  listing_refresh: 'Обновление объявления',
  saved_search_refresh: 'Обновление сохранённого поиска',
  market_refresh: 'Обновление рынка',
}

const RETRYABLE = new Set<ScrapeJobStatus>(['failed', 'cancelled'])
const CANCELLABLE = new Set<ScrapeJobStatus>(['pending', 'running'])

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU')
}

// job.query is {"search_query": SearchQuery, "max_pages": number} — see encode_job_query in
// app/scraping/schemas.py.
function describeJobQuery(query: Record<string, unknown> | null): string {
  if (!query) return 'Все объявления'
  const searchQuery = (query.search_query as SearchQuery | undefined) ?? {}
  const maxPages = typeof query.max_pages === 'number' ? query.max_pages : undefined
  const filters = describeQuery(searchQuery)
  return maxPages ? `${filters} (до ${maxPages} стр.)` : filters
}

function describeJobStats(stats: Record<string, unknown> | null): string {
  if (!stats) return '—'
  const s = stats as ScrapeJobStats
  const seen = s.listings_seen ?? 0
  const created = s.listings_created ?? 0
  const updated = s.listings_updated ?? 0
  const removed = s.listings_removed ?? 0
  const parts = [`всего ${seen}, новых ${created}, обновлено ${updated}, удалено ${removed}`]

  const outcomes = Object.entries(s.outcome_counts ?? {}).filter(([, count]) => count > 0)
  if (outcomes.length > 0) {
    parts.push(outcomes.map(([outcome, count]) => `${outcome}: ${count}`).join(', '))
  }
  if (s.error_detail) {
    parts.push(s.error_detail)
  }
  return parts.join(' — ')
}

// Editable form for the currently-loaded rate limit — split out from RateLimitSettings so its
// local draft state can be initialized directly from the `initial` prop (useState(initial)) once
// the query has data, instead of syncing query -> state with an effect.
function RateLimitForm({ initial }: { initial: ScrapeRateLimitOut }) {
  const [form, setForm] = useState(initial)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  async function handleSave(event: React.FormEvent) {
    event.preventDefault()
    setSaveError(null)
    setIsSaving(true)
    try {
      const updated = await scrapeApi.updateRateLimit(form)
      setForm(updated)
      setSavedAt(Date.now())
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Не удалось сохранить настройки')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <>
      <form onSubmit={handleSave} className="flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="rl-delay">
            Задержка, сек
          </label>
          <input
            id="rl-delay"
            type="number"
            min={0}
            step={0.1}
            value={form.request_delay_seconds}
            onChange={(e) => setForm({ ...form, request_delay_seconds: Number(e.target.value) })}
            className="w-28 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="rl-jitter">
            Разброс (±), сек
          </label>
          <input
            id="rl-jitter"
            type="number"
            min={0}
            step={0.1}
            value={form.request_jitter_seconds}
            onChange={(e) => setForm({ ...form, request_jitter_seconds: Number(e.target.value) })}
            className="w-28 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="rl-retry">
            Retry при обрыве, сек
          </label>
          <input
            id="rl-retry"
            type="number"
            min={0}
            step={0.5}
            value={form.network_error_retry_delay_seconds}
            onChange={(e) => setForm({ ...form, network_error_retry_delay_seconds: Number(e.target.value) })}
            className="w-32 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={isSaving}
          className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {isSaving ? 'Сохраняем…' : 'Сохранить'}
        </button>
        {savedAt && !saveError && <span className="text-xs text-emerald-600">Сохранено</span>}
      </form>
      {saveError && <p className="mt-2 text-sm text-red-600">{saveError}</p>}
    </>
  )
}

// Пауза между запросами внутри одной задачи парсинга (app/scraping/fetch_strategy.py's
// _RequestPacer) — держится в БД (ScrapeRateLimit), поэтому меняется здесь без деплоя и сразу
// действует на все новые задачи (уже запущенные задачи донашивают старое значение).
function RateLimitSettings() {
  const rateLimitQuery = useQuery({
    queryKey: ['admin', 'scrape-rate-limit'],
    queryFn: scrapeApi.getRateLimit,
  })

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-1 text-sm font-medium text-slate-900">Скорость парсинга</h2>
      <p className="mb-3 text-sm text-slate-600">
        Пауза между запросами к источнику внутри одной задачи. Меньшие значения — быстрее обход
        (12 тыс. страниц при 0.8с ≈ 2.5–3 часа вместо 7–8), но выше риск блокировки и больше
        расход прокси-квоты при срабатывании защиты источника.
      </p>

      {rateLimitQuery.isLoading && <LoadingState />}
      {rateLimitQuery.isError && (
        <ErrorState message="Не удалось загрузить настройки" onRetry={() => rateLimitQuery.refetch()} />
      )}
      {rateLimitQuery.data && <RateLimitForm initial={rateLimitQuery.data} />}
    </div>
  )
}

export function AdminJobsPage() {
  const [statusFilter, setStatusFilter] = useState<ScrapeJobStatus | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [jobsCollapsed, setJobsCollapsed] = useState(false)
  const [make, setMake] = useState('')
  const [maxPages, setMaxPages] = useState(5)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [pendingActionId, setPendingActionId] = useState<string | null>(null)

  const [scheduleJobType, setScheduleJobType] = useState<ScrapeJobType>('search')
  const [scheduleMake, setScheduleMake] = useState('')
  const [scheduleMaxPages, setScheduleMaxPages] = useState(5)
  const [intervalHours, setIntervalHours] = useState(6)
  const [scheduleFormError, setScheduleFormError] = useState<string | null>(null)
  const [isCreatingSchedule, setIsCreatingSchedule] = useState(false)
  const [pendingScheduleId, setPendingScheduleId] = useState<string | null>(null)

  const jobsQuery = useQuery({
    queryKey: ['admin', 'scrape-jobs', statusFilter, dateFrom, dateTo],
    queryFn: () =>
      scrapeApi.listJobs({
        status: statusFilter || undefined,
        dateFrom: dateFrom ? `${dateFrom}T00:00:00` : undefined,
        dateTo: dateTo ? `${dateTo}T23:59:59` : undefined,
      }),
  })

  const schedulesQuery = useQuery({
    queryKey: ['admin', 'scheduled-scrapes'],
    queryFn: scrapeApi.listSchedules,
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

  async function handleCreateSchedule(event: React.FormEvent) {
    event.preventDefault()
    setScheduleFormError(null)
    setIsCreatingSchedule(true)
    try {
      const isFullSourceRefresh = scheduleJobType === 'full_source_refresh'
      await scrapeApi.createSchedule(
        'polovniautomobili',
        intervalHours * 60,
        isFullSourceRefresh ? undefined : scheduleMake || undefined,
        scheduleMaxPages,
        scheduleJobType,
      )
      setScheduleMake('')
      await schedulesQuery.refetch()
    } catch (err) {
      setScheduleFormError(err instanceof ApiError ? err.message : 'Не удалось создать расписание')
    } finally {
      setIsCreatingSchedule(false)
    }
  }

  async function handleToggleSchedule(id: string, enabled: boolean) {
    setPendingScheduleId(id)
    try {
      await scrapeApi.updateSchedule(id, { enabled: !enabled })
      await schedulesQuery.refetch()
    } finally {
      setPendingScheduleId(null)
    }
  }

  async function handleDeleteSchedule(id: string) {
    setPendingScheduleId(id)
    try {
      await scrapeApi.deleteSchedule(id)
      await schedulesQuery.refetch()
    } finally {
      setPendingScheduleId(null)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Задачи парсинга</h1>
        <p className="mt-1 text-sm text-slate-600">Создание и управление задачами сбора объявлений.</p>
      </div>

      <RateLimitSettings />

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
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium text-slate-900">Все задачи</h2>
            <button
              type="button"
              onClick={() => setJobsCollapsed((prev) => !prev)}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
            >
              {jobsCollapsed ? 'Развернуть' : 'Свернуть'}
            </button>
            <a href="#schedules" className="text-xs font-medium text-slate-500 underline hover:text-slate-700">
              К расписаниям ↓
            </a>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="job-date-from">
                С даты
              </label>
              <input
                id="job-date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="job-date-to">
                По дату
              </label>
              <input
                id="job-date-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
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
        </div>

        {!jobsCollapsed && (
          <>
            {jobsQuery.isLoading && <LoadingState />}
            {jobsQuery.isError && (
              <ErrorState message="Не удалось загрузить задачи" onRetry={() => jobsQuery.refetch()} />
            )}
            {jobsQuery.isSuccess && jobsQuery.data.length === 0 && <EmptyState message="Задач пока нет" />}

            {jobsQuery.isSuccess && jobsQuery.data.length > 0 && (
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-2">Тип</th>
                      <th className="px-4 py-2">Параметры</th>
                      <th className="px-4 py-2">Статус</th>
                      <th className="px-4 py-2">Начало</th>
                      <th className="px-4 py-2">Конец</th>
                      <th className="px-4 py-2">Результат</th>
                      <th className="px-4 py-2">Ошибка</th>
                      <th className="px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {jobsQuery.data.map((job) => (
                      <tr key={job.id} className="border-b border-slate-100 last:border-0">
                        <td className="px-4 py-2 text-slate-700">{JOB_TYPE_LABELS[job.job_type]}</td>
                        <td className="px-4 py-2 max-w-xs text-slate-500">{describeJobQuery(job.query)}</td>
                        <td className="px-4 py-2 text-slate-700">{job.status}</td>
                        <td className="px-4 py-2 text-slate-500">{formatTimestamp(job.started_at)}</td>
                        <td className="px-4 py-2 text-slate-500">{formatTimestamp(job.finished_at)}</td>
                        <td className="px-4 py-2 text-slate-500">{describeJobStats(job.stats)}</td>
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
          </>
        )}
      </div>

      <div id="schedules" className="scroll-mt-4">
        <h2 className="mb-1 text-sm font-medium text-slate-900">Расписания</h2>
        <p className="mb-3 text-sm text-slate-600">
          Регулярный запуск задачи с заданным интервалом — держит данные актуальными без ручных запусков.
        </p>

        <form onSubmit={handleCreateSchedule} className="mb-4 rounded-lg border border-slate-200 bg-white p-4">
          {scheduleFormError && <p className="mb-3 text-sm text-red-600">{scheduleFormError}</p>}
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="schedule-job-type">
                Тип задачи
              </label>
              <select
                id="schedule-job-type"
                value={scheduleJobType}
                onChange={(e) => setScheduleJobType(e.target.value as ScrapeJobType)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                {SCHEDULABLE_JOB_TYPES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="schedule-make">
                Марка (опционально)
              </label>
              <input
                id="schedule-make"
                value={scheduleMake}
                onChange={(e) => setScheduleMake(e.target.value)}
                placeholder="Skoda"
                disabled={scheduleJobType === 'full_source_refresh'}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:bg-slate-50 disabled:text-slate-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="schedule-max-pages">
                Макс. страниц
              </label>
              <input
                id="schedule-max-pages"
                type="number"
                min={1}
                value={scheduleMaxPages}
                onChange={(e) => setScheduleMaxPages(Number(e.target.value))}
                className="w-24 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="schedule-interval">
                Интервал, часы
              </label>
              <input
                id="schedule-interval"
                type="number"
                min={1}
                max={168}
                value={intervalHours}
                onChange={(e) => setIntervalHours(Number(e.target.value))}
                className="w-24 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={isCreatingSchedule}
              className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {isCreatingSchedule ? 'Создаём…' : 'Добавить расписание'}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {SCHEDULABLE_JOB_TYPES.find((opt) => opt.value === scheduleJobType)?.hint}
          </p>
        </form>

        {schedulesQuery.isLoading && <LoadingState />}
        {schedulesQuery.isError && (
          <ErrorState message="Не удалось загрузить расписания" onRetry={() => schedulesQuery.refetch()} />
        )}
        {schedulesQuery.isSuccess && schedulesQuery.data.length === 0 && (
          <EmptyState message="Расписаний пока нет" />
        )}

        {schedulesQuery.isSuccess && schedulesQuery.data.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Тип</th>
                  <th className="px-4 py-2">Интервал</th>
                  <th className="px-4 py-2">Статус</th>
                  <th className="px-4 py-2">Следующий запуск</th>
                  <th className="px-4 py-2">Последний запуск</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {schedulesQuery.data.map((schedule) => (
                  <tr key={schedule.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-2 text-slate-700">{JOB_TYPE_LABELS[schedule.job_type]}</td>
                    <td className="px-4 py-2 text-slate-700">каждые {schedule.interval_minutes / 60} ч</td>
                    <td className="px-4 py-2 text-slate-700">{schedule.enabled ? 'активно' : 'приостановлено'}</td>
                    <td className="px-4 py-2 text-slate-500">{formatTimestamp(schedule.next_run_at)}</td>
                    <td className="px-4 py-2 text-slate-500">{formatTimestamp(schedule.last_run_at)}</td>
                    <td className="px-4 py-2 text-right">
                      <button
                        type="button"
                        disabled={pendingScheduleId === schedule.id}
                        onClick={() => handleToggleSchedule(schedule.id, schedule.enabled)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                      >
                        {schedule.enabled ? 'Приостановить' : 'Возобновить'}
                      </button>
                      <button
                        type="button"
                        disabled={pendingScheduleId === schedule.id}
                        onClick={() => handleDeleteSchedule(schedule.id)}
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
    </div>
  )
}
