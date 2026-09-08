import type { ListingStatus } from '../lib/listings'

export function StatusBadge({ status }: { status: ListingStatus }) {
  if (status === 'active') return null
  return (
    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700">
      снято с публикации
    </span>
  )
}
