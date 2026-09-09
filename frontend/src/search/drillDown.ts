import type { GroupField, ListingGroupOut, SearchQuery } from '../lib/search'

/**
 * Reconstructs filters for a flat listing of one group's members, per
 * docs/adr/03_FRONTEND.md §5.3 — the backend has no group->listings endpoint, so this replays
 * the group's key dimensions as SearchQuery filters on top of the query that produced it.
 * Mirrors the engine_volume_cc bucketing rounding in app/search/service.py (_ENGINE_VOLUME_BUCKET).
 */
export function buildDrillDownQuery(baseQuery: SearchQuery, groupBy: GroupField[], group: ListingGroupOut['group']): SearchQuery {
  const next: SearchQuery = { ...baseQuery }
  for (const field of groupBy) {
    const value = group[field]
    if (value === null || value === undefined) continue
    switch (field) {
      case 'make':
        next.make = String(value)
        break
      case 'model':
        next.models = [String(value)]
        break
      case 'fuel_type':
        next.fuel_types = [String(value)]
        break
      case 'transmission':
        next.transmissions = [String(value)]
        break
      case 'body_type':
        next.body_types = [String(value)]
        break
      case 'production_year':
        next.year_min = Number(value)
        next.year_max = Number(value)
        break
      case 'engine_volume_cc':
        next.engine_volume_min = Number(value) - 50
        next.engine_volume_max = Number(value) + 49
        break
    }
  }
  return next
}
