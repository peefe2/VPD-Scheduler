import { useState, type FormEvent, type ReactNode } from 'react'
import { useTrainingSources } from '../../api/hooks'
import type { Equipment, GreenhouseInput } from '../../api/types'
import { Card, Field, Notice } from '../../components/ui'
import { BandAdvice } from './BandAdvice'
import { hintClass, inputClass, selectClass } from '../../components/classes'
import { EQUIPMENT } from '../../lib/labels'
import s from './onboarding.module.css'

const CROPS = ['토마토', '파프리카', '오이', '딸기']

// 입력한 대역이 0~3 kPa 눈금에서 어디쯤인지 보여준다
function BandScale({ low, high }: { low: number; high: number }) {
  const max = Math.max(3, high)
  const at = (x: number) => `${(x / max) * 100}%`
  return (
    <div className={s.scale} aria-hidden="true">
      <div className={s.scaleTrack}>
        <span className={s.scaleBand} style={{ left: at(low), width: at(high - low) }} />
      </div>
      <div className={s.scaleZones}>
        {low >= 0.2 && <span style={{ left: at(low / 2) }}>과습</span>}
        <span style={{ left: at((low + high) / 2) }}>적정</span>
        {max - high >= 0.2 && <span style={{ left: at((high + max) / 2) }}>건조</span>}
      </div>
    </div>
  )
}

