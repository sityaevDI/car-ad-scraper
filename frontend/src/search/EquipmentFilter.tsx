import { useMemo, useState } from 'react'
import { EQUIPMENT_CATEGORIES, EQUIPMENT_POPULAR } from './constants'

const labelClass = 'mb-1 block text-xs font-medium text-slate-600'

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ' +
        (active
          ? 'border-slate-900 bg-slate-900 text-white'
          : 'border-slate-300 text-slate-700 hover:border-slate-400')
      }
    >
      {label}
    </button>
  )
}

export function EquipmentFilter({
  selected,
  onChange,
}: {
  selected: string[] | undefined
  onChange: (next: string[] | undefined) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [search, setSearch] = useState('')
  const current = selected ?? []

  function toggle(value: string) {
    const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value]
    onChange(next.length > 0 ? next : undefined)
  }

  const filteredCategories = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return EQUIPMENT_CATEGORIES
    return EQUIPMENT_CATEGORIES.map((group) => ({
      ...group,
      options: group.options.filter((o) => o.label.toLowerCase().includes(q)),
    })).filter((group) => group.options.length > 0)
  }, [search])

  // Selected features outside the popular set stay visible as their own chips even when
  // collapsed, so opening a saved search with an unusual feature doesn't look like it lost it.
  const extraSelected = current.filter((v) => !EQUIPMENT_POPULAR.some((p) => p.value === v))
  const extraSelectedLabels = extraSelected.map(
    (value) => EQUIPMENT_CATEGORIES.flatMap((g) => g.options).find((o) => o.value === value)?.label ?? value
  )

  return (
    <div>
      <span className={labelClass}>Оснащение</span>
      <div className="flex flex-wrap gap-1.5">
        {EQUIPMENT_POPULAR.map((option) => (
          <Chip
            key={option.value}
            label={option.label}
            active={current.includes(option.value)}
            onClick={() => toggle(option.value)}
          />
        ))}
        {extraSelected.map((value, i) => (
          <Chip key={value} label={extraSelectedLabels[i]} active onClick={() => toggle(value)} />
        ))}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="rounded-full border border-dashed border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-500 hover:border-slate-400"
        >
          {expanded ? 'Свернуть' : 'Ещё опции…'}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 rounded-md border border-slate-200 p-3">
          <input
            type="text"
            placeholder="Поиск по опциям…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="mb-3 w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
          <div className="max-h-72 space-y-3 overflow-y-auto pr-1">
            {filteredCategories.map((group) => (
              <div key={group.category}>
                <div className="mb-1 text-xs font-semibold text-slate-500">{group.category}</div>
                <div className="flex flex-wrap gap-x-3 gap-y-1">
                  {group.options.map((option) => (
                    <label key={option.value} className="flex items-center gap-1 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={current.includes(option.value)}
                        onChange={() => toggle(option.value)}
                        className="rounded border-slate-300"
                      />
                      {option.label}
                    </label>
                  ))}
                </div>
              </div>
            ))}
            {filteredCategories.length === 0 && <div className="text-sm text-slate-400">Ничего не найдено</div>}
          </div>
        </div>
      )}
    </div>
  )
}
