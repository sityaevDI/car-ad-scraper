import type { SavedSearchView } from '../lib/savedSearches'
import type { GroupField, SearchQuery } from '../lib/search'
import { DEFAULT_GROUP_BY, FLAT_SORT_OPTIONS, GROUP_FIELD_LABELS, GROUP_SORT_OPTIONS } from '../lib/search'

// The search page's state lives in the URL (`/?make=BMW&group_by=make&sort=count_desc&page=2`), so
// it is per-tab by construction, survives reloads, works with the browser's back/forward, and can
// be carried to the listing page and back (see parseBackTarget) — including into a new tab, which
// has no access to this tab's React state or sessionStorage.

export interface ViewSettings {
  groupBy: GroupField[]
  minGroupCount: number | null
  sort: string
}

export interface SearchState extends ViewSettings {
  query: SearchQuery
  page: number
}

type FieldKind = 'string' | 'number' | 'list'

// Typed as a full Record so adding a field to SearchQuery fails to compile until it's listed here.
// Keys double as URL param names; they must not collide with the view params below.
const QUERY_FIELDS: Record<keyof SearchQuery, FieldKind> = {
  make: 'string',
  models: 'list',
  year_min: 'number',
  year_max: 'number',
  price_min: 'number',
  price_max: 'number',
  mileage_min: 'number',
  mileage_max: 'number',
  engine_volume_min: 'number',
  engine_volume_max: 'number',
  power_min: 'number',
  power_max: 'number',
  fuel_types: 'list',
  transmissions: 'list',
  body_types: 'list',
  interior_materials: 'list',
  air_conditions: 'list',
  drive_types: 'list',
  seats: 'list',
  equipment: 'list',
  location: 'string',
}
const QUERY_FIELD_ENTRIES = Object.entries(QUERY_FIELDS) as [keyof SearchQuery, FieldKind][]

const VIEW_PARAMS = ['group_by', 'min_count', 'sort'] as const

export function defaultSort(isGrouped: boolean): string {
  return isGrouped ? 'count_desc' : 'first_seen_desc'
}

export const DEFAULT_VIEW: ViewSettings = {
  groupBy: DEFAULT_GROUP_BY,
  minGroupCount: null,
  sort: defaultSort(true),
}

export function isDefaultView(view: ViewSettings): boolean {
  return (
    view.minGroupCount === null &&
    view.sort === DEFAULT_VIEW.sort &&
    view.groupBy.length === DEFAULT_VIEW.groupBy.length &&
    view.groupBy.every((field, i) => field === DEFAULT_VIEW.groupBy[i])
  )
}

export function hasActiveFilters(query: SearchQuery): boolean {
  return Object.values(query).some((value) => (Array.isArray(value) ? value.length > 0 : !isUnset(value)))
}

function isGroupField(value: string): value is GroupField {
  return value in GROUP_FIELD_LABELS
}

// A query that came from the API (a saved search) is SearchQuery.model_dump(): every unset field is
// an explicit `null`, not a missing key — so "unset" has to cover both, or a null list is iterated
// and a null number is written out as the string "null".
function isUnset(value: unknown): boolean {
  return value === undefined || value === null || value === ''
}

function appendQuery(params: URLSearchParams, query: SearchQuery): void {
  for (const [key, kind] of QUERY_FIELD_ENTRIES) {
    const value = query[key]
    if (isUnset(value)) continue
    if (kind === 'list') {
      for (const item of value as string[]) params.append(key, item)
    } else {
      params.set(key, String(value))
    }
  }
}

// Always spells the view out (an ungrouped view is an empty `group_by=`), so a URL produced here
// means the same thing no matter what the saved view preference is when it's opened later.
function appendView(params: URLSearchParams, view: ViewSettings): void {
  if (view.groupBy.length === 0) params.set('group_by', '')
  for (const field of view.groupBy) params.append('group_by', field)
  if (view.minGroupCount !== null) params.set('min_count', String(view.minGroupCount))
  params.set('sort', view.sort)
}

export function encodeView(view: ViewSettings): URLSearchParams {
  const params = new URLSearchParams()
  appendView(params, view)
  return params
}

