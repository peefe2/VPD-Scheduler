import type { HourlyReading } from '../../api/types'
import { HOUR_MS, RECENT_HOURS as HOURS, localMs as ms, recentStart } from '../../lib/format'
import s from '../calendar/calendar.module.css'

const W = 320
const H = 168
const PAD = { l: 30, r: 8, t: 10, b: 22 }
const pad2 = (n: number) => String(n).padStart(2, '0')

// 마지막 정시까지 최근 24시간 VPD. 자정을 넘어도 이어서 그린다.
// 측정 없는 정시는 선을 끊는다 (보간하지 않음).
export function RecentChart({
  readings,
  end,
  low,
  high,
  daytime,
}: {
  readings: HourlyReading[]
  end: string
  low: number
  high: number
  daytime: [number, number]
}) {
  const start = recentStart(end)
  const hourOf = (i: number) => new Date(start + i * HOUR_MS).getHours()
  const points = readings
    .map((r) => ({ i: Math.round((ms(r.hour) - start) / HOUR_MS), v: r.vpd }))
    .filter((p) => p.i >= 0 && p.i < HOURS)

  const yMax = Math.max(high * 1.25, ...points.map((p) => p.v * 1.1), 0.5)
  const x = (i: number) => PAD.l + (i / (HOURS - 1)) * (W - PAD.l - PAD.r)
  const y = (v: number) => PAD.t + (1 - v / yMax) * (H - PAD.t - PAD.b)

  const segments: { i: number; v: number }[][] = []
  points.forEach((p, k) => {
    if (k === 0 || p.i !== points[k - 1].i + 1) segments.push([])
    segments.at(-1)!.push(p)
  })

  // 창이 자정을 넘으면 낮 구간이 둘로 나뉠 수 있다
  const dayRuns: [number, number][] = []
  for (let i = 0; i < HOURS; i++) {
    const h = hourOf(i)
    if (h < daytime[0] || h > daytime[1]) continue
    const last = dayRuns.at(-1)
    if (last && last[1] === i - 1) last[1] = i
    else dayRuns.push([i, i])
  }

  const color = (v: number) => (v < low ? 'var(--below)' : v > high ? 'var(--above)' : 'var(--brand-2)')

  return (
    <svg className={s.chart} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`최근 24시간 VPD, 적정 대역 ${low}~${high} kPa`}>
      {dayRuns.map(([a, b]) => (
        <rect
          key={a}
          x={x(a) - 4}
          y={PAD.t}
          width={x(b) - x(a) + 8}
          height={H - PAD.t - PAD.b}
          fill="var(--surface-muted)"
          opacity={0.55}
          rx={4}
        />
      ))}
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
      {[0, 6, 12, 18, 23].map((i) => (
        <text key={i} x={x(i)} y={H - 6} textAnchor="middle" className={s.chartAxis}>
          {pad2(hourOf(i))}
        </text>
      ))}
      {segments.map((seg, k) => (
        <polyline
          key={k}
          points={seg.map((p) => `${x(p.i)},${y(p.v)}`).join(' ')}
          fill="none"
          stroke="var(--ink-2)"
          strokeWidth={1.6}
          strokeLinejoin="round"
        />
      ))}
      {points.map((p) => (
        <circle key={p.i} cx={x(p.i)} cy={y(p.v)} r={3} fill={color(p.v)} stroke="#fff" strokeWidth={1}>
          <title>
            {pad2(hourOf(p.i))}시 · {p.v.toFixed(2)} kPa
          </title>
        </circle>
      ))}
    </svg>
  )
}
