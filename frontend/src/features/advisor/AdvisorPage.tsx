import { Fragment, useEffect, useRef, useState, type FormEvent } from 'react'
import {
  useAdvice,
  useAdviceLogs,
  useAsk,
  useGreenhouse,
  useQuestions,
  useRecordAction,
  useVisitor,
} from '../../api/hooks'
import type {
  AdviceAction,
  AdviceActionInput,
  AdviceCandidate,
  ActionKind,
  Equipment,
  FactSheet,
  SkipReason,
} from '../../api/types'
import { hintClass, inputClass, selectClass } from '../../components/classes'
import { ReplayNotice } from '../../components/ReplayNotice'
import { Badge, Button, Card, Empty, ErrorState, Loading, Notice, PageHeader } from '../../components/ui'
import { day, kpa, num } from '../../lib/format'
import { BAND_STATUS, EQUIPMENT, SKIP_REASONS } from '../../lib/labels'
import { RequiresApi } from '../placeholder/RequiresApi'
import s from './advisor.module.css'

const hhmm = (iso: string) => iso.slice(11, 16)
const eqLabel = (v: string | null) => EQUIPMENT.find((e) => e.value === v)?.label

function CandidateItem({ c, chosen }: { c: AdviceCandidate; chosen: boolean }) {
  return (
    <li className={s.cand} data-chosen={chosen || undefined}>
      <span className={s.num} aria-hidden="true">
        {c.index + 1}
      </span>
      <div>
        <div className={s.candHead}>
          <span className={s.candTitle}>{c.title}</span>
          {c.equipment && <Badge>{eqLabel(c.equipment)}</Badge>}
        </div>
        <p className={s.candReason}>{c.reason}</p>
      </div>
    </li>
  )
}

// 라디오 값: 후보는 "c0"·"c1"…, 그 밖은 "other"·"none"
type Choice = `c${number}` | 'other' | 'none'

const choiceOf = (a: AdviceAction | null): Choice | '' =>
  !a ? '' : a.kind === 'candidate' ? `c${a.candidate_index ?? 0}` : a.kind

function actionText(a: AdviceAction, candidates: AdviceCandidate[]) {
  if (a.kind === 'candidate') return candidates[a.candidate_index!]?.title ?? '후보'
  if (a.kind === 'other') return `후보에 없는 조치: ${eqLabel(a.equipment)}`
  return `조치 안 함 (${SKIP_REASONS.find((r) => r.value === a.reason)?.label})`
}

