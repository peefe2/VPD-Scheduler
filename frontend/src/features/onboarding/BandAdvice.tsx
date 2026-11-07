import { useState } from 'react'
import { useBandReferences } from '../../api/hooks'
import { selectClass } from '../../components/classes'
import { Badge, Button } from '../../components/ui'
import s from './onboarding.module.css'

// 작물·생육 단계로 문헌 표에서 대역을 찾아 출처와 함께 보여준다 (검토 2026-11-07).
// 근거가 있는 칸만 추천하고, 없으면 "근거 부족 — 기본값 유지". 온실 데이터로 고르지 않는다.
// 적용은 입력칸만 바꾸고, 저장 때 대역 변경 이력 규칙(오늘부터 / 처음부터 정정)을 따른다.
export function BandAdvice({
  crop,
  current,
  onApply,
}: {
  crop: string
  current: { low: number; high: number }
  onApply: (low: number, high: number) => void
}) {
  const { data } = useBandReferences()
  const [stage, setStage] = useState('')
  if (!data) return null

  const stages = data.crops[crop]
  const def = data.default
  const same = (l: number, h: number) => current.low === l && current.high === h

  if (!stages) {
    return (
      <div className={s.advice}>
        <p className={s.adviceHead}>작물·생육 단계로 추천</p>
        <p className={s.adviceText}>
          {crop}은(는) 문헌 표에 없어 기본값 {def.low}~{def.high} kPa를 권합니다.
        </p>
      </div>
    )
  }

  const picked = stages.find((x) => x.stage === stage)
  const rec = picked?.recommend
  const src = rec ? data.sources[rec.source] : null

  return (
    <div className={s.advice}>
      <div className={s.adviceTop}>
        <label className={s.adviceHead} htmlFor="band-stage">
          {crop} 생육 단계로 추천 받기
        </label>
        <select id="band-stage" className={selectClass} value={stage} onChange={(e) => setStage(e.target.value)}>
          <option value="">생육 단계 고르기</option>
          {stages.map((x) => (
            <option key={x.stage} value={x.stage}>
              {x.label}
            </option>
          ))}
        </select>
      </div>

      {picked && rec && src && (
        <div className={s.adviceCard}>
          <div className={s.adviceValue}>
            <span className="mono">
              {rec.low}~{rec.high}
            </span>{' '}
            kPa
            <Badge tone="neutral">근거 수준 {rec.evidence}</Badge>
          </div>
          <p className={s.adviceText}>{rec.note}</p>
          {rec.original && <p className={s.adviceText}>{rec.original}</p>}
          <p className={s.adviceSource}>
            출처:{' '}
            <a href={src.url} target="_blank" rel="noreferrer" title={src.citation}>
              {src.short}
            </a>
          </p>
          <Button type="button" variant="secondary" disabled={same(rec.low, rec.high)} onClick={() => onApply(rec.low, rec.high)}>
            {same(rec.low, rec.high) ? '적용됨' : '이 값으로 입력'}
          </Button>
        </div>
      )}

      {picked && !rec && (
        <div className={s.adviceCard} data-empty="true">
          <p className={s.adviceText}>
            <strong>근거 부족</strong> · {picked.reason} 기본값 {def.low}~{def.high} kPa를 유지하기를 권합니다.
          </p>
          {!same(def.low, def.high) && (
            <Button type="button" variant="secondary" onClick={() => onApply(def.low, def.high)}>
              기본값으로 입력
            </Button>
          )}
        </div>
      )}

      {picked?.references && picked.references.length > 0 && (
        <details className={s.adviceRefs}>
          <summary>출처별 참고값 {picked.references.length}개 (추천 아님)</summary>
          <ul>
            {picked.references.map((r) => (
              <li key={r.label}>
                <span className="mono">{r.low === r.high ? r.low : `${r.low}~${r.high}`}</span> kPa · {r.label}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
