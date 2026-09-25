import type { PriceScoreOut } from '../lib/listings'

// label values from app/market/pricing.py — text + color per deviation from the segment's
// equipment-adjusted reference price. `short` is used where space is tight (list cards), mirroring
// mobile.de's "Good price"/"Fair price"/"High price" style badges on search result rows.
export const PRICE_LABELS: Record<string, { text: string; short: string; className: string }> = {
  significantly_below: {
    text: 'Значительно ниже рынка',
    short: 'Отличная цена',
    className: 'bg-emerald-100 text-emerald-800',
  },
  below: { text: 'Ниже рынка', short: 'Хорошая цена', className: 'bg-emerald-50 text-emerald-700' },
  market: { text: 'Рыночная цена', short: 'Рыночная цена', className: 'bg-slate-100 text-slate-700' },
  above: { text: 'Выше рынка', short: 'Выше рынка', className: 'bg-amber-50 text-amber-700' },
  significantly_above: {
    text: 'Значительно выше рынка',
    short: 'Цена завышена',
    className: 'bg-rose-100 text-rose-800',
  },
}

export function PriceScoreBadge({
  priceScore,
  variant = 'full',
}: {
  priceScore: PriceScoreOut
  variant?: 'full' | 'short'
}) {
  const info = PRICE_LABELS[priceScore.label]
  if (!info) return null
  return (
    <span className={`inline-block shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${info.className}`}>
      {variant === 'short' ? info.short : info.text}
    </span>
  )
}
