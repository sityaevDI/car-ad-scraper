import { apiFetch } from './client'
import type { SearchQuery, SearchResponse } from './search'

export interface SavedSearchOut {
  id: string
  name: string
  query: SearchQuery
  enabled: boolean
  notification_settings: Record<string, unknown> | null
  last_run_at: string | null
  created_at: string
}

export const savedSearchesApi = {
  list: () => apiFetch<SavedSearchOut[]>('/api/v1/saved-searches'),

  get: (id: string) => apiFetch<SavedSearchOut>(`/api/v1/saved-searches/${id}`),

  create: (name: string, query: SearchQuery) =>
    apiFetch<SavedSearchOut>('/api/v1/saved-searches', {
      method: 'POST',
      body: JSON.stringify({ name, query }),
    }),

  update: (id: string, update: { name?: string; enabled?: boolean }) =>
    apiFetch<SavedSearchOut>(`/api/v1/saved-searches/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    }),

  remove: (id: string) => apiFetch<void>(`/api/v1/saved-searches/${id}`, { method: 'DELETE' }),

  run: (id: string) => apiFetch<SearchResponse>(`/api/v1/saved-searches/${id}/run`, { method: 'POST' }),
}