// 정시마다 "이번에 한 조치" 하나만 남긴다 (2026-11-07, 후보별 실행함/안 함 대신).
// 설비 명령이 아니라 기록이다. 2시간 뒤 실측 VPD가 아래 조치 기록에 붙는다.
function ActionForm({
  id,
  adviceId,
  observedAt,
  candidates,
  equipment,
  action,
  visitor,
}: {
  id: number
  adviceId: number
  observedAt: string
  candidates: AdviceCandidate[]
  equipment: Equipment[]
  action: AdviceAction | null
  visitor?: string
}) {
  const record = useRecordAction(id, visitor)
  const [choice, setChoice] = useState<Choice | ''>(choiceOf(action))
  const [other, setOther] = useState<Equipment | ''>(action?.kind === 'other' ? action.equipment! : '')
  const [reason, setReason] = useState<SkipReason | ''>(action?.reason ?? '')
  const kind: ActionKind | null = choice === '' ? null : choice === 'other' || choice === 'none' ? choice : 'candidate'
  const ready = kind === 'candidate' || (kind === 'other' && other !== '') || (kind === 'none' && reason !== '')
  // 서버 시각은 타임존 없는 현지 시각이라 Date(UTC 변환)를 거치지 않고 시만 더한다
  const after = `${String((Number(observedAt.slice(11, 13)) + 2) % 24).padStart(2, '0')}:00`

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!ready || !kind) return
    const input: AdviceActionInput =
      kind === 'candidate'
        ? { kind, candidate_index: Number(choice.slice(1)) }
        : kind === 'other'
          ? { kind, equipment: other as Equipment }
          : { kind, reason: reason as SkipReason }
    record.mutate({ adviceId, input })
  }

  return (
    <form className={s.actionForm} onSubmit={submit}>
      <fieldset className={s.actionSet}>
        <legend className={s.actionLegend}>이번 정시에 한 조치</legend>
        {candidates.map((c) => (
          <label key={c.index} className={s.actionOption}>
            <input
              type="radio"
              name="action"
              checked={choice === `c${c.index}`}
              onChange={() => setChoice(`c${c.index}`)}
            />
            <span>
              <span className={s.actionNum}>{c.index + 1}</span> {c.title}
            </span>
          </label>
        ))}
        <label className={s.actionOption}>
          <input type="radio" name="action" checked={choice === 'other'} onChange={() => setChoice('other')} />
          <span>후보에 없는 조치</span>
        </label>
        {choice === 'other' && (
          <div className={s.actionSub}>
            <label htmlFor="action-other" className="visually-hidden">
              한 조치의 설비
            </label>
            <select
              id="action-other"
              className={selectClass}
              value={other}
              onChange={(e) => setOther(e.target.value as Equipment)}
            >
              <option value="">등록 설비 고르기</option>
              {equipment.map((e) => (
                <option key={e} value={e}>
                  {eqLabel(e)}
                </option>
              ))}
            </select>
          </div>
        )}
        <label className={s.actionOption}>
          <input type="radio" name="action" checked={choice === 'none'} onChange={() => setChoice('none')} />
          <span>이번엔 조치 안 함</span>
        </label>
        {choice === 'none' && (
          <div className={s.actionSub} role="group" aria-label="조치하지 않은 이유">
            {SKIP_REASONS.map((r) => (
              <button
                key={r.value}
                type="button"
                className={s.tag}
                aria-pressed={reason === r.value}
                onClick={() => setReason(r.value)}
              >
                {r.label}
              </button>
            ))}
          </div>
        )}
      </fieldset>

      <div className={s.actionFoot}>
        <Button type="submit" disabled={!ready || record.isPending}>
          {record.isPending ? '저장 중…' : action ? '기록 바꾸기' : '기록하기'}
        </Button>
        {action && (
          <Button
            type="button"
            variant="ghost"
            disabled={record.isPending}
            onClick={() => record.mutate({ adviceId, input: null }, { onSuccess: () => setChoice('') })}
          >
            기록 취소
          </Button>
        )}
      </div>
      <p className={hintClass} aria-live="polite">
        {action
          ? `기록됨: ${actionText(action, candidates)}. ${after} 실측이 들어오면 아래 조치 기록에 이어서 보입니다.`
          : '설비를 직접 조작하지 않습니다. 실제로 한 일을 고르면 2시간 뒤 실측 VPD와 나란히 남습니다.'}
        {visitor && ' 공개 데모라 기록은 이 브라우저에만 저장됩니다.'}
      </p>
      {record.error && <ErrorState error={record.error} />}
    </form>
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
              : f.forecasts.map((x) => `+${x.horizon}h ${kpa(x.vpd)}`).join(' · ')}
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

// "10-01 09:00" — 재생 온실은 날짜가 옮겨져 있어 날짜도 함께 보여준다
const stamp = (iso: string) => `${iso.slice(5, 10)} ${hhmm(iso)}`

function AskCard({ id }: { id: number }) {
  const [q, setQ] = useState('')
  const { visitor, ready } = useVisitor()
  const { data: history, isLoading } = useQuestions(id, visitor)
  const ask = useAsk(id, visitor)
  const listRef = useRef<HTMLOListElement>(null)
  const count = history?.length ?? 0

  // 새 대화가 생기면 맨 아래(최신)로 내린다
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [count, ask.isPending])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const text = q.trim()
    if (!text || ask.isPending || !ready) return
    ask.mutate(text)
    setQ('')
  }
  return (
    <Card
      title="질문하기"
      sub={`답변도 위 근거와 등록 설비 안에서만 합니다. ${visitor ? '대화는 이 브라우저에서만 보입니다.' : '대화는 이 온실에 저장됩니다.'}`}
    >
      {isLoading ? (
        <Loading />
      ) : count === 0 && !ask.isPending ? (
        <p className={hintClass}>아직 대화가 없습니다. 지금 상황에 대해 물어보세요.</p>
      ) : (
        <ol className={s.chat} ref={listRef} aria-label="대화 내역">
          {history?.map((h) => (
            <Fragment key={h.id}>
              <li className={s.mine}>{h.question}</li>
              <li className={s.theirs}>
                {h.answer}
                <p className={s.answerMeta}>
                  {h.source === 'llm' ? 'AI 답변' : '규칙 기반 안내'} · {stamp(h.observed_at)} 정시 VPD {kpa(h.vpd)} kPa
                  {h.note ? ` · ${h.note}` : ''}
                </p>
              </li>
            </Fragment>
          ))}
          {ask.isPending && (
            <>
              <li className={s.mine}>{ask.variables}</li>
              <li className={s.theirs} data-pending="true" aria-live="polite">
                확인 중…
              </li>
            </>
          )}
        </ol>
      )}
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
    </Card>
  )
}

