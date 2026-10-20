import { useTranslation } from 'react-i18next'
import type { ListingStatus } from '../lib/listings'

export function StatusBadge({ status }: { status: ListingStatus }) {
  const { t } = useTranslation()
  if (status === 'active') return null
  return (
    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700">
      {t('common.removed')}
    </span>
  )
}
