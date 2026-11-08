import { useState } from 'react'
import { useBandReferences } from '../../api/hooks'
import type { BandReferences } from '../../api/types'
import { Badge, Button, Segmented } from '../../components/ui'
import s from './onboarding.module.css'

type Temp = '18' | '22' | '25' | '28'
const TEMPS: { value: Temp; label: string }[] = [
  { value: '18', label: '18°C' },
  { value: '22', label: '22°C' },
  { value: '25', label: '25°C' },
  { value: '28', label: '28°C' },
]

// 포화수증기압 kPa (backend/app/vpd.py와 같은 식). 농가에 익숙한 습도로 보여줄 때만 쓴다.
const saturation = (t: number) => 0.6108 * Math.exp((17.27 * t) / (t + 237.3))
const rhOf = (vpd: number, t: number) => Math.max(0, Math.round(100 * (1 - vpd / saturation(t))))

type Band = { low: number; high: number }

// 지금 입력한 대역과 추천 대역을 같은 눈금에 나란히
function Compare({ rec, current }: { rec: Band; current: Band }) {
  const valid = Number.isFinite(current.low) && Number.isFinite(current.high) && current.low >= 0 && current.low < current.high
  const max = Math.max(3, rec.high, valid ? current.high : 0)
  const row = (name: string, band: Band, tone: 'rec' | 'mine') => (
    <div className={s.compareRow}>
      <span className={s.compareName}>{name}</span>
      <span className={s.compareTrack}>
        <span
          className={s.compareBand}
          data-tone={tone}
          style={{ left: `${(band.low / max) * 100}%`, width: `${((band.high - band.low) / max) * 100}%` }}
        />
      </span>
      <span className={`${s.compareValue} mono`}>
        {band.low}~{band.high}
      </span>
    </div>
  )
  return (
    <div className={s.compare}>
      {row('추천', rec, 'rec')}
      {valid && row('내 설정', current, 'mine')}
    </div>
  )
}

function SourceLink({ data, id }: { data: BandReferences; id: string }) {
  const src = data.sources[id]
  return (
    <a href={src.url} target="_blank" rel="noreferrer" title={src.citation}>
      {src.short}
    </a>
  )
}

// 작물·생육 단계로 문헌 표에서 대역을 찾아 출처와 함께 보여준다 (검토 2026-11-07, 2026-11-08).
// 근거가 있는 칸만 추천하고, 없으면 "근거 부족 — 기본값 유지". 온실 데이터로 고르지 않는다.
// 적용은 입력칸만 바꾸고, 저장 때 대역 변경 이력 규칙(오늘부터 / 처음부터 정정)을 따른다.
export function BandAdvice({
  crop,
  current,
  onApply,
}: {
  crop: string
  current: Band
  onApply: (low: number, high: number) => void
}) {
  const { data } = useBandReferences()
  const [stage, setStage] = useState('')
  const [temp, setTemp] = useState<Temp>('25')
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

  // 단계가 하나뿐인 작물은 고를 것이 없다
  const picked = stages.length === 1 ? stages[0] : stages.find((x) => x.stage === stage)
  const rec = picked?.recommend
  const src = rec ? data.sources[rec.source] : null
  const notes = data.crop_notes[crop] ?? []
  const t = Number(temp)

  return (
    <div className={s.advice}>
      <p className={s.adviceHead}>{crop} 생육 단계로 추천 받기</p>

      {stages.length > 1 && (
        <>
          <div className={s.stageFlow} role="group" aria-label="생육 단계">
            {stages.map((x, i) => (
              <span key={x.stage} className={s.stageStep}>
                {i > 0 && x.stage !== 'all' && (
                  <span className={s.stageArrow} aria-hidden="true">
                    ›
                  </span>
                )}
                <button
                  type="button"
                  className={s.stageChip}
                  aria-pressed={x.stage === stage}
                  onClick={() => setStage(x.stage === stage ? '' : x.stage)}
                >
                  <span className={s.stageDot} data-has={!!x.recommend} aria-hidden="true" />
                  {x.label}
                  <span className="visually-hidden">{x.recommend ? ' (문헌 근거 있음)' : ' (근거 부족)'}</span>
                </button>
              </span>
            ))}
          </div>
          <p className={s.adviceSource}>
            <span className={s.stageDot} data-has="true" aria-hidden="true" /> 문헌 근거 있음 &nbsp;
            <span className={s.stageDot} data-has="false" aria-hidden="true" /> 근거 부족
          </p>
        </>
      )}

      {picked && rec && src && (
        <div className={s.adviceCard}>
          <div className={s.adviceValue}>
            <span className={s.adviceNumber}>
              {rec.low}~{rec.high}
            </span>{' '}
            kPa
          </div>
          <div className={s.adviceBadges}>
            <Badge tone="brand">근거 수준 {rec.evidence}</Badge>
            <Badge tone="neutral">{src.kind}</Badge>
            <Badge tone="neutral">{src.region} 자료</Badge>
          </div>

          <Compare rec={rec} current={current} />

          <div className={s.adviceRh}>
            <span>
              습도로 보면 <strong className="mono">{rhOf(rec.high, t)}~{rhOf(rec.low, t)}%</strong>
            </span>
            <Segmented label="습도 환산 기온" value={temp} options={TEMPS} onChange={setTemp} />
          </div>

          <p className={s.adviceText}>{rec.note}</p>
          {rec.original && <p className={s.adviceText}>{rec.original}</p>}
          <p className={s.adviceSource}>
            출처 1건: <SourceLink data={data} id={rec.source} />
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

      {notes.length > 0 && (
        <ul className={s.cropNotes} aria-label={`${crop} 재배 참고`}>
          {notes.map((n) => (
            <li key={n.text}>
              <Badge tone={n.kind === 'caution' ? 'warn' : 'neutral'}>{n.kind === 'caution' ? '주의' : '특성'}</Badge>
              <span>
                {n.text} <span className={s.adviceSource}>(<SourceLink data={data} id={n.source} />)</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
