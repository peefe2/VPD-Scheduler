import type { CalendarDay } from '../../api/types'
import { monthRange, pct, WEEKDAYS } from '../../lib/format'
import s from './calendar.module.css'
import { level, LEVELS } from './scale'

export function MonthGrid({
  month,
  days,
  selected,
  onSelect,
}: {
  month: string
  days: Map<string, CalendarDay>
  selected: string | null
  onSelect: (date: string) => void
}) {
  const { days: count } = monthRange(month)
  const firstWeekday = new Date(`${month}-01T00:00:00Z`).getUTCDay()
  const cells = Array.from({ length: count }, (_, i) => `${month}-${String(i + 1).padStart(2, '0')}`)

  return (
    <div>
      <div className={s.weekdays} aria-hidden="true">
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className={s.grid}>
        {Array.from({ length: firstWeekday }, (_, i) => (
          <span key={`pad-${i}`} className={s.pad} />
        ))}
        {cells.map((date) => {
          const d = days.get(date)
          const dayNum = Number(date.slice(8))
          if (!d) {
            return (
              <div key={date} className={s.cell} data-empty="true" aria-label={`${dayNum}일 관측 없음`}>
                <span className={s.dayNum}>{dayNum}</span>
              </div>
            )
          }
          const insufficient = !d.daytime.sufficient
          // 밤은 경고 배지 대신 과습 비율을 항상 숫자로 (2026-10-31). 밤 관측 10시간 미만이면 표시 안 함
          const night = d.night.sufficient ? pct(d.night.below_ratio) : null
          const label =
            (insufficient ? `${dayNum}일, 낮 데이터 부족` : `${dayNum}일, 낮 대역 안 ${pct(d.daytime.in_band_ratio)}`) +
            (night ? `, 밤 과습 ${night}` : ', 밤 데이터 부족')
          return (
            <button
              key={date}
              type="button"
              className={s.cell}
              data-level={insufficient ? undefined : level(d.daytime.in_band_ratio)}
              data-insufficient={insufficient}
              aria-pressed={selected === date}
              aria-label={label}
              onClick={() => onSelect(date)}
            >
              <span className={s.dayNum}>{dayNum}</span>
              <span className={s.cellBody}>
                <span className={s.cellFoot}>
                  {insufficient ? (
                    <span className={s.cellNote}>데이터 부족</span>
                  ) : (
                    <>
                      <span className={s.cellPct}>{pct(d.daytime.in_band_ratio)}</span>
                      <span className={s.cellNote}>
                        {d.daytime.hours_in_band}/{d.daytime.hours_observed}h
                      </span>
                    </>
                  )}
                </span>
                <span className={s.nightLine} aria-hidden="true">
                  밤 {night ?? '–'}
                </span>
              </span>
            </button>
          )
        })}
      </div>

      <div className={s.legend}>
        <span className={s.legendScale}>
          낮 대역 안
          {LEVELS.map((l, i) => (
            <i key={l.label} style={{ background: `var(--scale-${i})` }} title={l.label} />
          ))}
          <span className="mono">0 → 100%</span>
        </span>
        <span className={s.legendItem}>
          <span className="mono">밤 87%</span> = 그날 밤(0~8시, 18~23시) 중 대역 아래(과습)였던 비율 · 관측 10시간
          미만은 –
        </span>
        <span className={s.legendItem}>
          <span className={s.swatchHatch} aria-hidden="true" />낮 관측 6시간 미만
        </span>
      </div>
    </div>
  )
}
