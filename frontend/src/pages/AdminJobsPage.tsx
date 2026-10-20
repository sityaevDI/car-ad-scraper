import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n, { intlLocale } from '../i18n'
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

const STATUS_VALUES: (ScrapeJobStatus | '')[] = ['', 'pending', 'running', 'completed', 'partial', 'failed', 'cancelled']

// Only types the pipeline actually gives distinct behavior to are offered here — the rest
// (listing_refresh, saved_search_refresh, market_refresh) are declared on the backend for later
// phases but aren't wired into run_scrape yet, so scheduling them would silently behave like a
// plain search.
const SCHEDULABLE_JOB_TYPES: ScrapeJobType[] = ['search', 'full_source_refresh']

const RETRYABLE = new Set<ScrapeJobStatus>(['failed', 'cancelled'])
const CANCELLABLE = new Set<ScrapeJobStatus>(['pending', 'running'])

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(intlLocale())
}

// job.query is {"search_query": SearchQuery, "max_pages": number} — see encode_job_query in
// app/scraping/schemas.py.
function describeJobQuery(query: Record<string, unknown> | null): string {
  if (!query) return i18n.t('query.all')
  const searchQuery = (query.search_query as SearchQuery | undefined) ?? {}
  const maxPages = typeof query.max_pages === 'number' ? query.max_pages : undefined
  const filters = describeQuery(searchQuery)
  return maxPages ? i18n.t('admin.upToPages', { filters, pages: maxPages }) : filters
}

function describeJobStats(stats: Record<string, unknown> | null): string {
  if (!stats) return '—'
  const s = stats as ScrapeJobStats
  const seen = s.listings_seen ?? 0
  const created = s.listings_created ?? 0
  const updated = s.listings_updated ?? 0
  const removed = s.listings_removed ?? 0
  const parts = [i18n.t('admin.stats', { seen, created, updated, removed })]

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
  const { t } = useTranslation()
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
      setSaveError(err instanceof ApiError ? err.message : t('admin.saveSettingsFailed'))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <>
      <form onSubmit={handleSave} className="flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="rl-delay">
            {t('admin.delay')}
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
            {t('admin.jitter')}
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
            {t('admin.retryDelay')}
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
          {isSaving ? t('admin.saving') : t('admin.save')}
        </button>
        {savedAt && !saveError && <span className="text-xs text-emerald-600">{t('admin.saved')}</span>}
      </form>
      {saveError && <p className="mt-2 text-sm text-red-600">{saveError}</p>}
    </>
  )
}

// Пауза между запросами внутри одной задачи парсинга (app/scraping/fetch_strategy.py's
// _RequestPacer) — держится в БД (ScrapeRateLimit), поэтому меняется здесь без деплоя и сразу
// действует на все новые задачи (уже запущенные задачи донашивают старое значение).
function RateLimitSettings() {
  const { t } = useTranslation()
  const rateLimitQuery = useQuery({
    queryKey: ['admin', 'scrape-rate-limit'],
    queryFn: scrapeApi.getRateLimit,
  })

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-1 text-sm font-medium text-slate-900">{t('admin.speedTitle')}</h2>
      <p className="mb-3 text-sm text-slate-600">
        {t('admin.speedIntro')}
      </p>

      {rateLimitQuery.isLoading && <LoadingState />}
      {rateLimitQuery.isError && (
        <ErrorState message={t('admin.loadSettingsFailed')} onRetry={() => rateLimitQuery.refetch()} />
      )}
      {rateLimitQuery.data && <RateLimitForm initial={rateLimitQuery.data} />}
    </div>
  )
}

