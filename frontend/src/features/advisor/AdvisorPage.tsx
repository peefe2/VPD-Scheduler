import { useState, type FormEvent } from 'react'
import { useAdvice, useAdviceLogs, useAsk, useDecide, useGreenhouse } from '../../api/hooks'
import type { AdviceCandidate, AdviceDecision, FactSheet } from '../../api/types'
import { hintClass, inputClass, tableClass, tableWrapClass } from '../../components/classes'
import { ReplayNotice } from '../../components/ReplayNotice'
import { Badge, Button, Card, Empty, ErrorState, Loading, Notice, PageHeader } from '../../components/ui'
import { day, kpa, num } from '../../lib/format'
import { BAND_STATUS, EQUIPMENT } from '../../lib/labels'
import { RequiresApi } from '../placeholder/RequiresApi'
import s from './advisor.module.css'

const hhmm = (iso: string) => iso.slice(11, 16)
const eqLabel = (v: string | null) => EQUIPMENT.find((e) => e.value === v)?.label

function CandidateItem({
  c,
  pending,
  onDecide,
}: {
  c: AdviceCandidate
  pending: boolean
  onDecide: (d: AdviceDecision | null) => void
}) {
  // 같은 버튼을 다시 누르면 선택을 취소한다
  const toggle = (d: AdviceDecision) => onDecide(c.decision === d ? null : d)
  return (
    <li className={s.cand} data-decision={c.decision ?? undefined}>
      <span className={s.num} aria-hidden="true">
        {c.index + 1}
      </span>
      <div>
        <div className={s.candHead}>
          <span className={s.candTitle}>{c.title}</span>
          {c.equipment && <Badge>{eqLabel(c.equipment)}</Badge>}
        </div>
        <p className={s.candReason}>{c.reason}</p>
        <div className={s.choices} role="group" aria-label={`${c.index + 1}번 후보 선택`}>
          <button
            type="button"
            className={s.choice}
            data-kind="done"
            aria-pressed={c.decision === 'done'}
            disabled={pending}
            onClick={() => toggle('done')}
          >
            실행함
          </button>
          <button
            type="button"
            className={s.choice}
            data-kind="skipped"
            aria-pressed={c.decision === 'skipped'}
            disabled={pending}
            onClick={() => toggle('skipped')}
          >
            이번엔 안 함
          </button>
        </div>
      </div>
    </li>
  )
}

function FactCard({ f }: { f: FactSheet }) {
  const status = BAND_STATUS[f.current.band_status]
  return (
    <Card title="추천의 근거" sub="이 값들 밖의 숫자는 화면에 나오지 않습니다.">
      <ul className={s.facts}>
        <li>
          <span>VPD</span>
          <span className="mono">{kpa(f.current.vpd)} kPa</span>
        </li>
        <li>
          <span>상태</span>
          <span>
            <Badge tone={status.tone}>{status.label}</Badge> <span className="mono">{f.current.run_hours}시간째</span>
          </span>
        </li>
        <li>
          <span>온도 · 습도</span>
          <span className="mono">
            {f.current.temperature}°C · {f.current.humidity}%
          </span>
        </li>
        <li>
          <span>CO2</span>
          <span className="mono">{f.current.co2 == null ? '–' : `${num(f.current.co2)} ppm`}</span>
        </li>
        <li>
          <span>적정 대역</span>
          <span className="mono">
            {f.greenhouse.band.low}~{f.greenhouse.band.high} kPa
          </span>
        </li>
        <li>
          <span>모델 예측</span>
          <span className="mono">
            {f.forecasts.length === 0
              ? '쓰지 않음'
              : f.forecasts.map((x) => `+${x.horizon}h ${kpa(x.vpd)}${x.reference ? '(참고)' : ''}`).join(' · ')}
          </span>
        </li>
        <li>
          <span>등록 설비</span>
          <span style={{ textAlign: 'right' }}>
            {f.greenhouse.equipment.length === 0 ? '없음' : f.greenhouse.equipment.map(eqLabel).join(', ')}
          </span>
        </li>
      </ul>
    </Card>
  )
}

function AskCard({ id }: { id: number }) {
  const [q, setQ] = useState('')
  const ask = useAsk(id)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (q.trim()) ask.mutate(q.trim())
  }
  return (
    <Card title="질문하기" sub="답변도 위 근거와 등록 설비 안에서만 합니다.">
      <form className={s.ask} onSubmit={submit}>
        <label htmlFor="advisor-q" className="visually-hidden">
          질문
        </label>
        <input
          id="advisor-q"
          className={inputClass}
          value={q}
          maxLength={500}
          placeholder="예: 지금 환기를 해도 될까요?"
          onChange={(e) => setQ(e.target.value)}
        />
        <Button type="submit" disabled={!q.trim() || ask.isPending}>
          {ask.isPending ? '확인 중…' : '묻기'}
        </Button>
      </form>
      {ask.error && (
        <div style={{ marginTop: 12 }}>
          <ErrorState error={ask.error} />
        </div>
      )}
      {ask.data && (
        <div className={s.answer} aria-live="polite">
          {ask.data.answer}
          <p className={s.answerMeta}>
            {ask.data.source === 'llm' ? 'AI 답변' : '규칙 기반 안내'}
            {ask.data.note ? ` · ${ask.data.note}` : ''}
          </p>
        </div>
      )}
    </Card>
  )
}

