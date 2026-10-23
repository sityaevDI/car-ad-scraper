import { Link } from 'react-router-dom'
import { formatMileage, formatPrice } from '../lib/format'
import type { ListingOut } from '../lib/listings'
import { useTranslation } from 'react-i18next'
import { optionLabel, type OptionGroup } from '../i18n'
import { PriceScoreBadge } from './PriceScoreBadge'
import { StatusBadge } from './StatusBadge'

function tag(group: OptionGroup, value: string | null): string | null {
  return value ? optionLabel(group, value) : null
}

// `from` is the search-page URL to return to. It rides in the link's own URL rather than in router
// state or storage, so "← back to search" still lands on the right search when the card is opened in a
// new tab (ctrl/middle click), where neither this tab's state nor its sessionStorage exists.
export function ListingCard({ listing, from }: { listing: ListingOut; from?: string }) {
  const { t } = useTranslation()
  const listingPath = from
    ? `/listings/${listing.id}?${new URLSearchParams({ from })}`
    : `/listings/${listing.id}`
  const tags = [
    tag('fuel_type', listing.fuel_type),
    tag('transmission', listing.transmission),
    tag('body_type', listing.body_type),
    tag('interior_material', listing.interior_material),
    tag('air_condition', listing.air_condition),
    tag('drive_type', listing.drive_type),
  ].filter((label): label is string => Boolean(label))

  return (
    <div className="relative flex gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow-md">
      <div className="h-24 w-32 shrink-0 overflow-hidden rounded-md bg-slate-100">
        {listing.image_url ? (
          <img src={listing.image_url} alt={listing.title} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-slate-400">{t('common.noPhoto')}</div>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-2">
          <h3 className="truncate text-sm font-semibold text-slate-900">{listing.title}</h3>
          <StatusBadge status={listing.status} />
        </div>
        <p className="mt-0.5 text-xs text-slate-500">
          {listing.make} {listing.model} · {listing.production_year} · {formatMileage(listing.mileage_km)}
        </p>
        {tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {tags.map((label) => (
              <span key={label} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                {label}
              </span>
            ))}
          </div>
        )}
        <div className="mt-auto flex items-end justify-between gap-2 pt-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-semibold text-slate-900">{formatPrice(listing.price, listing.currency)}</span>
            {listing.price_score && <PriceScoreBadge priceScore={listing.price_score} variant="short" />}
          </div>
          <div className="flex shrink-0 gap-3 text-xs">
            <span className="font-medium text-slate-700">{t('common.details')}</span>
            {/* Positioned + z-10 so this link stays above the card-wide stretched link below and
                keeps its own click behavior (new tab) instead of triggering the internal one. */}
            <a
              href={listing.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="relative z-10 font-medium text-slate-700 hover:underline"
            >
              {t('common.source')} ↗
            </a>
          </div>
        </div>
      </div>
      {/* Stretched link: makes the whole card (image, title, "Details" text, etc.) clickable. */}
      <Link to={listingPath} className="absolute inset-0 rounded-lg" aria-label={t('common.detailsFor', { title: listing.title })} />
    </div>
  )
}
