import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useCalendar, useGreenhouse } from '../../api/hooks'
import { Icon } from '../../components/Icon'
import { ReplayNotice } from '../../components/ReplayNotice'
import { ButtonLink, Card, Empty, ErrorState, IconButton, Loading, PageHeader, Stat } from '../../components/ui'
import { monthKey, pct } from '../../lib/format'
import { summarize } from '../../lib/summary'
import s from './calendar.module.css'
import { DayDetail } from './DayDetail'
import { MonthGrid } from './MonthGrid'

export function CalendarPage({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  // 이력 전체를 한 번 받아 월별로 나눈다 (하루 1행이라 수백 행 수준)
  const { data: cal, isLoading, error } = useCalendar(id)
  const [params, setParams] = useSearchParams()
  const [selected, setSelected] = useState<string | null>(null)

  const byDate = useMemo(() => new Map(cal?.days.map((d) => [d.date, d]) ?? []), [cal])
  const months = useMemo(() => [...new Set(cal?.days.map((d) => monthKey(d.date)) ?? [])].sort(), [cal])

  if (isLoading) return <Loading />
  if (error) return <ErrorState error={error} />
  if (!cal || cal.days.length === 0) {
    return (
      <>
        <PageHeader title="VPD 캘린더" sub={gh?.name} />
        <Card>
          <Empty
            title="아직 데이터가 없습니다"
            action={<ButtonLink to={`/g/${id}/setup/data`}>CSV 올리기</ButtonLink>}
          >
            이력을 올리면 날짜별로 적정 대역 안에 있던 시간을 보여줍니다.
          </Empty>
        </Card>
      </>
    )
  }

  const month = params.get('month') && months.includes(params.get('month')!) ? params.get('month')! : months.at(-1)!
  const monthDays = cal.days.filter((d) => monthKey(d.date) === month)
  const sum = summarize(monthDays)
  const [y, m] = month.split('-').map(Number)
  // 데이터가 있는 달만 오간다 (중간에 빈 달은 건너뜀)
  const go = (delta: number) => {
    const next = months[months.indexOf(month) + delta]
    if (!next) return
    setSelected(null)
    setParams({ month: next })
  }

  // 한 줄로 쌓이는 폭에서는 상세가 달력 아래에 있어, 눌러도 변화가 안 보이지 않게 내려 준다
  const select = (date: string) => {
    setSelected(date)
    if (window.matchMedia('(max-width: 1080px)').matches) {
      requestAnimationFrame(() => document.querySelector(`.${s.detail}`)?.scrollIntoView({ behavior: 'smooth' }))
    }
  }

  return (
    <>
      <PageHeader
        title="VPD 캘린더"
        sub={`${gh?.name} · 적정 대역 ${cal.band.low}~${cal.band.high} kPa${
          cal.bands.length > 1 ? ' · 대역을 바꾼 적이 있어 날짜마다 그때 대역으로 판정합니다' : ''
        }`}
        actions={
          <div className={s.monthNav}>
            <IconButton label="이전 달" onClick={() => go(-1)} disabled={month === months[0]}>
              <Icon name="left" />
            </IconButton>
            <span className={s.monthLabel} aria-live="polite">
              {y}년 {m}월
            </span>
            <IconButton label="다음 달" onClick={() => go(1)} disabled={month === months.at(-1)}>
              <Icon name="right" />
            </IconButton>
          </div>
        }
      />

      {gh?.connection_type === 'replay' && (
        <div style={{ marginBottom: 16 }}>
          <ReplayNotice gh={gh} />
        </div>
      )}

      <div className={s.stats}>
        <Stat label="낮 대역 안" value={pct(sum.dayInBand)} foot={`09~17시 관측 ${sum.dayObserved}시간 기준`} />
        <Stat label="낮 대역 아래 (과습)" value={pct(sum.dayBelow)} foot={`대역 위 ${pct(sum.dayAbove)}`} />
        <Stat label="밤 대역 아래" value={pct(sum.nightBelow)} foot="밤 15시간 기준" />
        <Stat label="판단 가능한 날" value={sum.sufficientDays} unit={`/ ${sum.days}일`} foot="낮 관측 6시간 이상" />
      </div>

      <div className={s.layout}>
        <Card title={`${m}월`} sub="칸 색은 낮(09~17시)에 적정 대역 안에 있던 비율입니다.">
          <MonthGrid month={month} days={byDate} selected={selected} onSelect={select} />
        </Card>
        <DayDetail id={id} day={selected ? byDate.get(selected) : undefined} cal={cal} />
      </div>
    </>
  )
}
