import { useState } from 'react'
import { useBacktest, useGreenhouse } from '../../api/hooks'
import type { HorizonStatus } from '../../api/types'
import { ReplayNotice } from '../../components/ReplayNotice'
import { StateBadge } from '../../components/StateBadge'
import { ButtonLink, Card, Empty, ErrorState, Loading, Notice, PageHeader } from '../../components/ui'
import { hintClass, tableClass, tableWrapClass } from '../../components/classes'
import { day, signedPct } from '../../lib/format'
import { STATE } from '../../lib/labels'
import { LOSO, ONSET_1H } from '../../lib/research'
import s from './trust.module.css'
import { WeeklyChart } from './WeeklyChart'

const judged = (h: HorizonStatus) => h.buckets.filter((b) => b.index >= 2 && b.verdict !== 'insufficient')

function HorizonCard({ h, active, onClick }: { h: HorizonStatus; active: boolean; onClick: () => void }) {
  const last = judged(h).at(-1)
  const v = last?.improvement_pct
  return (
    <button type="button" className={s.hz} aria-pressed={active} onClick={onClick}>
      <span className={s.hzHead}>
        <span className={s.hzName}>+{h.horizon}h</span>
        <StateBadge state={h.state} />
      </span>
      <span>
        <span className={`${s.hzValue} ${v == null ? '' : v > 0 ? s.pos : s.neg}`}>{signedPct(v)}</span>
        <span className="muted" style={{ fontSize: 12, marginLeft: 6 }}>
          최근 판정 주
        </span>
      </span>
      <span className={s.hzDesc}>{h.reason || STATE[h.state].desc}</span>
      <span className={s.hzMeta}>
        <span>판정한 주 {judged(h).length}</span>
        <span>{h.next_judgment_at ? `다음 판정 ${day(h.next_judgment_at)}` : '판정 없음'}</span>
      </span>
    </button>
  )
}

export function TrustPage({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  const { data: bt, isLoading, error } = useBacktest(id)
  const [hz, setHz] = useState<1 | 3 | 6>(1)

  if (isLoading) return <Loading label="백테스트를 계산하는 중" />
  if (error) return <ErrorState error={error} />
  if (!bt || bt.hours === 0) {
    return (
      <>
        <PageHeader title="모델 신뢰도" sub={gh?.name} />
        <Card>
          <Empty title="아직 데이터가 없습니다" action={<ButtonLink to={`/g/${id}/setup/data`}>CSV 올리기</ButtonLink>}>
            이력이 쌓이면 이 온실에서 모델이 persistence보다 나은지 주 단위로 판정합니다.
          </Empty>
        </Card>
      </>
    )
  }

  const selected = bt.horizons.find((h) => h.horizon === hz)!

  return (
    <>
      <PageHeader
        title="모델 신뢰도"
        sub={`${gh?.name} · ${day(bt.history_start)} ~ ${day(bt.history_end)} · 정시 ${bt.hours.toLocaleString('ko-KR')}시간`}
      />

      {(gh?.connection_type === 'replay' || bt.model_set !== 'deployed') && (
        <div style={{ marginBottom: 16 }}>
          <ReplayNotice gh={gh} modelSet={bt.model_set} explain />
        </div>
      )}

      <div className={s.horizons}>
        {bt.horizons.map((h) => (
          <HorizonCard key={h.horizon} h={h} active={h.horizon === hz} onClick={() => setHz(h.horizon)} />
        ))}
      </div>

      <div className={s.layout}>
        <div className={s.col}>
          <Card
            title={`주간 개선율 · +${hz}h`}
            sub="이 온실 실측으로 잰 persistence 대비 RMSE 개선율. 이력 첫날부터 7일씩 끊어 판정합니다."
          >
            {selected.buckets.length === 0 ? (
              <Empty title="아직 끝난 주가 없습니다">첫 7일이 지나면 표시됩니다.</Empty>
            ) : (
              <WeeklyChart buckets={selected.buckets} />
            )}
          </Card>

          <Card title="연구 데이터 검증값" sub="10개 온실, 온실 하나씩 학습에서 빼고 잰 값입니다. 이 온실의 값이 아닙니다.">
            <div className={tableWrapClass}>
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th>지평</th>
                    <th className="num">그룹 A · AI Hub 농가 6곳</th>
                    <th className="num">그룹 B · 정밀제어 온실 4곳</th>
                  </tr>
                </thead>
                <tbody>
                  {LOSO.map((r) => (
                    <tr key={r.horizon}>
                      <td className="mono">
                        {r.horizon}
                        {'reference' in r && <span className="muted"> · 검증용</span>}
                      </td>
                      <td className="num">
                        <span className={s.pos}>{signedPct(r.a)}</span> <span className="muted">({r.aImproved})</span>
                      </td>
                      <td className="num">
                        <span className={s.neg}>{signedPct(r.b)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className={hintClass} style={{ marginTop: 12 }}>
              정밀제어 온실에서는 모델이 persistence보다 못했습니다. 이탈 탐지(+1h, 오경보 10%에서의 재현율)도 그룹 B는
              모델 {ONSET_1H.b.model}로, 단순히 대역 경계까지 남은 거리를 보는 규칙({ONSET_1H.b.edge})보다 낮습니다. 그래서
              이 서비스는 모델을 무조건 쓰지 않고, 온실마다 실측으로 확인된 뒤에만 씁니다.
            </p>
          </Card>
        </div>

        <aside className={s.col}>
          <Card title="자동 전환 규칙" sub="지평마다 따로 판정합니다.">
            <ol className={s.flow}>
              <li className={s.flowNode}>
                <span className={s.flowTitle}>
                  <StateBadge state="learning" />
                </span>
                <p className={s.flowDesc}>처음 14일. persistence만 표시하고 판정하지 않습니다.</p>
              </li>
              <li className={s.flowArrow}>↓ 14일 경과</li>
              <li className={s.flowNode}>
                <span className={s.flowTitle}>
                  <StateBadge state="persistence" />
                </span>
                <p className={s.flowDesc}>현재 값을 그대로 예측값으로 씁니다.</p>
              </li>
              <li className={s.flowArrow}>↓ 3주 연속 개선율 &gt; 0 (빨라야 35일째)</li>
              <li className={s.flowNode}>
                <span className={s.flowTitle}>
                  <StateBadge state="model" />
                </span>
                <p className={s.flowDesc}>모델 예측을 표시합니다.</p>
              </li>
              <li className={s.flowArrow}>↑ 한 주라도 개선율 ≤ 0, 또는 판정 불가 2주 연속이면 즉시 복귀</li>
            </ol>
            <p className={hintClass} style={{ marginTop: 12 }}>
              전환은 느리게, 복귀는 빠르게 합니다. 실제로는 나쁜 모델을 쓰는 쪽이 보수적으로 persistence에 머무는 쪽보다
              피해가 크기 때문입니다. +6h는 검증용으로만 계산하고 오늘 화면에는 보여주지 않습니다.
            </p>
          </Card>
          {!gh?.has_co2 && <Notice tone="warn">{STATE.no_co2.desc}</Notice>}
        </aside>
      </div>
    </>
  )
}
