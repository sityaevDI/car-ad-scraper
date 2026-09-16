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
  is_following: boolean
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

export type MarketConfidence = 'insufficient' | 'low' | 'medium' | 'high'

export interface MarketEstimateOut {
  estimated_price: number | null
  currency: string
  price_low: number | null
  price_high: number | null
  confidence: MarketConfidence
  comparable_listings_count: number
  computed_at: string
  algorithm_version: string
}

export interface PriceScoreOut {
  price_ratio: number
  deviation_pct: number
  label: string
}

export interface MarketComparisonOut {
  market: MarketEstimateOut | null
  price_score: PriceScoreOut | null
}

export const listingsApi = {
  get: (id: string) => apiFetch<ListingOut>(`/api/v1/listings/${id}`),
  getHistory: (id: string) => apiFetch<ListingHistoryOut>(`/api/v1/listings/${id}/history`),
  follow: (id: string) => apiFetch<void>(`/api/v1/listings/${id}/follow`, { method: 'POST' }),
  unfollow: (id: string) => apiFetch<void>(`/api/v1/listings/${id}/follow`, { method: 'DELETE' }),
  getMarketComparison: (id: string) => apiFetch<MarketComparisonOut>(`/api/v1/listings/${id}/market-comparison`),
}
