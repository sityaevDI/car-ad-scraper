import type { SearchQuery } from '../lib/search'
import { useVehicleMakes } from './useVehicleMakes'
import { BODY_TYPE_OPTIONS, FUEL_TYPE_OPTIONS, TRANSMISSION_OPTIONS } from './constants'
import { EquipmentFilter } from './EquipmentFilter'

const inputClass =
  'w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500'
const labelClass = 'mb-1 block text-xs font-medium text-slate-600'

function numOrUndefined(raw: string): number | undefined {
  if (raw === '') return undefined
  const n = Number(raw)
  return Number.isNaN(n) ? undefined : n
}

function RangeField({
  label,
  minValue,
  maxValue,
  onMinChange,
  onMaxChange,
}: {
  label: string
  minValue: number | undefined
  maxValue: number | undefined
  onMinChange: (v: number | undefined) => void
  onMaxChange: (v: number | undefined) => void
}) {
  return (
    <div>
      <span className={labelClass}>{label}</span>
      <div className="flex items-center gap-2">
        <input
          type="number"
          placeholder="от"
          className={inputClass}
          value={minValue ?? ''}
          onChange={(e) => onMinChange(numOrUndefined(e.target.value))}
        />
        <span className="text-slate-400">–</span>
        <input
          type="number"
          placeholder="до"
          className={inputClass}
          value={maxValue ?? ''}
          onChange={(e) => onMaxChange(numOrUndefined(e.target.value))}
        />
      </div>
    </div>
  )
}

function CheckboxGroup({
  label,
  options,
  selected,
  onChange,
}: {
  label: string
  options: readonly { value: string; label: string }[]
  selected: string[] | undefined
  onChange: (next: string[] | undefined) => void
}) {
  const current = selected ?? []
  function toggle(value: string) {
    const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value]
    onChange(next.length > 0 ? next : undefined)
  }
  return (
    <div>
      <span className={labelClass}>{label}</span>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {options.map((option) => (
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
  )
}

export function SearchFilters({
  value,
  onChange,
  onSubmit,
  isSubmitting,
}: {
  value: SearchQuery
  onChange: (next: SearchQuery) => void
  onSubmit: () => void
  isSubmitting: boolean
}) {
  const { makes, isLoading: makesLoading } = useVehicleMakes()
  const makeOptions = Object.keys(makes).sort()
  const modelOptions = value.make ? (makes[value.make] ?? []).slice().sort() : []

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
      className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <span className={labelClass}>Марка</span>
          <select
            className={inputClass}
            disabled={makesLoading}
            value={value.make ?? ''}
            onChange={(e) => onChange({ ...value, make: e.target.value || undefined, models: undefined })}
          >
            <option value="">Все марки</option>
            {makeOptions.map((make) => (
              <option key={make} value={make}>
                {make}
              </option>
            ))}
          </select>
        </div>
        <div>
          <span className={labelClass}>Модель</span>
          <select
            className={inputClass}
            disabled={!value.make || modelOptions.length === 0}
            value={value.models?.[0] ?? ''}
            onChange={(e) => onChange({ ...value, models: e.target.value ? [e.target.value] : undefined })}
          >
            <option value="">Все модели</option>
            {modelOptions.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <RangeField
          label="Год"
          minValue={value.year_min}
          maxValue={value.year_max}
          onMinChange={(v) => onChange({ ...value, year_min: v })}
          onMaxChange={(v) => onChange({ ...value, year_max: v })}
        />
        <RangeField
          label="Цена, €"
          minValue={value.price_min}
          maxValue={value.price_max}
          onMinChange={(v) => onChange({ ...value, price_min: v })}
          onMaxChange={(v) => onChange({ ...value, price_max: v })}
        />
        <RangeField
          label="Пробег, км"
          minValue={value.mileage_min}
          maxValue={value.mileage_max}
          onMinChange={(v) => onChange({ ...value, mileage_min: v })}
          onMaxChange={(v) => onChange({ ...value, mileage_max: v })}
        />
        <RangeField
          label="Объём двигателя, см³"
          minValue={value.engine_volume_min}
          maxValue={value.engine_volume_max}
          onMinChange={(v) => onChange({ ...value, engine_volume_min: v })}
          onMaxChange={(v) => onChange({ ...value, engine_volume_max: v })}
        />
        <RangeField
          label="Мощность, л.с."
          minValue={value.power_min}
          maxValue={value.power_max}
          onMinChange={(v) => onChange({ ...value, power_min: v })}
          onMaxChange={(v) => onChange({ ...value, power_max: v })}
        />
        <div>
          <span className={labelClass}>Локация</span>
          <input
            type="text"
            className={inputClass}
            value={value.location ?? ''}
            onChange={(e) => onChange({ ...value, location: e.target.value || undefined })}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <CheckboxGroup
          label="Топливо"
          options={FUEL_TYPE_OPTIONS}
          selected={value.fuel_types}
          onChange={(v) => onChange({ ...value, fuel_types: v })}
        />
        <CheckboxGroup
          label="КПП"
          options={TRANSMISSION_OPTIONS}
          selected={value.transmissions}
          onChange={(v) => onChange({ ...value, transmissions: v })}
        />
        <CheckboxGroup
          label="Кузов"
          options={BODY_TYPE_OPTIONS}
          selected={value.body_types}
          onChange={(v) => onChange({ ...value, body_types: v })}
        />
      </div>

      <EquipmentFilter
        selected={value.equipment}
        onChange={(v) => onChange({ ...value, equipment: v })}
      />

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
      >
        Найти
      </button>
    </form>
  )
}
