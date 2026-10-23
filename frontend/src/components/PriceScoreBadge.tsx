import { useTranslation } from 'react-i18next'
import type { PriceScoreOut } from '../lib/listings'

// label values from app/market/pricing.py — color per deviation from the segment's equipment-adjusted
// reference price; text lives in the dictionaries (price.<label>.text|short). `short` is used where
// space is tight (list cards), mirroring mobile.de's "Good price"/"Fair price"/"High price" badges.
export const PRICE_CLASSES: Record<string, string> = {
  significantly_below: 'bg-emerald-100 text-emerald-800',
  below: 'bg-emerald-50 text-emerald-700',
  market: 'bg-slate-100 text-slate-700',
  above: 'bg-amber-50 text-amber-700',
  significantly_above: 'bg-rose-100 text-rose-800',
}

export function PriceScoreBadge({
  priceScore,
  variant = 'full',
}: {
  priceScore: PriceScoreOut
  variant?: 'full' | 'short'
}) {
  const { t } = useTranslation()
  const className = PRICE_CLASSES[priceScore.label]
  if (!className) return null
  return (
    <span className={`inline-block shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${className}`}>
      {t(`price.${priceScore.label}.${variant === 'short' ? 'short' : 'text'}`)}
    </span>
  )
}