// Canonical form: fixed param order and no defaults dropped, so parse -> encode is stable and the
// page can rewrite a hand-edited or partial URL into it without looping.
export function encodeSearchState(state: SearchState): URLSearchParams {
  const params = new URLSearchParams()
  appendQuery(params, state.query)
  appendView(params, state)
  if (state.page > 1) params.set('page', String(state.page))
  return params
}

// Filters only — the view (grouping/sort) then comes from the saved preference. Used by links that
// open a stored query ("Открыть в поиске", the saved-search email).
export function searchPathForQuery(query: SearchQuery): string {
  const params = new URLSearchParams()
  appendQuery(params, query)
  const search = params.toString()
  return search ? `/?${search}` : '/'
}

export function searchPathForState(state: SearchState): string {
  return `/?${encodeSearchState(state)}`
}

export function viewToSaved(view: ViewSettings): SavedSearchView {
  return { group_by: view.groupBy, min_group_count: view.minGroupCount, sort: view.sort }
}

// Goes through the URL decoder so a stored layout is validated (unknown fields dropped, a sort that
// doesn't fit the grouping mode replaced) the same way as one typed into the address bar.
export function viewFromSaved(saved: SavedSearchView): ViewSettings {
  return decodeView(encodeView({ groupBy: saved.group_by, minGroupCount: saved.min_group_count, sort: saved.sort }))
}

// "Открыть в поиске" / the saved-search email link. A saved layout is spelled out in the URL (it
// wins over the user's remembered view, like any explicit view); a saved search from before layouts
// were stored carries only filters, so the remembered view applies.
export function searchPathForSaved(saved: { query: SearchQuery; view_settings: SavedSearchView | null }): string {
  if (!saved.view_settings) return searchPathForQuery(saved.query)
  return searchPathForState({ query: saved.query, ...viewFromSaved(saved.view_settings), page: 1 })
}

function parseQuery(params: URLSearchParams): SearchQuery {
  const query: Record<string, string | number | string[]> = {}
  for (const [key, kind] of QUERY_FIELD_ENTRIES) {
    if (kind === 'list') {
      const items = params.getAll(key).filter(Boolean)
      if (items.length > 0) query[key] = items
      continue
    }
    const raw = params.get(key)
    if (!raw) continue
    if (kind === 'string') {
      query[key] = raw
    } else {
      const parsed = Number(raw)
      if (Number.isFinite(parsed)) query[key] = parsed
    }
  }
  return query as SearchQuery
}

function hasExplicitView(params: URLSearchParams): boolean {
  return VIEW_PARAMS.some((name) => params.has(name))
}

// Missing params mean "default" here, not "whatever was saved" — the fallback to the saved view is
// decided once, in parseSearchParams, for URLs that don't mention the view at all.
export function decodeView(params: URLSearchParams): ViewSettings {
  const groupBy = params.has('group_by') ? params.getAll('group_by').filter(isGroupField) : DEFAULT_GROUP_BY

  const rawMin = params.get('min_count')
  const min = rawMin === null || rawMin === '' ? NaN : Number(rawMin)
  const minGroupCount = Number.isFinite(min) && min >= 0 ? min : null

  const rawSort = params.get('sort')
  const sortOptions = groupBy.length > 0 ? GROUP_SORT_OPTIONS : FLAT_SORT_OPTIONS
  const sort = sortOptions.some((option) => option.value === rawSort) ? rawSort! : defaultSort(groupBy.length > 0)

  return { groupBy, minGroupCount, sort }
}

export function parseSearchParams(params: URLSearchParams, savedView: ViewSettings | null): SearchState {
  const view = hasExplicitView(params) ? decodeView(params) : (savedView ?? DEFAULT_VIEW)
  const page = Number(params.get('page'))
  return {
    query: parseQuery(params),
    ...view,
    page: Number.isInteger(page) && page > 1 ? page : 1,
  }
}

// The listing page's "← К поиску" target comes from a URL param, so only accept a search-page
// location (`/` or `/?...`) — never another route or an external/protocol-relative URL.
export function parseBackTarget(raw: string | null): string | null {
  if (raw === null) return null
  return raw === '/' || raw.startsWith('/?') ? raw : null
}
