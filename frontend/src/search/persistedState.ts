import type { GroupField, SearchQuery } from '../lib/search'

// Keeps the search page's filters/grouping/sort/page across reloads and "back to search"
// navigation (SearchPage remounts on both, losing its React state). Session-scoped: a closed tab
// should start fresh, but a reload or a "← К поиску" link shouldn't lose what was just searched.
const STORAGE_KEY = 'polovni:search-state'

export interface PersistedSearchState {
  query: SearchQuery
  groupBy: GroupField[]
  minGroupCount: number | null
  sort: string
  page: number
}

export function loadPersistedSearchState(): PersistedSearchState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as PersistedSearchState) : null
  } catch {
    return null
  }
}

export function savePersistedSearchState(state: PersistedSearchState): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Private browsing / storage disabled — filters just won't survive a reload.
  }
}