function LogCard({ id, visitor }: { id: number; visitor?: string }) {
  const { data: logs } = useAdviceLogs(id, visitor)
  return (
    <Card
      title="조치 기록"
      sub="그 정시의 VPD와 2시간 뒤 실측 VPD를 이어서 보여줍니다. 날씨 등 다른 요인도 VPD를 바꾸므로 효과를 판정하지는 않습니다."
    >
      {!logs || logs.length === 0 ? (
        <Empty title="아직 기록이 없습니다">위에서 이번 정시에 한 조치를 고르면 여기에 남습니다.</Empty>
      ) : (
        <ol className={s.logs}>
          {logs.map((r) => (
            <li key={r.advice_id} className={s.log} data-kind={r.kind}>
              <div className={s.logHead}>
                <span className="mono muted">{stamp(r.observed_at)}</span>
                <span className={s.logTitle}>{r.title}</span>
              </div>
              <div className={s.logVpd}>
                <span>
                  <span className="mono">{kpa(r.vpd_at)}</span>{' '}
                  <Badge tone={BAND_STATUS[r.status_at].tone}>{BAND_STATUS[r.status_at].label}</Badge>
                </span>
                <span className={s.arrow} aria-hidden="true">
                  →
                </span>
                {r.vpd_after_2h == null ? (
                  <span className="muted">2시간 뒤 값 대기 중</span>
                ) : (
                  <span>
                    <span className="mono">{kpa(r.vpd_after_2h)}</span>{' '}
                    <Badge tone={BAND_STATUS[r.status_after_2h!].tone}>{BAND_STATUS[r.status_after_2h!].label}</Badge>
                    <span className="muted"> · 2시간 뒤</span>
                  </span>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}

export function AdvisorPage({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  const live = gh?.connection_type === 'api' || gh?.connection_type === 'replay'
  const { visitor, ready } = useVisitor()
  // 방문자 id가 정해진 뒤에 읽어야 내 기록이 섞이지 않는다
  const { data: advice, isLoading, error } = useAdvice(id, live && ready, visitor)

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
        {advice.guardrail.fallback_reason && (
          <Notice tone="warn">
            {advice.guardrail.fallback_reason}
            {advice.guardrail.blocked.length > 0 && <> (막힌 이유: {advice.guardrail.blocked.join(', ')})</>}
          </Notice>
        )}
      </div>

      <div className={s.layout}>
        <div className={s.col}>
          <Card title="조치 후보" sub="설비를 직접 조작하지 않습니다. 검토할 방안이고, 실제로 한 일은 아래에 기록합니다.">
            <p className={s.summary}>{advice.summary}</p>
            <ol className={s.candidates}>
              {advice.candidates.map((c) => (
                <CandidateItem
                  key={c.index}
                  c={c}
                  chosen={advice.action?.kind === 'candidate' && advice.action.candidate_index === c.index}
                />
              ))}
            </ol>
            <ActionForm
              // 정시가 바뀌면 새 추천이므로 고르던 값을 비운다
              key={advice.advice_id}
              id={id}
              adviceId={advice.advice_id}
              observedAt={advice.observed_at}
              candidates={advice.candidates}
              equipment={advice.fact_sheet.greenhouse.equipment}
              action={advice.action}
              visitor={visitor}
            />
          </Card>
          <AskCard id={id} />
          <LogCard id={id} visitor={visitor} />
        </div>

        <aside className={s.col}>
          <FactCard f={advice.fact_sheet} />
          <Card title="안전장치">
            <ul className={s.safety}>
              <li>자동 제어는 하지 않습니다. 조치 기록은 기록일 뿐 설비 명령이 아닙니다.</li>
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
