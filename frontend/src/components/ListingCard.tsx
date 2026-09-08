import { Link } from 'react-router-dom'
import { formatMileage, formatPrice } from '../lib/format'
import type { ListingOut } from '../lib/listings'
import { StatusBadge } from './StatusBadge'
import { FUEL_TYPE_OPTIONS, TRANSMISSION_OPTIONS, BODY_TYPE_OPTIONS } from '../search/constants'

const TAG_LABELS = new Map<string, string>(
  [...FUEL_TYPE_OPTIONS, ...TRANSMISSION_OPTIONS, ...BODY_TYPE_OPTIONS].map((o) => [o.value, o.label]),
)

function tag(value: string | null): string | null {
  if (!value) return null
  return TAG_LABELS.get(value) ?? value
}

export function ListingCard({ listing }: { listing: ListingOut }) {
  const tags = [tag(listing.fuel_type), tag(listing.transmission), tag(listing.body_type)].filter(
    (t): t is string => Boolean(t),
  )

  return (
    <div className="flex gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="h-24 w-32 shrink-0 overflow-hidden rounded-md bg-slate-100">
        {listing.image_url ? (
          <img src={listing.image_url} alt={listing.title} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-slate-400">Нет фото</div>
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
            {tags.map((t) => (
              <span key={t} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                {t}
              </span>
            ))}
          </div>
        )}
        <div className="mt-auto flex items-end justify-between pt-2">
          <span className="text-base font-semibold text-slate-900">{formatPrice(listing.price, listing.currency)}</span>
          <div className="flex gap-3 text-xs">
            <Link to={`/listings/${listing.id}`} className="font-medium text-slate-700 hover:underline">
              Подробнее
            </Link>
            <a
              href={listing.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-slate-700 hover:underline"
            >
              Источник ↗
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
