import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState, ErrorState } from '../components/StateMessage'
import i18n, { intlLocale } from '../i18n'
import { formatDate } from '../lib/format'
import { type RemovalBreakdownRow, type RemovalMetrics, type RemovalPeriod, marketApi } from '../lib/market'
import { DailyBarChart } from '../market/DailyBarChart'
import { useVehicleMakes } from '../search/useVehicleMakes'

const PERIODS: RemovalPeriod[] = ['day', 'week', 'month']

const numberFormat = { format: (value: number) => new Intl.NumberFormat(intlLocale()).format(value) }

function formatEuro(value: number | null): string {
  return value === null ? '—' : `${numberFormat.format(value)} €`
}

function formatDays(value: number | null): string {
  return value === null ? '—' : i18n.t('stats.days', { value: numberFormat.format(Math.round(value)) })
}

function formatShare(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function describeDelta(current: RemovalMetrics, previous: RemovalMetrics | null, periodLabel: string): string {
  if (!previous || previous.removed_count === 0) return i18n.t('stats.noCompare')
  const pct = Math.round(((current.removed_count - previous.removed_count) / previous.removed_count) * 100)
  const sign = pct > 0 ? '+' : ''
  return i18n.t('stats.delta', { sign, pct, period: periodLabel, prev: numberFormat.format(previous.removed_count) })
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
  const { t } = useTranslation()
  const max = Math.max(1, ...rows.map((row) => row.removed_count))
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2 font-medium">{byModel ? t('stats.colModel') : t('stats.colMake')}</th>
            <th className="px-4 py-2 font-medium">{t('stats.colRemoved')}</th>
            <th className="px-4 py-2 font-medium">{t('stats.colDays')}</th>
            <th className="px-4 py-2 font-medium">{t('stats.colMedianPrice')}</th>
            <th className="px-4 py-2 font-medium">{t('stats.colPriceCut')}</th>
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
  const { t } = useTranslation()
  const [period, setPeriod] = useState<RemovalPeriod>('week')
  const [make, setMake] = useState('')
  const { makes, isLoading: makesLoading } = useVehicleMakes()

  const query = useQuery({
    queryKey: ['removal-stats', period, make],
    queryFn: () => marketApi.getRemovalStats(period, make || undefined),
    placeholderData: keepPreviousData,
  })

  const data = query.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t('stats.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">
          {t('stats.intro')}
        </p>
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {t('stats.disclaimer')}
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="inline-flex overflow-hidden rounded-md border border-slate-300 bg-white text-sm shadow-sm">
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPeriod(p)}
              aria-pressed={period === p}
              className={`px-4 py-1.5 font-medium ${
                period === p ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              {t(`stats.periods.${p}.label`)}
            </button>
          ))}
        </div>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">{t('stats.make')}</span>
          <select
            className="rounded-md border border-slate-300 px-2.5 py-1.5 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            disabled={makesLoading}
            value={make}
            onChange={(e) => setMake(e.target.value)}
          >
            <option value="">{t('stats.allMakes')}</option>
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
        <ErrorState message={t('stats.loadFailed')} onRetry={() => query.refetch()} />
      ) : !data || !data.current || !data.as_of ? (
        <EmptyState message={t('stats.notComputed')} />
      ) : (
        <>
          <p className="text-sm text-slate-600">
            {t('stats.summary', {
              make: make || t('stats.allMakes'),
              window: t(`stats.periods.${period}.window`),
              date: formatDate(data.as_of),
            })}
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label={t('stats.tileRemoved')}
              value={numberFormat.format(data.current.removed_count)}
              hint={describeDelta(data.current, data.previous, t(`stats.periods.${period}.label`).toLowerCase())}
            />
            <StatTile
              label={t('stats.tileDays')}
              value={formatDays(data.current.median_days_on_market)}
              hint={t('stats.tileDaysHint')}
            />
            <StatTile
              label={t('stats.tileMedianPrice')}
              value={formatEuro(data.current.median_price_at_removal)}
            />
            <StatTile
              label={t('stats.tileCut')}
              value={formatShare(data.current.price_cut_share)}
              hint={
                data.current.median_price_cut_pct === null
                  ? undefined
                  : t('stats.tileCutHint', { pct: data.current.median_price_cut_pct })
              }
            />
          </div>

          {data.series.length > 0 && (
            <section>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">{t('stats.byDay')}</h2>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <DailyBarChart series={data.series} />
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">
              {make ? t('stats.topModels', { make }) : t('stats.topMakes')}
            </h2>
            {data.breakdown.length > 0 ? (
              <BreakdownTable rows={data.breakdown} byModel={Boolean(make)} />
            ) : (
              <EmptyState
                message={
                  make
                    ? t('stats.fewModels')
                    : t('stats.noneRemoved')
                }
              />
            )}
          </section>

          {data.computed_at && (
            <p className="text-xs text-slate-500">
              {t('stats.updated', { date: new Date(data.computed_at).toLocaleString(intlLocale()) })}
            </p>
          )}
        </>
      )}
    </div>
  )
}
