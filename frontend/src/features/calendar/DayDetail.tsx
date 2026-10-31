import { useReadings } from '../../api/hooks'
import type { CalendarDay, CalendarResponse } from '../../api/types'
import { Card, Empty, Loading } from '../../components/ui'
import { hintClass } from '../../components/classes'
import { kpa, pct, WEEKDAYS } from '../../lib/format'
import s from './calendar.module.css'
import { DayChart } from './DayChart'

function PartBar({
  title,
  part,
  total,
  minHours,
  emphasis,
}: {
  title: string
  part: { hours_observed: number; hours_in_band: number; hours_below: number; hours_above: number; sufficient: boolean }
  total: number
  minHours: number
  emphasis: 'band' | 'below'
}) {
  const w = (n: number) => `${(n / total) * 100}%`
  const headLabel = emphasis === 'band' ? '대역 안' : '과습'
  const headValue =
    part.hours_observed === 0
      ? '–'
      : pct((emphasis === 'band' ? part.hours_in_band : part.hours_below) / part.hours_observed)
  return (
    <div className={s.part}>
      <div className={s.partHead}>
        <span>{title}</span>
        <span>
          {headLabel} <span className="mono">{headValue}</span>
        </span>
      </div>
      <div className={s.bar} aria-hidden="true">
        <span style={{ width: w(part.hours_below), background: 'var(--below)' }} />
        <span style={{ width: w(part.hours_in_band), background: 'var(--brand-2)' }} />
        <span style={{ width: w(part.hours_above), background: 'var(--above)' }} />
      </div>
      <div className={s.partLegend}>
        <span>
          아래 <b>{part.hours_below}h</b>
        </span>
        <span>
          안 <b>{part.hours_in_band}h</b>
        </span>
        <span>
          위 <b>{part.hours_above}h</b>
        </span>
        <span>
          관측 <b>{part.hours_observed}</b>/{total}h
        </span>
      </div>
      {!part.sufficient && (
        <p className={hintClass}>관측이 {minHours}시간 미만이라 판단 근거가 부족합니다.</p>
      )}
    </div>
  )
}

export function DayDetail({ id, day, cal }: { id: number; day: CalendarDay | undefined; cal: CalendarResponse }) {
  const { data: readings, isLoading } = useReadings(id, day?.date ?? null)

  if (!day) {
    return (
      <Card title="날짜 상세">
        <Empty title="날짜를 고르세요">캘린더에서 날짜를 누르면 그날의 시간별 VPD를 보여줍니다.</Empty>
      </Card>
    )
  }

  const date = new Date(`${day.date}T00:00:00Z`)
  const title = `${date.getUTCMonth() + 1}월 ${date.getUTCDate()}일 (${WEEKDAYS[date.getUTCDay()]})`

  return (
    <div className={s.detail}>
      <Card title={title} sub={`VPD ${kpa(day.vpd_min)} ~ ${kpa(day.vpd_max)} kPa · 평균 ${kpa(day.vpd_mean)}`}>
        {isLoading || !readings ? (
          <Loading />
        ) : (
          <DayChart readings={readings} low={day.band.low} high={day.band.high} daytime={cal.daytime_hours} />
        )}
        <p className={hintClass} style={{ marginTop: 8 }}>
          회색 띠는 낮(09~17시), 초록 띠는 그날의 적정 대역({day.band.low}~{day.band.high} kPa)입니다. 측정이 없는
          정시는 선을 끊었습니다.
        </p>
      </Card>
      <Card title="낮과 밤">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <PartBar title="낮 09~17시" part={day.daytime} total={9} minHours={cal.min_hours.daytime} emphasis="band" />
          <PartBar title="밤" part={day.night} total={15} minHours={cal.min_hours.night} emphasis="below" />
        </div>
      </Card>
    </div>
  )
}
