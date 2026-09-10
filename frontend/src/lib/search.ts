import { apiFetch } from './client'
import type { ListingOut } from './listings'

export interface SearchQuery {
  make?: string
  models?: string[]
  year_min?: number
  year_max?: number
  price_min?: number
  price_max?: number
  mileage_min?: number
  mileage_max?: number
  engine_volume_min?: number
  engine_volume_max?: number
  power_min?: number
  power_max?: number
  fuel_types?: string[]
  transmissions?: string[]
  body_types?: string[]
  location?: string
}

// Mirrors SearchQuery.describe() in app/search/query.py.
export function describeQuery(query: SearchQuery): string {
  const parts: string[] = []
  if (query.make) parts.push(String(query.make))
  if (Array.isArray(query.models) && query.models.length) parts.push((query.models as string[]).join('/'))
  if (query.year_min || query.year_max) parts.push(`${query.year_min ?? '…'}–${query.year_max ?? '…'}`)
  if (query.price_min || query.price_max) parts.push(`€${query.price_min ?? '…'}–${query.price_max ?? '…'}`)
  return parts.length ? parts.join(', ') : 'Все объявления'
}

// Mirrors ALLOWED_GROUP_FIELDS in app/search/service.py.
export type GroupField = 'make' | 'model' | 'production_year' | 'fuel_type' | 'transmission' | 'engine_volume_cc' | 'body_type'

export const GROUP_FIELD_LABELS: Record<GroupField, string> = {
  make: 'Марка',
  model: 'Модель',
  production_year: 'Год',
  fuel_type: 'Топливо',
  transmission: 'КПП',
  engine_volume_cc: 'Объём двигателя',
  body_type: 'Кузов',
}

// Mirrors SearchRequest.group_by's default in app/search/query.py.
export const DEFAULT_GROUP_BY: GroupField[] = ['make', 'model', 'engine_volume_cc', 'fuel_type', 'transmission']

export interface SearchRequest {
  query: SearchQuery
  group_by?: GroupField[] | null
  min_group_count?: number | null
  sort?: string
  page?: number
  page_size?: number
}

export interface ListingGroupOut {
  group: Record<string, string | number>
  label: string
  count: number
  currency: string
  price_min: number
  price_avg: number
  price_max: number
  year_min: number
  year_max: number
  mileage_min: number
  mileage_max: number
}

export interface SearchResponse {
  groups?: ListingGroupOut[] | null
  listings?: ListingOut[] | null
  total_listings: number
  total_groups?: number | null
  page: number
  page_size: number
}

// Mirrors _FLAT_SORTS in app/search/service.py.
export const FLAT_SORT_OPTIONS = [
  { value: 'first_seen_desc', label: 'Сначала новые' },
  { value: 'price_asc', label: 'Цена: по возрастанию' },
  { value: 'price_desc', label: 'Цена: по убыванию' },
  { value: 'mileage_asc', label: 'Пробег: по возрастанию' },
  { value: 'mileage_desc', label: 'Пробег: по убыванию' },
  { value: 'year_desc', label: 'Год: сначала новые' },
] as const

// Grouped search only recognizes these three explicitly, else falls back to count_desc — see
// app/search/service.py._search_grouped.
export const GROUP_SORT_OPTIONS = [
  { value: 'count_desc', label: 'Сначала популярные' },
  { value: 'price_asc', label: 'Цена: по возрастанию' },
  { value: 'price_desc', label: 'Цена: по убыванию' },
  { value: 'year_desc', label: 'Год: сначала новые' },
] as const

export const searchApi = {
  search: (request: SearchRequest) =>
    apiFetch<SearchResponse>('/api/v1/search', { method: 'POST', body: JSON.stringify(request) }),
}
