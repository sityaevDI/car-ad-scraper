import { apiFetch } from './client'
import type { GroupField, SearchQuery, SearchResponse } from './search'

// Mirrors SavedSearchView in app/saved_searches/schemas.py: the results layout stored next to the
// filters. Not part of `query` — that's what gets scraped and matched, this is presentation only.
export interface SavedSearchView {
  group_by: GroupField[]
  min_group_count: number | null
  sort: string
}

export interface SavedSearchOut {
  id: string
  name: string
  query: SearchQuery
  view_settings: SavedSearchView | null
  enabled: boolean
  notification_settings: Record<string, unknown> | null
  last_run_at: string | null
  created_at: string
}

export const savedSearchesApi = {
  list: () => apiFetch<SavedSearchOut[]>('/api/v1/saved-searches'),

  get: (id: string) => apiFetch<SavedSearchOut>(`/api/v1/saved-searches/${id}`),

  create: (name: string, query: SearchQuery, viewSettings: SavedSearchView) =>
    apiFetch<SavedSearchOut>('/api/v1/saved-searches', {
      method: 'POST',
      body: JSON.stringify({ name, query, view_settings: viewSettings }),
    }),

  update: (id: string, update: { name?: string; enabled?: boolean }) =>
    apiFetch<SavedSearchOut>(`/api/v1/saved-searches/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    }),

  remove: (id: string) => apiFetch<void>(`/api/v1/saved-searches/${id}`, { method: 'DELETE' }),

  run: (id: string) => apiFetch<SearchResponse>(`/api/v1/saved-searches/${id}/run`, { method: 'POST' }),
}
