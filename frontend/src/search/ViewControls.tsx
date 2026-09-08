import type { GroupField } from '../lib/search'
import { FLAT_SORT_OPTIONS, GROUP_FIELD_LABELS, GROUP_SORT_OPTIONS } from '../lib/search'

const ALL_GROUP_FIELDS = Object.keys(GROUP_FIELD_LABELS) as GroupField[]

export function ViewControls({
  groupBy,
  onGroupByChange,
  sort,
  onSortChange,
  minGroupCount,
  onMinGroupCountChange,
}: {
  groupBy: GroupField[]
  onGroupByChange: (next: GroupField[]) => void
  sort: string
  onSortChange: (next: string) => void
  minGroupCount: number | null
  onMinGroupCountChange: (next: number | null) => void
}) {
  const isGrouped = groupBy.length > 0
  const sortOptions = isGrouped ? GROUP_SORT_OPTIONS : FLAT_SORT_OPTIONS

  function toggleField(field: GroupField) {
    onGroupByChange(groupBy.includes(field) ? groupBy.filter((f) => f !== field) : [...groupBy, field])
  }

  return (
    <div className="mb-4 flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-xs font-medium text-slate-600">Группировать по:</span>
        {ALL_GROUP_FIELDS.map((field) => (
          <label key={field} className="flex items-center gap-1 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={groupBy.includes(field)}
              onChange={() => toggleField(field)}
              className="rounded border-slate-300"
            />
            {GROUP_FIELD_LABELS[field]}
          </label>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {isGrouped && (
          <label className="flex items-center gap-1.5 text-sm text-slate-700">
            Мин. кол-во в группе
            <input
              type="number"
              min={0}
              className="w-16 rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={minGroupCount ?? ''}
              onChange={(e) => onMinGroupCountChange(e.target.value === '' ? null : Number(e.target.value))}
            />
          </label>
        )}
        <label className="flex items-center gap-1.5 text-sm text-slate-700">
          Сортировка
          <select
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={sort}
            onChange={(e) => onSortChange(e.target.value)}
          >
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  )
}