export function AdminJobsPage() {
  const { t } = useTranslation()
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
      setFormError(err instanceof ApiError ? err.message : t('admin.createJobFailed'))
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
      setScheduleFormError(err instanceof ApiError ? err.message : t('admin.createScheduleFailed'))
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
        <h1 className="text-xl font-semibold text-slate-900">{t('admin.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('admin.intro')}</p>
      </div>

      <RateLimitSettings />

      <form onSubmit={handleCreate} className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-900">{t('admin.newJob')}</h2>
        {formError && <p className="mb-3 text-sm text-red-600">{formError}</p>}
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="job-source">
              {t('admin.source')}
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
              {t('admin.makeOptional')}
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
              {t('admin.maxPages')}
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
            {isSubmitting ? t('admin.creating') : t('admin.run')}
          </button>
        </div>
      </form>

      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium text-slate-900">{t('admin.allJobs')}</h2>
            <button
              type="button"
              onClick={() => setJobsCollapsed((prev) => !prev)}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
            >
              {jobsCollapsed ? t('admin.expand') : t('admin.collapse')}
            </button>
            <a href="#schedules" className="text-xs font-medium text-slate-500 underline hover:text-slate-700">
              {t('admin.toSchedules')}
            </a>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="job-date-from">
                {t('admin.dateFrom')}
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
                {t('admin.dateTo')}
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
              {STATUS_VALUES.map((value) => (
                <option key={value} value={value}>
                  {t(`admin.statuses.${value || 'all'}`)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {!jobsCollapsed && (
          <>
            {jobsQuery.isLoading && <LoadingState />}
            {jobsQuery.isError && (
              <ErrorState message={t('admin.loadJobsFailed')} onRetry={() => jobsQuery.refetch()} />
            )}
            {jobsQuery.isSuccess && jobsQuery.data.length === 0 && <EmptyState message={t('admin.noJobs')} />}

            {jobsQuery.isSuccess && jobsQuery.data.length > 0 && (
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-2">{t('admin.colType')}</th>
                      <th className="px-4 py-2">{t('admin.colParams')}</th>
                      <th className="px-4 py-2">{t('admin.colStatus')}</th>
                      <th className="px-4 py-2">{t('admin.colStart')}</th>
                      <th className="px-4 py-2">{t('admin.colEnd')}</th>
                      <th className="px-4 py-2">{t('admin.colResult')}</th>
                      <th className="px-4 py-2">{t('admin.colError')}</th>
                      <th className="px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {jobsQuery.data.map((job) => (
                      <tr key={job.id} className="border-b border-slate-100 last:border-0">
                        <td className="px-4 py-2 text-slate-700">{t(`admin.jobTypes.${job.job_type}`)}</td>
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
                              {t('admin.cancel')}
                            </button>
                          )}
                          {RETRYABLE.has(job.status) && (
                            <button
                              type="button"
                              disabled={pendingActionId === job.id}
                              onClick={() => handleRetry(job.id)}
                              className="ml-2 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                            >
                              {t('admin.retry')}
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
        <h2 className="mb-1 text-sm font-medium text-slate-900">{t('admin.schedules')}</h2>
        <p className="mb-3 text-sm text-slate-600">
          {t('admin.schedulesIntro')}
        </p>

        <form onSubmit={handleCreateSchedule} className="mb-4 rounded-lg border border-slate-200 bg-white p-4">
          {scheduleFormError && <p className="mb-3 text-sm text-red-600">{scheduleFormError}</p>}
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="schedule-job-type">
                {t('admin.jobType')}
              </label>
              <select
                id="schedule-job-type"
                value={scheduleJobType}
                onChange={(e) => setScheduleJobType(e.target.value as ScrapeJobType)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                {SCHEDULABLE_JOB_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {t(`admin.jobTypes.${type}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="schedule-make">
                {t('admin.makeOptional')}
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
                {t('admin.maxPages')}
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
                {t('admin.intervalHours')}
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
              {isCreatingSchedule ? t('admin.creating') : t('admin.addSchedule')}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {t(`admin.jobHints.${scheduleJobType}`)}
          </p>
        </form>

        {schedulesQuery.isLoading && <LoadingState />}
        {schedulesQuery.isError && (
          <ErrorState message={t('admin.loadSchedulesFailed')} onRetry={() => schedulesQuery.refetch()} />
        )}
        {schedulesQuery.isSuccess && schedulesQuery.data.length === 0 && (
          <EmptyState message={t('admin.noSchedules')} />
        )}

        {schedulesQuery.isSuccess && schedulesQuery.data.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">{t('admin.colType')}</th>
                  <th className="px-4 py-2">{t('admin.colInterval')}</th>
                  <th className="px-4 py-2">{t('admin.colStatus')}</th>
                  <th className="px-4 py-2">{t('admin.colNext')}</th>
                  <th className="px-4 py-2">{t('admin.colLast')}</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {schedulesQuery.data.map((schedule) => (
                  <tr key={schedule.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-2 text-slate-700">{t(`admin.jobTypes.${schedule.job_type}`)}</td>
                    <td className="px-4 py-2 text-slate-700">{t('admin.everyHours', { hours: schedule.interval_minutes / 60 })}</td>
                    <td className="px-4 py-2 text-slate-700">{schedule.enabled ? t('admin.enabled') : t('admin.paused')}</td>
                    <td className="px-4 py-2 text-slate-500">{formatTimestamp(schedule.next_run_at)}</td>
                    <td className="px-4 py-2 text-slate-500">{formatTimestamp(schedule.last_run_at)}</td>
                    <td className="px-4 py-2 text-right">
                      <button
                        type="button"
                        disabled={pendingScheduleId === schedule.id}
                        onClick={() => handleToggleSchedule(schedule.id, schedule.enabled)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                      >
                        {schedule.enabled ? t('admin.pause') : t('admin.resume')}
                      </button>
                      <button
                        type="button"
                        disabled={pendingScheduleId === schedule.id}
                        onClick={() => handleDeleteSchedule(schedule.id)}
                        className="ml-2 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                      >
                        {t('admin.delete')}
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
