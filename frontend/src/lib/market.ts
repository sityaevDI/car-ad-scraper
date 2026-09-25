import { apiFetch } from './client'

export type RemovalPeriod = 'day' | 'week' | 'month'

export interface RemovalMetrics {
  removed_count: number
  median_days_on_market: number | null
  median_price_at_removal: number | null
  price_cut_share: number | null
  median_price_cut_pct: number | null
}

export interface RemovalBreakdownRow extends RemovalMetrics {
  make: string
  model: string | null
}

export interface RemovalSeriesPoint {
  date: string
  removed_count: number
}

export interface RemovalStatsResponse {
  period: RemovalPeriod
  make: string | null
  as_of: string | null
  computed_at: string | null
  current: RemovalMetrics | null
  previous: RemovalMetrics | null
  series: RemovalSeriesPoint[]
  breakdown: RemovalBreakdownRow[]
}

export const marketApi = {
  getRemovalStats: (period: RemovalPeriod, make?: string) => {
    const params = new URLSearchParams({ period })
    if (make) params.set('make', make)
    return apiFetch<RemovalStatsResponse>(`/api/v1/market/removed-stats?${params}`)
  },
}