function LogCard({ id }: { id: number }) {
  const { data: logs } = useAdviceLogs(id)
  return (
    <Card title="선택 기록" sub="추천 당시 VPD와 2시간 뒤 실측 VPD를 나란히 보여줍니다. 효과를 판정하지는 않습니다.">
      {!logs || logs.length === 0 ? (
        <Empty title="아직 기록이 없습니다">후보에서 실행함 또는 이번엔 안 함을 누르면 여기에 남습니다.</Empty>
      ) : (
        <div className={tableWrapClass}>
          <table className={tableClass}>
            <thead>
              <tr>
                <th>기준 정시</th>
                <th>후보</th>
                <th>선택</th>
                <th className="num">그때 VPD</th>
                <th className="num">2시간 뒤</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((r) => (
                <tr key={`${r.advice_id}-${r.title}`}>
                  <td className="mono">
                    {day(r.observed_at).slice(5)} {hhmm(r.observed_at)}
                  </td>
                  <td>{r.title}</td>
                  <td>{r.decision === 'done' ? <Badge tone="brand">실행함</Badge> : <Badge>이번엔 안 함</Badge>}</td>
                  <td className="num">
                    {kpa(r.vpd_at)} <span className="muted">{BAND_STATUS[r.status_at].label}</span>
                  </td>
                  <td className="num">
                    {r.vpd_after_2h == null ? (
                      <span className="muted">대기 중</span>
                    ) : (
                      <>
                        {kpa(r.vpd_after_2h)} <span className="muted">{BAND_STATUS[r.status_after_2h!].label}</span>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

export function AdvisorPage({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  const live = gh?.connection_type === 'api' || gh?.connection_type === 'replay'
  const { data: advice, isLoading, error } = useAdvice(id, live)
  const decide = useDecide(id)

  if (gh && !live) return <RequiresApi title="AI 어드바이저" />
  if (error) return <ErrorState error={error} />
  if (isLoading || !advice) return <Loading />

  if (!advice.available) {
    return (
      <>
        <PageHeader title="AI 어드바이저" sub={gh?.name} />
        <Card>
          <Empty title="아직 추천할 수 없습니다">{advice.reason}</Empty>
        </Card>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="AI 어드바이저"
        sub={`${gh?.name} · ${day(advice.observed_at)} ${hhmm(advice.observed_at)} 정시 기준`}
        actions={<Badge tone={advice.source === 'llm' ? 'info' : 'neutral'}>{advice.source === 'llm' ? 'AI 답변' : '규칙 기반'}</Badge>}
      />

      <div className={s.notices}>
        <ReplayNotice gh={gh} />
        {advice.mode === 'persistence' && (
          <Notice>
            모델이 이 온실에서 아직 persistence보다 낫다고 확인되지 않아, 실측 상태와 등록 설비로 정한 규칙 기반 안내만
            보여줍니다.
          </Notice>
        )}
        {advice.guardrail.fallback_reason && <Notice tone="warn">{advice.guardrail.fallback_reason}</Notice>}
      </div>

      <div className={s.layout}>
        <div className={s.col}>
          <Card title="조치 후보" sub="설비를 직접 조작하지 않습니다. 실행 여부는 직접 정하고 기록만 남깁니다.">
            <p className={s.summary}>{advice.summary}</p>
            <ol className={s.candidates}>
              {advice.candidates.map((c) => (
                <CandidateItem
                  key={c.index}
                  c={c}
                  pending={decide.isPending}
                  onDecide={(d) => decide.mutate({ adviceId: advice.advice_id, index: c.index, decision: d })}
                />
              ))}
            </ol>
            {decide.error && (
              <div style={{ marginTop: 12 }}>
                <ErrorState error={decide.error} />
              </div>
            )}
          </Card>
          <AskCard id={id} />
          <LogCard id={id} />
        </div>

        <aside className={s.col}>
          <FactCard f={advice.fact_sheet} />
          <Card title="안전장치">
            <ul className={s.safety}>
              <li>자동 제어는 하지 않습니다. 버튼은 선택 기록일 뿐 설비 명령이 아닙니다.</li>
              <li>근거에 없는 숫자, 등록하지 않은 설비, 단정적인 표현, 깨진 글자가 나오면 막고 규칙 기반 안내로 바꿉니다.</li>
              <li>대역을 벗어나는 시각은 예측하지 않습니다.</li>
              <li>모델이 이 온실에서 검증되기 전에는 예측을 근거로 쓰지 않습니다.</li>
            </ul>
            <p className={hintClass} style={{ marginTop: 10 }}>
              조치 방안은 초안 규칙이라 재배 전문가 검토가 필요합니다.
            </p>
          </Card>
        </aside>
      </div>
    </>
  )
}