export function GreenhouseForm({
  initial,
  error,
  onSubmit,
  footer,
  askBandApply = false,
}: {
  initial: GreenhouseInput
  error?: unknown
  onSubmit: (data: GreenhouseInput) => void
  footer: ReactNode
  askBandApply?: boolean // 설정 화면: 대역을 바꾸면 적용 시점을 묻는다
}) {
  const [form, setForm] = useState(initial)
  const [submitted, setSubmitted] = useState(false)
  const [low, setLow] = useState(String(initial.vpd_low))
  const [high, setHigh] = useState(String(initial.vpd_high))
  const [bandApply, setBandApply] = useState<'today' | 'all'>('today')
  const { data: sources } = useTrainingSources()

  const lo = Number(low)
  const hi = Number(high)
  const bandError =
    !Number.isFinite(lo) || !Number.isFinite(hi) || low === '' || high === ''
      ? '숫자를 입력하세요.'
      : lo < 0 || hi > 5
        ? '0~5 kPa 사이로 입력하세요.'
        : lo >= hi
          ? '하한은 상한보다 작아야 합니다.'
          : null
  const nameError = form.name.trim() === '' ? '온실 이름을 입력하세요.' : null

  const toggle = (eq: Equipment) =>
    setForm((f) => ({
      ...f,
      equipment: f.equipment.includes(eq) ? f.equipment.filter((e) => e !== eq) : [...f.equipment, eq],
    }))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (bandError || nameError) return
    const bandChanged = lo !== initial.vpd_low || hi !== initial.vpd_high
    onSubmit({
      ...form,
      name: form.name.trim(),
      vpd_low: lo,
      vpd_high: hi,
      ...(askBandApply && bandChanged ? { band_apply: bandApply } : {}),
    })
  }

  return (
    <form onSubmit={submit} className={s.col} noValidate>
      <Card title="온실 기본 정보" sub="여러 동을 운영하면 온실마다 따로 등록합니다.">
        <div className={s.formRow}>
          <Field label="온실 이름" htmlFor="gh-name" hint={submitted ? nameError : undefined}>
            <input
              id="gh-name"
              className={inputClass}
              value={form.name}
              placeholder="예: 1동 토마토"
              maxLength={100}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              aria-invalid={submitted && !!nameError}
              autoFocus={!initial.name}
            />
          </Field>
          <Field label="작물" htmlFor="gh-crop">
            <select
              id="gh-crop"
              className={selectClass}
              value={form.crop}
              onChange={(e) => setForm({ ...form, crop: e.target.value })}
            >
              {[...new Set([form.crop, ...CROPS])].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </Field>
        </div>
      </Card>

      <Card title="적정 VPD 대역" sub="대역 안 시간, 캘린더 색의 기준이 됩니다.">
        <div className={s.band}>
          <Field label="하한 kPa" htmlFor="gh-low">
            <input
              id="gh-low"
              className={`${inputClass} mono`}
              inputMode="decimal"
              value={low}
              onChange={(e) => setLow(e.target.value)}
              aria-invalid={!!bandError}
            />
          </Field>
          <span className={s.tilde}>~</span>
          <Field label="상한 kPa" htmlFor="gh-high">
            <input
              id="gh-high"
              className={`${inputClass} mono`}
              inputMode="decimal"
              value={high}
              onChange={(e) => setHigh(e.target.value)}
              aria-invalid={!!bandError}
            />
          </Field>
        </div>
        {!bandError && <BandScale low={lo} high={hi} />}
        <p className={hintClass} style={{ marginTop: 10, color: bandError ? 'var(--danger)' : undefined }}>
          {bandError ??
            '기본값 0.5~1.5 kPa는 시설 채소의 주간 적정 범위로 보고된 값입니다. 작물과 시기에 맞게 바꿀 수 있습니다.'}
        </p>
        <BandAdvice
          crop={form.crop}
          current={{ low: lo, high: hi }}
          onApply={(l, h) => {
            setLow(String(l))
            setHigh(String(h))
          }}
        />
        {askBandApply && !bandError && (lo !== initial.vpd_low || hi !== initial.vpd_high) && (
          <fieldset className={s.applyBox}>
            <legend className={s.applyLegend}>바꾼 대역을 언제부터 적용할까요?</legend>
            <label className={s.applyOption}>
              <input
                type="radio"
                name="band-apply"
                checked={bandApply === 'today'}
                onChange={() => setBandApply('today')}
              />
              <span>
                <strong>오늘부터</strong>
                <span className={hintClass}>지난 캘린더는 그때 대역으로 그대로 둡니다.</span>
              </span>
            </label>
            <label className={s.applyOption}>
              <input type="radio" name="band-apply" checked={bandApply === 'all'} onChange={() => setBandApply('all')} />
              <span>
                <strong>처음부터 (정정)</strong>
                <span className={hintClass}>잘못 입력한 값을 고칠 때. 지난 캘린더도 새 대역으로 다시 계산하고 이력을 지웁니다.</span>
              </span>
            </label>
          </fieldset>
        )}
      </Card>

      <Card title="보유 설비" sub="선택한 설비 안에서만 AI 어드바이저가 조치 후보를 제안합니다.">
        <div className={s.checks}>
          {EQUIPMENT.map((eq) => (
            <label key={eq.value} className={s.check}>
              <input type="checkbox" checked={form.equipment.includes(eq.value)} onChange={() => toggle(eq.value)} />
              {eq.label}
            </label>
          ))}
        </div>
        <p className={hintClass} style={{ marginTop: 12 }}>
          설비를 제어기와 연결하지 않으며 자동 제어는 하지 않습니다.
        </p>
      </Card>

      {sources && sources.length > 0 && (
        <details className={s.demoBox} open={!!initial.holdout_source}>
          <summary>데모 설정 · 연구 데이터셋에 있던 온실의 데이터를 올릴 때만</summary>
          <Field
            label="학습에 쓰인 온실"
            htmlFor="gh-holdout"
            hint="지정하면 백테스트가 그 온실을 빼고 학습한 모델로 계산합니다. 학습에 쓴 데이터로 성능을 재면 실제보다 좋게 나오기 때문입니다."
          >
            <select
              id="gh-holdout"
              className={selectClass}
              value={form.holdout_source ?? ''}
              onChange={(e) => setForm({ ...form, holdout_source: e.target.value || null })}
            >
              <option value="">해당 없음 (내 온실 데이터)</option>
              {sources.map((src) => (
                <option key={src} value={src}>
                  {src}
                </option>
              ))}
            </select>
          </Field>
        </details>
      )}

      {error != null && <Notice tone="warn">{error instanceof Error ? error.message : String(error)}</Notice>}
      {footer}
    </form>
  )
}
