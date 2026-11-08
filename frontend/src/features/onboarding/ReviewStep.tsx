import { useBacktest, useCalendar, useGreenhouse } from '../../api/hooks'
import { StateBadge } from '../../components/StateBadge'
import { ButtonLink, Card, ErrorState, Loading, Notice, PageHeader, Stat } from '../../components/ui'
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
  // 실시간 값이 들어오는 연결이어야 오늘·어드바이저 화면이 채워진다
  const live = gh.connection_type !== 'csv'

  return (
    <>
      <PageHeader title={`이력 확인과 시작 · ${gh.name}`} sub="올린 이력을 점검하고 시작 상태를 확인합니다." />
      <Steps current={3} ghId={id} />

      <div className={s.grid}>
        <div className={s.col}>
          <Card title="이력 점검">
            <div className={s.review}>
              <Stat
                label="이력 기간"
                value={span}
                unit="일"
                foot={`${day(backtest.history_start)} ~ ${day(backtest.history_end)} · ${span >= 14 ? '판정 가능' : '14일부터 판정'}`}
              />
              <Stat
                label="정시 관측"
                value={pct(coverage)}
                foot={`${num(span * 24)}시간 중 ${num(backtest.hours)}시간`}
              />
              <Stat
                label="낮 대역 안"
                value={pct(sum.dayInBand, 1)}
                foot={`아래 ${pct(sum.dayBelow)} · 위 ${pct(sum.dayAbove)} · ${gh.vpd_low}~${gh.vpd_high} kPa`}
              />
              <Stat
                label="CO2"
                value={gh.has_co2 ? '연결됨' : '없음'}
                foot={gh.has_co2 ? '모델 예측을 쓸 수 있습니다' : '모델 예측은 쓰지 않습니다'}
              />
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
                    <th>예측</th>
                    <th className="num">판정한 주</th>
                    <th className="num">최근 주 개선율</th>
                    <th>시작 상태</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.horizons.filter((h) => h.state !== 'reference').map((h) => {
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
                <span className={s.listVal}>{live ? '오늘 · 캘린더 · AI 어드바이저' : '캘린더'}</span>
              </li>
              {!live && (
                <li>
                  <span className={s.listKey}>수집 API가 필요한 화면</span>
                  <span className={s.listVal}>오늘 · AI 어드바이저</span>
                </li>
              )}
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
