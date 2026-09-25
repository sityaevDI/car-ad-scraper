import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { EmptyState, ErrorState } from '../components/StateMessage'
import { formatDate } from '../lib/format'
import { type RemovalBreakdownRow, type RemovalMetrics, type RemovalPeriod, marketApi } from '../lib/market'
import { DailyBarChart } from '../market/DailyBarChart'
import { useVehicleMakes } from '../search/useVehicleMakes'

const PERIODS: { value: RemovalPeriod; label: string; window: string }[] = [
  { value: 'day', label: 'День', window: 'за последние сутки' },
  { value: 'week', label: 'Неделя', window: 'за последние 7 дней' },
  { value: 'month', label: 'Месяц', window: 'за последние 30 дней' },
]

const numberFormat = new Intl.NumberFormat('ru-RU')

function formatEuro(value: number | null): string {
  return value === null ? '—' : `${numberFormat.format(value)} €`
}

function formatDays(value: number | null): string {
  return value === null ? '—' : `${numberFormat.format(Math.round(value))} дн.`
}

function formatShare(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function describeDelta(current: RemovalMetrics, previous: RemovalMetrics | null, periodLabel: string): string {
  if (!previous || previous.removed_count === 0) return 'Нет данных для сравнения с прошлым периодом'
  const pct = Math.round(((current.removed_count - previous.removed_count) / previous.removed_count) * 100)
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct}% к предыдущему периоду (${periodLabel}: ${numberFormat.format(previous.removed_count)})`
}

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

function BreakdownTable({ rows, byModel }: { rows: RemovalBreakdownRow[]; byModel: boolean }) {
  const max = Math.max(1, ...rows.map((row) => row.removed_count))
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2 font-medium">{byModel ? 'Модель' : 'Марка'}</th>
            <th className="px-4 py-2 font-medium">Снято</th>
            <th className="px-4 py-2 font-medium">Срок на рынке</th>
            <th className="px-4 py-2 font-medium">Медианная цена</th>
            <th className="px-4 py-2 font-medium">Снижали цену</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.make}/${row.model}`} className="border-b border-slate-100 last:border-0">
              <td className="px-4 py-2 font-medium text-slate-900">{byModel ? row.model : row.make}</td>
              <td className="px-4 py-2">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-24 rounded bg-slate-100">
                    <div
                      className="h-2 rounded bg-slate-700"
                      style={{ width: `${(row.removed_count / max) * 100}%` }}
                    />
                  </div>
                  <span className="tabular-nums text-slate-700">{numberFormat.format(row.removed_count)}</span>
                </div>
              </td>
              <td className="px-4 py-2 tabular-nums text-slate-700">{formatDays(row.median_days_on_market)}</td>
              <td className="px-4 py-2 tabular-nums text-slate-700">{formatEuro(row.median_price_at_removal)}</td>
              <td className="px-4 py-2 tabular-nums text-slate-700">{formatShare(row.price_cut_share)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function RemovedStatsPage() {
  const [period, setPeriod] = useState<RemovalPeriod>('week')
  const [make, setMake] = useState('')
  const { makes, isLoading: makesLoading } = useVehicleMakes()

  const query = useQuery({
    queryKey: ['removal-stats', period, make],
    queryFn: () => marketApi.getRemovalStats(period, make || undefined),
    placeholderData: keepPreviousData,
  })

  const periodInfo = PERIODS.find((p) => p.value === period) ?? PERIODS[1]
  const data = query.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Статистика снятых объявлений</h1>
        <p className="mt-1 text-sm text-slate-600">
          Сколько объявлений пропало с площадки, как долго они висели и как менялась цена перед этим.
        </p>
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        «Снято» — не то же самое, что «продано»: объявление могло исчезнуть, потому что продавец его закрыл. Это
        оценка спроса, а не подтверждённые продажи. «Срок на рынке» — сколько мы видели объявление, а не сколько оно
        реально висело на площадке.
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="inline-flex overflow-hidden rounded-md border border-slate-300 bg-white text-sm shadow-sm">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => setPeriod(p.value)}
              aria-pressed={period === p.value}
              className={`px-4 py-1.5 font-medium ${
                period === p.value ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Марка</span>
          <select
            className="rounded-md border border-slate-300 px-2.5 py-1.5 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            disabled={makesLoading}
            value={make}
            onChange={(e) => setMake(e.target.value)}
          >
            <option value="">Все марки</option>
            {Object.keys(makes)
              .sort()
              .map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
          </select>
        </label>
      </div>

      {query.isLoading ? (
        <div className="h-64 animate-pulse rounded-lg border border-slate-200 bg-slate-100" />
      ) : query.isError ? (
        <ErrorState message="Не удалось загрузить статистику." onRetry={() => query.refetch()} />
      ) : !data || !data.current || !data.as_of ? (
        <EmptyState message="Статистика ещё не рассчитана — она обновляется два раза в день." />
      ) : (
        <>
          <p className="text-sm text-slate-600">
            {make || 'Все марки'}, {periodInfo.window} по {formatDate(data.as_of)} (полные сутки, UTC).
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Снято объявлений"
              value={numberFormat.format(data.current.removed_count)}
              hint={describeDelta(data.current, data.previous, periodInfo.label.toLowerCase())}
            />
            <StatTile
              label="Медианный срок на рынке"
              value={formatDays(data.current.median_days_on_market)}
              hint="От первого до последнего момента, когда мы видели объявление"
            />
            <StatTile
              label="Медианная цена при снятии"
              value={formatEuro(data.current.median_price_at_removal)}
            />
            <StatTile
              label="Снижали цену до снятия"
              value={formatShare(data.current.price_cut_share)}
              hint={
                data.current.median_price_cut_pct === null
                  ? undefined
                  : `Медианное снижение — ${data.current.median_price_cut_pct}%`
              }
            />
          </div>

          {data.series.length > 0 && (
            <section>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">Снятые объявления по дням</h2>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <DailyBarChart series={data.series} />
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">
              {make ? `Модели ${make}` : 'Марки'} — чаще всего снимают
            </h2>
            {data.breakdown.length > 0 ? (
              <BreakdownTable rows={data.breakdown} byModel={Boolean(make)} />
            ) : (
              <EmptyState
                message={
                  make
                    ? 'Слишком мало снятых объявлений по отдельным моделям — нужно хотя бы 3 на модель.'
                    : 'За этот период нет снятых объявлений.'
                }
              />
            )}
          </section>

          {data.computed_at && (
            <p className="text-xs text-slate-500">
              Обновлено {new Date(data.computed_at).toLocaleString('ru-RU')}
            </p>
          )}
        </>
      )}
    </div>
  )
}
