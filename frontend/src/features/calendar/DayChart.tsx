import type { HourlyReading } from '../../api/types'
import s from './calendar.module.css'

const W = 320
const H = 168
const PAD = { l: 30, r: 8, t: 10, b: 22 }

// 하루 24시간 VPD. 측정 없는 정시는 선을 끊는다 (보간하지 않음).
export function DayChart({
  readings,
  low,
  high,
  daytime,
}: {
  readings: HourlyReading[]
  low: number
  high: number
  daytime: [number, number]
}) {
  const yMax = Math.max(high * 1.25, ...readings.map((r) => r.vpd * 1.1), 0.5)
  const x = (h: number) => PAD.l + (h / 23) * (W - PAD.l - PAD.r)
  const y = (v: number) => PAD.t + (1 - v / yMax) * (H - PAD.t - PAD.b)
  const points = readings.map((r) => ({ h: Number(r.hour.slice(11, 13)), v: r.vpd }))

  const segments: { h: number; v: number }[][] = []
  points.forEach((p, i) => {
    if (i === 0 || p.h !== points[i - 1].h + 1) segments.push([])
    segments.at(-1)!.push(p)
  })

  const color = (v: number) => (v < low ? 'var(--below)' : v > high ? 'var(--above)' : 'var(--brand-2)')

  return (
    <svg className={s.chart} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`시간별 VPD, 적정 대역 ${low}~${high} kPa`}>
      <rect
        x={x(daytime[0]) - 4}
        y={PAD.t}
        width={x(daytime[1]) - x(daytime[0]) + 8}
        height={H - PAD.t - PAD.b}
        fill="var(--surface-muted)"
        opacity={0.55}
        rx={4}
      />
      <rect x={PAD.l} y={y(high)} width={W - PAD.l - PAD.r} height={y(low) - y(high)} fill="var(--brand-soft)" opacity={0.85} />
      {[low, high].map((v) => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke="var(--brand-2)" strokeDasharray="3 3" strokeWidth={1} />
          <text x={PAD.l - 5} y={y(v) + 3} textAnchor="end" className={s.chartAxis}>
            {v}
          </text>
        </g>
      ))}
      <text x={PAD.l - 5} y={y(0) + 3} textAnchor="end" className={s.chartAxis}>
        0
      </text>
      <line x1={PAD.l} x2={W - PAD.r} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" />
      {[0, 6, 12, 18, 23].map((h) => (
        <text key={h} x={x(h)} y={H - 6} textAnchor="middle" className={s.chartAxis}>
          {String(h).padStart(2, '0')}
        </text>
      ))}
      {segments.map((seg, i) => (
        <polyline
          key={i}
          points={seg.map((p) => `${x(p.h)},${y(p.v)}`).join(' ')}
          fill="none"
          stroke="var(--ink-2)"
          strokeWidth={1.6}
          strokeLinejoin="round"
        />
      ))}
      {points.map((p) => (
        <circle key={p.h} cx={x(p.h)} cy={y(p.v)} r={3} fill={color(p.v)} stroke="#fff" strokeWidth={1}>
          <title>
            {String(p.h).padStart(2, '0')}시 · {p.v.toFixed(2)} kPa
          </title>
        </circle>
      ))}
    </svg>
  )
}
