import { useMutation } from '@tanstack/react-query'
import { useRef, useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import {
  useBacktest,
  useGreenhouse,
  useImportCsv,
  useIngestToken,
  useIssueIngestToken,
  useUpdateGreenhouse,
} from '../../api/hooks'
import type { ColumnMapping, CsvPreview } from '../../api/types'
import { Icon } from '../../components/Icon'
import { Badge, Button, ButtonLink, Card, Field, Notice, PageHeader, Stat } from '../../components/ui'
import { hintClass, selectClass, tableClass, tableWrapClass } from '../../components/classes'
import { daysBetween, day, num } from '../../lib/format'
import { CONNECTIONS } from '../../lib/labels'
import s from './onboarding.module.css'
import { Steps } from './Steps'

const MAP_FIELDS: { key: keyof ColumnMapping; label: string; required: boolean }[] = [
  { key: 'timestamp', label: '시간', required: true },
  { key: 'temperature', label: '온도 °C', required: true },
  { key: 'humidity', label: '습도 %', required: true },
  { key: 'co2', label: 'CO2 ppm', required: false },
]

export function DataStep({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [over, setOver] = useState(false)
  const [mapping, setMapping] = useState<Partial<ColumnMapping>>({})
  const importCsv = useImportCsv(id)
  const { data: existing } = useBacktest(id)
  const update = useUpdateGreenhouse(id)
  const isApi = gh?.connection_type === 'api'
  const isReplay = gh?.connection_type === 'replay'

  const preview = useMutation({
    mutationFn: (f: File) => api.previewCsv(id, f),
    onSuccess: (p: CsvPreview) => {
      const g = p.guessed_mapping
      setMapping({ timestamp: g.timestamp ?? '', temperature: g.temperature ?? '', humidity: g.humidity ?? '', co2: g.co2 })
    },
  })

  const choose = (f: File | undefined) => {
    if (!f) return
    setFile(f)
    importCsv.reset()
    preview.mutate(f)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    choose(e.dataTransfer.files[0])
  }

  const missing = MAP_FIELDS.filter((f) => f.required && !mapping[f.key])
  const mappedCols = new Set(Object.values(mapping).filter(Boolean))
  const result = importCsv.data

  return (
    <>
      <PageHeader title={`데이터 연결 · ${gh?.name ?? ''}`} sub="연결 방식을 고르고 측정 데이터를 가져옵니다." />
      <Steps current={2} ghId={id} />

      <div className={s.grid}>
        <div className={s.col}>
          <Card title="연결 방식">
            <div className={s.conns}>
              {CONNECTIONS.map((c) => (
                <button
                  key={c.value}
                  type="button"
                  className={s.conn}
                  aria-pressed={c.value === gh?.connection_type}
                  disabled={c.disabled || update.isPending}
                  onClick={() => c.value !== gh?.connection_type && update.mutate({ connection_type: c.value })}
                >
                  <span className={s.connHead}>
                    {c.label}
                    <Badge tone={c.disabled ? 'neutral' : 'brand'}>{c.disabled ? '준비 중' : c.tag}</Badge>
                  </span>
                  <span className={s.connDesc}>{c.desc}</span>
                </button>
              ))}
            </div>
          </Card>

          {isApi && <IngestGuide id={id} />}
          {isReplay && <ReplayGuide id={id} source={gh?.holdout_source ?? null} />}

          {/* 재생 모드에 CSV를 섞으면 날짜를 옮긴 재생 데이터와 원본 시각 데이터가 한 온실에 섞인다 */}
          {!isReplay && (
            <Card
              title={isApi ? 'CSV 이력 (선택)' : 'CSV 파일'}
              sub={
                isApi
                  ? '지난 이력을 먼저 올려 두면 백테스트 판정이 그만큼 일찍 시작됩니다. 매 정시의 첫 측정값만 씁니다(평균 아님).'
                  : '분 단위 파일도 됩니다. 매 정시의 첫 측정값만 씁니다(평균 아님).'
              }
            >
              {file ? (
                <div className={s.fileChip}>
                  <Icon name="file" />
                  <span>
                    <strong>{file.name}</strong>
                    {preview.data && <span className="muted"> · {num(preview.data.total_rows)}행</span>}
                  </span>
                  <Button variant="ghost" type="button" onClick={() => inputRef.current?.click()}>
                    다른 파일
                  </Button>
                </div>
              ) : (
                <label
                  className={s.drop}
                  data-over={over}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setOver(true)
                  }}
                  onDragLeave={() => setOver(false)}
                  onDrop={onDrop}
                  htmlFor="csv-file"
                >
                  <Icon name="upload" size={26} />
                  <span className={s.dropTitle}>CSV 파일을 끌어다 놓거나 클릭해서 고르세요</span>
                  <span className={hintClass}>UTF-8 또는 CP949 · 최대 50MB</span>
                </label>
              )}
              <input
                ref={inputRef}
                id="csv-file"
                type="file"
                accept=".csv,text/csv"
                className="visually-hidden"
                onChange={(e) => choose(e.target.files?.[0])}
              />
              {preview.error && (
                <div style={{ marginTop: 12 }}>
                  <Notice tone="warn">{(preview.error as Error).message}</Notice>
                </div>
              )}
            </Card>
          )}

          {preview.data && (
            <Card title="컬럼 매핑" sub="열 이름을 보고 자동으로 골랐습니다. 다르면 바꿔 주세요.">
              <div className={s.mapping}>
                {MAP_FIELDS.map((f) => (
                  <Field key={f.key} label={`${f.label}${f.required ? '' : ' (선택)'}`} htmlFor={`map-${f.key}`}>
                    <select
                      id={`map-${f.key}`}
                      className={selectClass}
                      value={mapping[f.key] ?? ''}
                      onChange={(e) => setMapping({ ...mapping, [f.key]: e.target.value || null })}
                    >
                      <option value="">{f.required ? '선택하세요' : '없음'}</option>
                      {preview.data.columns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </Field>
                ))}
              </div>

              <div className={tableWrapClass} style={{ marginTop: 18 }}>
                <table className={`${tableClass} ${s.previewTable}`}>
                  <thead>
                    <tr>
                      {preview.data.columns.map((c) => (
                        <th key={c} className={mappedCols.has(c) ? s.mappedCol : undefined}>
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.data.rows.map((row, i) => (
                      <tr key={i}>
                        {preview.data.columns.map((c) => (
                          <td key={c} className={mappedCols.has(c) ? s.mappedCol : undefined}>
                            {row[c]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {!mapping.co2 && (
                <div style={{ marginTop: 14 }}>
                  <Notice tone="warn">
                    CO2 열이 없으면 이 온실은 모델 예측으로 전환되지 않고 persistence와 캘린더 회고만 쓸 수 있습니다. CO2
                    없이 온도·습도만으로 충분한지는 아직 검증되지 않았습니다.
                  </Notice>
                </div>
              )}

              <div className={s.actions} style={{ marginTop: 16 }}>
                <Button
                  type="button"
                  disabled={missing.length > 0 || importCsv.isPending}
                  onClick={() => file && importCsv.mutate({ file, mapping: mapping as ColumnMapping })}
                >
                  {importCsv.isPending
                    ? '정시 값으로 변환 중…'
                    : missing.length > 0
                      ? `${missing.map((m) => m.label).join(', ')} 열을 고르세요`
                      : '이 매핑으로 가져오기'}
                </Button>
              </div>
              {importCsv.error && (
                <div style={{ marginTop: 12 }}>
                  <Notice tone="warn">{(importCsv.error as Error).message}</Notice>
                </div>
              )}
            </Card>
          )}

          {result && (
            <Card title="가져오기 결과" action={<Badge tone="brand" dot>저장됨</Badge>}>
              <div className={s.result}>
                <Stat label="저장된 정시" value={num(result.hours_imported)} unit="시간" />
                <Stat
                  label="기간"
                  value={result.start && result.end ? daysBetween(result.start, result.end) : 0}
                  unit="일"
                  foot={`${day(result.start)} ~ ${day(result.end)}`}
                />
                <Stat label="CO2" value={result.co2_included ? '있음' : '없음'} />
              </div>
              <ul className={s.list} style={{ marginTop: 14 }}>
                <li>
                  <span className={s.listKey}>읽은 행</span>
                  <span className={s.listVal}>{num(result.rows_read)}행</span>
                </li>
                {result.rows_bad_timestamp > 0 && (
                  <li>
                    <span className={s.listKey}>시각을 읽지 못해 뺀 행</span>
                    <span className={s.listVal}>{num(result.rows_bad_timestamp)}행</span>
                  </li>
                )}
                {result.rows_humidity_out_of_range > 0 && (
                  <li>
                    <span className={s.listKey}>습도가 0~100% 밖이라 뺀 행</span>
                    <span className={s.listVal}>{num(result.rows_humidity_out_of_range)}행</span>
                  </li>
                )}
                {result.hours_skipped_late > 0 && (
                  <li>
                    <span className={s.listKey}>정시+10분 안에 측정이 없어 비운 정시</span>
                    <span className={s.listVal}>{num(result.hours_skipped_late)}시간</span>
                  </li>
                )}
              </ul>
            </Card>
          )}
        </div>

        <aside className={s.col}>
          <Card title="입력 요건">
            <ul className={s.list}>
              <li>
                <span className={s.listKey}>센서</span>
                <span className={s.listVal}>온도 · 습도는 필수, CO2는 모델 예측에 필요 (VPD는 온도와 습도로 계산)</span>
              </li>
              <li>
                <span className={s.listKey}>샘플링</span>
                <span className={s.listVal}>매 정시의 첫 측정값 (평균 아님)</span>
              </li>
              <li>
                <span className={s.listKey}>결측</span>
                <span className={s.listVal}>정시 값이 없으면 그 시각은 비워 두고 보간하지 않습니다</span>
              </li>
              <li>
                <span className={s.listKey}>이력</span>
                <span className={s.listVal}>14일부터 판정 시작, 모델 전환은 빨라야 35일째</span>
              </li>
            </ul>
          </Card>
          <div className={s.actions}>
            <ButtonLink to={`/g/${id}/settings`} variant="secondary">
              이전
            </ButtonLink>
            <Button
              type="button"
              disabled={!result && !existing?.hours && !isApi && !isReplay}
              onClick={() => navigate(`/g/${id}/setup/review`)}
            >
              다음 · 이력 확인
            </Button>
          </div>
        </aside>
      </div>
    </>
  )
}

const EXAMPLE = `{
  "measurements": [
    { "measured_at": "2026-10-18T14:00:12", "temperature": 24.3, "humidity": 71.5, "co2": 520 }
  ]
}`

// 원문 토큰은 발급 응답에만 있어 이 화면을 떠나면 다시 볼 수 없다 (서버는 해시만 저장)
function TokenPanel({ id, issue }: { id: number; issue: ReturnType<typeof useIssueIngestToken> }) {
  const { data: status } = useIngestToken(id)
  const [copied, setCopied] = useState(false)
  const token = issue.data?.token

  const onIssue = () => {
    if (status?.issued && !window.confirm('재발급하면 지금 쓰는 토큰은 바로 무효가 됩니다. 계속할까요?')) return
    setCopied(false)
    issue.mutate()
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(token!)
      setCopied(true)
    } catch {
      /* 클립보드 권한 없음 — 직접 선택해서 복사 */
    }
  }

  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <Button variant={status?.issued ? 'secondary' : 'primary'} disabled={issue.isPending} onClick={onIssue}>
          {status?.issued ? '토큰 재발급' : '토큰 발급'}
        </Button>
        <span className={hintClass}>
          {status?.issued
            ? `발급됨 · ${day(status.created_at)}`
            : '아직 발급하지 않았습니다. 토큰이 없으면 수집 요청이 401로 거부됩니다.'}
        </span>
      </div>
      {token && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
            <code className="code" style={{ fontSize: 12, wordBreak: 'break-all', userSelect: 'all' }}>
              {token}
            </code>
            <Button variant="ghost" onClick={copy}>
              {copied ? '복사됨' : '복사'}
            </Button>
          </div>
          <div style={{ marginTop: 10 }}>
            <Notice tone="warn">이 토큰은 지금만 볼 수 있습니다. 잃어버리면 재발급하세요.</Notice>
          </div>
        </>
      )}
      {issue.isError && <Notice tone="warn">토큰을 발급하지 못했습니다: {String(issue.error.message)}</Notice>}
    </div>
  )
}

// 센서가 보낼 백엔드 주소. 개발 중엔 화면(5173)과 백엔드(8000)가 따로 뜨고, 배포 때는 같은 서버다.
const apiOrigin = () =>
  import.meta.env.DEV
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : window.location.origin

function IngestGuide({ id }: { id: number }) {
  const issue = useIssueIngestToken(id)
  return (
    <Card title="수집 API" sub="게이트웨이가 측정할 때마다(또는 모아서) 아래 주소로 보내면 됩니다.">
      <ul className={s.list}>
        <li>
          <span className={s.listKey}>주소</span>
          <span className={`${s.listVal} code`}>
            POST {apiOrigin()}/api/greenhouses/{id}/ingest
          </span>
        </li>
        <li>
          <span className={s.listKey}>인증</span>
          <span className={`${s.listVal} code`}>Authorization: Bearer &lt;토큰&gt;</span>
        </li>
        <li>
          <span className={s.listKey}>시각</span>
          <span className={s.listVal}>온실 현지 시각, 타임존 없이 (예: 2026-10-18T14:00:12)</span>
        </li>
        <li>
          <span className={s.listKey}>정시 값</span>
          <span className={s.listVal}>
            각 정시의 가장 이른 측정 하나만 씁니다. 정시+10분보다 늦은 측정과 습도 0~100% 밖 값은 버립니다.
          </span>
        </li>
        <li>
          <span className={s.listKey}>한 번에</span>
          <span className={s.listVal}>최대 1,000건</span>
        </li>
      </ul>
      <pre className={s.codeBlock}>{EXAMPLE}</pre>
      <TokenPanel id={id} issue={issue} />
    </Card>
  )
}

function ReplayGuide({ id, source }: { id: number; source: string | null }) {
  const issue = useIssueIngestToken(id)
  if (!source) {
    return (
      <Notice tone="warn">
        재생 모드는 학습 온실 데이터를 쓰므로 <strong>학습 온실(데모용)</strong>을 먼저 지정해야 합니다. 그래야 그 온실을
        학습에서 뺀 모델로 예측합니다. <Link to={`/g/${id}/settings`}>온실 설정</Link>에서 지정하세요.
      </Notice>
    )
  }
  return (
    <Card title="재생 모드" sub="연구 데이터를 날짜만 오늘로 옮겨, 실제 시계에 맞춰 정시마다 1건씩 보냅니다.">
      <pre className={s.codeBlock} style={{ marginTop: 0 }}>
        {`cd research\nuv run --project ../backend python replay_ingest.py ${id} ${source} --token ${issue.data?.token ?? '<토큰>'}`}
      </pre>
      <TokenPanel id={id} issue={issue} />
      <ul className={s.list} style={{ marginTop: 14 }}>
        <li>
          <span className={s.listKey}>지난 이력</span>
          <span className={s.listVal}>
            원본 앞 35일을 먼저 보냅니다 (첫 모델 전환이 가능한 최소 이력). --backfill-days로 조정
          </span>
        </li>
        <li>
          <span className={s.listKey}>속도</span>
          <span className={s.listVal}>
            기본은 실제 시계(매 정시 1건). --speed 60이면 1분에 1시간씩 — 표시 시각이 실제보다 앞서 나갑니다
          </span>
        </li>
        <li>
          <span className={s.listKey}>시각</span>
          <span className={s.listVal}>날짜만 옮기고 시·분은 원본 그대로라 낮·밤 주기가 맞습니다</span>
        </li>
      </ul>
    </Card>
  )
}
