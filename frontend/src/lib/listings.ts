import { apiFetch } from './client'

export type ListingStatus = 'active' | 'removed'

export interface ListingOut {
  id: string
  source_id: string
  external_id: string
  canonical_url: string
  title: string
  make: string
  model: string
  production_year: number
  mileage_km: number
  price: number
  currency: string
  fuel_type: string | null
  transmission: string | null
  body_type: string | null
  engine_volume_cc: number | null
  power_hp: number | null
  location: string | null
  image_url: string | null
  status: ListingStatus
  first_seen_at: string
  last_seen_at: string
  last_checked_at: string
}

export interface ListingSnapshotOut {
  id: string
  captured_at: string
  price: number
  mileage_km: number
  title: string
}

export interface ListingHistoryOut {
  listing: ListingOut
  snapshots: ListingSnapshotOut[]
}

export const listingsApi = {
  get: (id: string) => apiFetch<ListingOut>(`/api/v1/listings/${id}`),
  getHistory: (id: string) => apiFetch<ListingHistoryOut>(`/api/v1/listings/${id}/history`),
}
