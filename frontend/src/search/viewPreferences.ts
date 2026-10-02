import type { ViewSettings } from './searchUrl'
import { decodeView, encodeView } from './searchUrl'

// The grouping / min-group-count / sort the user last picked, remembered across tabs and visits.
// Only a starting point: it applies when the URL doesn't spell out a view (a fresh "Поиск", a
// saved-search link), while a URL that does — e.g. the "← К поиску" link — always wins, so
// changing the preference in one tab never rewrites what another tab's links mean.
//
// Stored in the same query-string form the URL uses, so it's validated by the same decoder.
const STORAGE_KEY = 'polovni:search-view'

export function loadViewPreferences(): ViewSettings | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw === null ? null : decodeView(new URLSearchParams(raw))
  } catch {
    return null
  }
}

export function saveViewPreferences(view: ViewSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, encodeView(view).toString())
  } catch {
    // Private browsing / storage disabled — the grouping just won't be remembered.
  }
}

export function clearViewPreferences(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // See saveViewPreferences.
  }
}
