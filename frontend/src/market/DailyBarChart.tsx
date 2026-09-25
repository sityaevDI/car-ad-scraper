import type { RemovalSeriesPoint } from '../lib/market'

const WIDTH = 720
const HEIGHT = 180
const PAD = { top: 12, right: 8, bottom: 24, left: 32 }

function shortDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', timeZone: 'UTC' })
}

export function DailyBarChart({ series }: { series: RemovalSeriesPoint[] }) {
  const max = Math.max(1, ...series.map((p) => p.removed_count))
  const plotWidth = WIDTH - PAD.left - PAD.right
  const plotHeight = HEIGHT - PAD.top - PAD.bottom
  const slot = plotWidth / series.length
  const barWidth = Math.max(2, slot - 3)

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Снятые объявления по дням" className="w-full">
      {[0, 0.5, 1].map((fraction) => {
        const y = PAD.top + plotHeight * (1 - fraction)
        return (
          <g key={fraction}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y} y2={y} className="stroke-slate-200" />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" className="fill-slate-500 text-[10px]">
              {Math.round(max * fraction)}
            </text>
          </g>
        )
      })}
      {series.map((point, i) => {
        const height = (point.removed_count / max) * plotHeight
        return (
          <rect
            key={point.date}
            x={PAD.left + i * slot + (slot - barWidth) / 2}
            y={PAD.top + plotHeight - height}
            width={barWidth}
            height={height}
            rx={1.5}
            className="fill-slate-700 hover:fill-slate-900"
          >
            <title>{`${shortDate(point.date)}: ${point.removed_count}`}</title>
          </rect>
        )
      })}
      <text x={PAD.left} y={HEIGHT - 6} className="fill-slate-500 text-[10px]">
        {shortDate(series[0].date)}
      </text>
      <text x={WIDTH - PAD.right} y={HEIGHT - 6} textAnchor="end" className="fill-slate-500 text-[10px]">
        {shortDate(series[series.length - 1].date)}
      </text>
    </svg>
  )
}
