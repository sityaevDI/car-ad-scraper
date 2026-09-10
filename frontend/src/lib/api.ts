import { apiFetch } from './client'

export { ApiError } from './client'

export type UserRole = 'user' | 'admin'

export interface UserOut {
  id: string
  email: string
  email_verified: boolean
  role: UserRole
  created_at: string
  last_login_at: string | null
}

export interface MessageOut {
  detail: string
}

export const authApi = {
  register: (email: string, password: string) =>
    apiFetch<UserOut>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),

  login: (email: string, password: string) =>
    apiFetch<UserOut>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  logout: () => apiFetch<void>('/api/v1/auth/logout', { method: 'POST' }),

  verifyEmail: (token: string) =>
    apiFetch<MessageOut>('/api/v1/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) }),

  forgotPassword: (email: string) =>
    apiFetch<MessageOut>('/api/v1/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),

  resetPassword: (token: string, newPassword: string) =>
    apiFetch<MessageOut>('/api/v1/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  me: () => apiFetch<UserOut>('/api/v1/me'),
}

export type ScrapeJobStatus = 'pending' | 'running' | 'completed' | 'partial' | 'failed' | 'cancelled'
export type ScrapeJobType =
  | 'search'
  | 'listing_refresh'
  | 'saved_search_refresh'
  | 'full_source_refresh'
  | 'market_refresh'

export interface ScrapeJobOut {
  id: string
  source_id: string
  job_type: ScrapeJobType
  status: ScrapeJobStatus
  query: Record<string, unknown> | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  stats: Record<string, unknown> | null
  error: Record<string, unknown> | null
}

export interface ScrapeJobStats {
  listings_seen?: number
  listings_created?: number
  listings_updated?: number
  listings_removed?: number
  outcome_counts?: Record<string, number>
  error_detail?: string | null
}

export interface ListJobsFilters {
  status?: ScrapeJobStatus
  dateFrom?: string
  dateTo?: string
}

export const scrapeApi = {
  listJobs: (filters: ListJobsFilters = {}) => {
    const params = new URLSearchParams()
    if (filters.status) params.set('status', filters.status)
    if (filters.dateFrom) params.set('date_from', filters.dateFrom)
    if (filters.dateTo) params.set('date_to', filters.dateTo)
    const qs = params.toString()
    return apiFetch<ScrapeJobOut[]>(`/api/v1/scrape/jobs${qs ? `?${qs}` : ''}`)
  },

  createJob: (sourceCode: string, make?: string, maxPages = 5) =>
    apiFetch<ScrapeJobOut>('/api/v1/scrape/jobs', {
      method: 'POST',
      body: JSON.stringify({ source_code: sourceCode, query: make ? { make } : {}, max_pages: maxPages }),
    }),

  cancelJob: (id: string) => apiFetch<ScrapeJobOut>(`/api/v1/scrape/jobs/${id}/cancel`, { method: 'POST' }),

  retryJob: (id: string) => apiFetch<ScrapeJobOut>(`/api/v1/scrape/jobs/${id}/retry`, { method: 'POST' }),

  listSchedules: () => apiFetch<ScheduledScrapeOut[]>('/api/v1/scrape/schedules'),

  createSchedule: (
    sourceCode: string,
    intervalMinutes: number,
    make?: string,
    maxPages = 5,
    jobType: ScrapeJobType = 'search',
  ) =>
    apiFetch<ScheduledScrapeOut>('/api/v1/scrape/schedules', {
      method: 'POST',
      body: JSON.stringify({
        source_code: sourceCode,
        job_type: jobType,
        query: make ? { make } : {},
        max_pages: maxPages,
        interval_minutes: intervalMinutes,
      }),
    }),

  updateSchedule: (id: string, update: { enabled?: boolean; interval_minutes?: number }) =>
    apiFetch<ScheduledScrapeOut>(`/api/v1/scrape/schedules/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    }),

  deleteSchedule: (id: string) => apiFetch<void>(`/api/v1/scrape/schedules/${id}`, { method: 'DELETE' }),

  getRateLimit: () => apiFetch<ScrapeRateLimitOut>('/api/v1/scrape/rate-limit'),

  updateRateLimit: (update: Partial<ScrapeRateLimitOut>) =>
    apiFetch<ScrapeRateLimitOut>('/api/v1/scrape/rate-limit', {
      method: 'PATCH',
      body: JSON.stringify(update),
    }),
}

export interface ScrapeRateLimitOut {
  request_delay_seconds: number
  request_jitter_seconds: number
  network_error_retry_delay_seconds: number
}

export interface ScheduledScrapeOut {
  id: string
  source_id: string
  job_type: ScrapeJobType
  query: Record<string, unknown> | null
  interval_minutes: number
  enabled: boolean
  next_run_at: string
  last_run_at: string | null
  last_job_id: string | null
}
