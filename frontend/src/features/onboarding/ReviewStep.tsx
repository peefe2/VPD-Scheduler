import { useBacktest, useCalendar, useGreenhouse } from '../../api/hooks'
import { StateBadge } from '../../components/StateBadge'
import { Badge, ButtonLink, Card, ErrorState, Loading, Notice, PageHeader } from '../../components/ui'
import { hintClass, tableClass, tableWrapClass } from '../../components/classes'
import { day, daysBetween, num, pct, signedPct } from '../../lib/format'
import { connectionLabel, STATE } from '../../lib/labels'
import { summarize } from '../../lib/summary'
import s from './onboarding.module.css'
import { Steps } from './Steps'

export function ReviewStep({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  const bt = useBacktest(id)
  const cal = useCalendar(id)

  if (bt.isLoading || cal.isLoading || !gh) return <Loading label="이력으로 백테스트를 계산하는 중" />
  if (bt.error) return <ErrorState error={bt.error} />
  if (cal.error) return <ErrorState error={cal.error} />
  const backtest = bt.data!
  const sum = summarize(cal.data!.days)

  const span = backtest.history_start && backtest.history_end ? daysBetween(backtest.history_start, backtest.history_end) : 0
  const coverage = span > 0 ? backtest.hours / (span * 24) : 0

  return (
    <>
      <PageHeader title={`이력 확인과 시작 · ${gh.name}`} sub="온보딩 3/3 · 이력 점검과 시작 상태" />
      <Steps current={3} ghId={id} />

      <div className={s.grid}>
        <div className={s.col}>
          <Card title="이력 점검">
            <div className={tableWrapClass}>
              <table className={tableClass}>
                <tbody>
                  <tr>
                    <th scope="row">이력 기간</th>
                    <td className="mono">
                      {day(backtest.history_start)} ~ {day(backtest.history_end)} · {span}일
                    </td>
                    <td>{span >= 14 ? <Badge tone="brand">14일 이상</Badge> : <Badge tone="info">14일 미만</Badge>}</td>
                  </tr>
                  <tr>
                    <th scope="row">정시 관측</th>
                    <td className="mono">
                      {num(span * 24)}시간 중 {num(backtest.hours)}시간 · {pct(coverage)}
                    </td>
                    <td />
                  </tr>
                  <tr>
                    <th scope="row">CO2</th>
                    <td>{gh.has_co2 ? '연결됨' : '없음 — 모델 예측은 쓰지 않습니다'}</td>
                    <td>{gh.has_co2 ? <Badge tone="brand">연결됨</Badge> : <Badge tone="warn">없음</Badge>}</td>
                  </tr>
                  <tr>
                    <th scope="row">낮 대역 안</th>
                    <td className="mono">
                      {pct(sum.dayInBand, 1)} · 아래 {pct(sum.dayBelow)} · 위 {pct(sum.dayAbove)}
                    </td>
                    <td>
                      <span className="muted mono">
                        {gh.vpd_low}~{gh.vpd_high} kPa
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className={hintClass} style={{ marginTop: 12 }}>
              낮은 09~17시 기준입니다. 대역 아래(과습) 비율이 높게 나오는 건 오류가 아니라 이력 그대로입니다. 대역은 작물과
              시기에 맞는지로 정하고, 이력이 잘 나오게 맞추지는 마세요.
            </p>
          </Card>

          <Card title="백테스트와 시작 상태" sub="persistence(현재 값을 그대로 쓰는 방법)와 주 단위로 비교합니다.">
            {backtest.model_set !== 'deployed' && (
              <div style={{ marginBottom: 14 }}>
                <Notice tone="brand">
                  데모 모드: <strong>{backtest.model_set.replace('loso:', '')}</strong>을(를) 학습에서 뺀 모델로 계산했습니다.
                </Notice>
              </div>
            )}
            <div className={tableWrapClass}>
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th>지평</th>
                    <th className="num">판정한 주</th>
                    <th className="num">최근 주 개선율</th>
                    <th>시작 상태</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.horizons.map((h) => {
                    const judged = h.buckets.filter((b) => b.index >= 2 && b.verdict !== 'insufficient')
                    const last = judged.at(-1)
                    return (
                      <tr key={h.horizon}>
                        <td className="mono">+{h.horizon}h</td>
                        <td className="num">{judged.length}</td>
                        <td className="num">{signedPct(last?.improvement_pct)}</td>
                        <td>
                          <StateBadge state={h.state} />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className={hintClass} style={{ marginTop: 12 }}>
              처음 14일은 학습 기간이라 판정하지 않습니다. 그 뒤 3주 연속 persistence보다 나으면 모델로 전환하고, 한 주라도
              못하면 바로 되돌아갑니다. 그래서 전환은 빨라야 35일째입니다.
            </p>
            {!gh.has_co2 && (
              <div style={{ marginTop: 12 }}>
                <Notice tone="warn">{STATE.no_co2.desc}</Notice>
              </div>
            )}
          </Card>
        </div>

        <aside className={s.col}>
          <Card title="시작 전 확인">
            <ul className={s.list}>
              <li>
                <span className={s.listKey}>온실 · 작물</span>
                <span className={s.listVal}>
                  {gh.name} · {gh.crop}
                </span>
              </li>
              <li>
                <span className={s.listKey}>적정 대역 · 연결 방식</span>
                <span className={s.listVal}>
                  {gh.vpd_low}~{gh.vpd_high} kPa · {connectionLabel(gh.connection_type)}
                </span>
              </li>
              <li>
                <span className={s.listKey}>지금 쓸 수 있는 화면</span>
                <span className={s.listVal}>캘린더 · 모델 신뢰도</span>
              </li>
              <li>
                <span className={s.listKey}>수집 API가 필요한 화면</span>
                <span className={s.listVal}>오늘 · AI 어드바이저</span>
              </li>
            </ul>
          </Card>
          <div className={s.actions}>
            <ButtonLink to={`/g/${id}/setup/data`} variant="secondary">
              이전
            </ButtonLink>
            <ButtonLink to={`/g/${id}/calendar`}>시작하기</ButtonLink>
          </div>
        </aside>
      </div>
    </>
  )
}
