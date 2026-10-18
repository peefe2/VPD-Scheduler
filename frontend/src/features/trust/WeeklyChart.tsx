import type { Bucket } from '../../api/types'
import { shortDate, signedPct } from '../../lib/format'
import s from './trust.module.css'

const H = 220
const PAD = { l: 44, r: 10, t: 14, b: 34 }
const LEARNING = 2 // 처음 두 버킷(14일)은 판정에서 뺀다

// 주간(비중첩 7일 버킷) 개선율 막대. 모델 사용 상태였던 주는 배경을 칠한다.
export function WeeklyChart({ buckets }: { buckets: Bucket[] }) {
  const W = Math.max(560, PAD.l + PAD.r + buckets.length * 30)
  const vals = buckets.map((b) => b.improvement_pct ?? 0)
  const lim = Math.max(10, ...vals.map((v) => Math.ceil(Math.abs(v) / 10) * 10))
  const innerW = W - PAD.l - PAD.r
  const bw = innerW / Math.max(buckets.length, 1)
  const y = (v: number) => PAD.t + ((lim - v) / (2 * lim)) * (H - PAD.t - PAD.b)
  const ticks = [-lim, -lim / 2, 0, lim / 2, lim]

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg
        className={s.chart}
        viewBox={`0 0 ${W} ${H}`}
        style={{ minWidth: W }}
        role="img"
        aria-label="주간 persistence 대비 RMSE 개선율"
      >
        {buckets.map((b, i) =>
          b.state_after === 'model' ? (
            <rect key={`m${i}`} x={PAD.l + i * bw} y={PAD.t} width={bw} height={H - PAD.t - PAD.b} fill="var(--brand-soft)" opacity={0.6} />
          ) : null,
        )}
        {LEARNING > 0 && buckets.length > 0 && (
          <rect
            x={PAD.l}
            y={PAD.t}
            width={Math.min(LEARNING, buckets.length) * bw}
            height={H - PAD.t - PAD.b}
            fill="var(--surface-muted)"
            opacity={0.7}
          />
        )}
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={y(t)}
              y2={y(t)}
              stroke={t === 0 ? 'var(--ink-3)' : 'var(--line)'}
              strokeWidth={t === 0 ? 1.2 : 1}
            />
            <text x={PAD.l - 6} y={y(t) + 3.5} textAnchor="end" className={s.axis}>
              {t > 0 ? '+' : ''}
              {t}%
            </text>
          </g>
        ))}
        {buckets.map((b, i) => {
          const cx = PAD.l + i * bw + bw / 2
          const barW = Math.min(18, bw * 0.6)
          const label = (
            <title>
              {i + 1}주차 ({shortDate(b.start)}~) · {b.verdict === 'insufficient' ? `판정 불가 (표본 ${b.n})` : signedPct(b.improvement_pct)}
              {i < LEARNING ? ' · 학습 기간' : ''}
            </title>
          )
          if (b.improvement_pct == null) {
            return (
              <g key={i}>
                <rect x={cx - barW / 2} y={y(0) - 3} width={barW} height={6} rx={2} fill="none" stroke="var(--ink-4)" strokeDasharray="2 2" />
                {label}
              </g>
            )
          }
          const v = b.improvement_pct
          const fill = i < LEARNING ? 'var(--ink-4)' : v > 0 ? 'var(--brand-2)' : 'var(--above)'
          return (
            <g key={i}>
              <rect x={cx - barW / 2} y={Math.min(y(v), y(0))} width={barW} height={Math.max(1.5, Math.abs(y(v) - y(0)))} rx={3} fill={fill} />
              {label}
            </g>
          )
        })}
        {buckets.map((_, i) =>
          i % Math.ceil(buckets.length / 12) === 0 ? (
            <text key={`x${i}`} x={PAD.l + i * bw + bw / 2} y={H - 12} textAnchor="middle" className={s.axis}>
              {i + 1}주
            </text>
          ) : null,
        )}
      </svg>
      <div className={s.chartLegend}>
        <span>
          <i style={{ background: 'var(--brand-2)' }} />
          persistence보다 나음
        </span>
        <span>
          <i style={{ background: 'var(--above)' }} />
          못함
        </span>
        <span>
          <i style={{ background: 'var(--ink-4)' }} />
          학습 기간(판정 제외)
        </span>
        <span>
          <i style={{ border: '1px dashed var(--ink-4)' }} />
          판정 불가(표본 부족)
        </span>
        <span>
          <i style={{ background: 'var(--brand-soft)' }} />
          모델 사용 중이던 주
        </span>
      </div>
    </div>
  )
}
