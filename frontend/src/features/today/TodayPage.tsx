import { useGreenhouse, useReadingsRange, useToday } from '../../api/hooks'
import type { TodayForecast, TodayResponse } from '../../api/types'
import { StateBadge } from '../../components/StateBadge'
import { Badge, ButtonLink, Card, Empty, ErrorState, Loading, Notice, PageHeader } from '../../components/ui'
import { hintClass } from '../../components/classes'
import { day, kpa, localDate, localMs, num, recentStart } from '../../lib/format'
import { BAND_STATUS, STATE } from '../../lib/labels'
import { ReplayNotice } from '../../components/ReplayNotice'
import { RequiresApi } from '../placeholder/RequiresApi'
import { RecentChart } from './RecentChart'
import s from './today.module.css'

// 캘린더·이탈 탐지 검증과 같은 낮 창 (CLAUDE.md, 09~17시 고정)
const DAYTIME: [number, number] = [9, 17]
// 마지막 정시 값이 이보다 오래되면 연결을 확인하라고 알린다
const STALE_HOURS = 2

const hhmm = (iso: string) => iso.slice(11, 16)

// 서버 시각은 온실 현지 시각(타임존 없음). 브라우저도 같은 현지 시각이라고 가정한다.
function hoursAgo(iso: string) {
  return (Date.now() - new Date(iso).getTime()) / 3_600_000
}

function ago(hours: number) {
  if (hours < 48) return `${Math.floor(hours)}시간`
  return `${num(Math.floor(hours / 24))}일`
}

function ForecastCard({ f }: { f: TodayForecast }) {
  const tone = BAND_STATUS[f.band_status]
  return (
    <div className={s.hz}>
      <span className={s.hzHead}>
        <span className={s.hzName}>+{f.horizon}h</span>
        <StateBadge state={f.state} />
      </span>
      <span>
        <span className={`${s.hzValue} ${s[f.band_status]}`}>{kpa(f.vpd)}</span>
        <span className={s.unit}>kPa</span>
      </span>
      <span>
        <Badge tone={tone.tone}>{tone.label}</Badge>
      </span>
      <span className={s.hzMeta}>
        {hhmm(f.target_at)} 예상 · {f.source === 'model' ? '모델 예측' : '현재 값 유지 (persistence)'}
      </span>
      {f.note && <span className={s.hzMeta}>{f.note}</span>}
    </div>
  )
}

function HoldCard({ t }: { t: TodayResponse }) {
  const latest = t.latest!
  const status = BAND_STATUS[latest.band_status]
  const modelOutlook = t.forecasts.filter((f) => f.source === 'model' && !f.reference)
  return (
    <Card title="대역 안 유지 시간" sub={`적정 대역 ${t.band.low}~${t.band.high} kPa`}>
      <div className={s.now}>
        <Badge tone={status.tone} dot>
          {status.label}
        </Badge>
        <span className={s.run}>
          {t.run_hours}
          <span className={s.unit}>시간째</span>
        </span>
      </div>
      {t.basis === 'model' ? (
        <>
          <ul className={s.outlook}>
            {modelOutlook.map((f) => (
              <li key={f.horizon}>
                <span>
                  +{f.horizon}h 모델 예측 <span className="mono">{kpa(f.vpd)}</span> kPa
                </span>
                <Badge tone={BAND_STATUS[f.band_status].tone}>{BAND_STATUS[f.band_status].label}</Badge>
              </li>
            ))}
          </ul>
          <p className={hintClass} style={{ marginTop: 12 }}>
            모델 예측값은 대역을 벗어나는 시점을 정확히 맞히지 못할 수 있어 참고로만 보여줍니다. 실측으로 확인하세요.
          </p>
        </>
      ) : (
        <p className={hintClass} style={{ marginTop: 12 }}>
          이 온실에서 모델이 아직 persistence보다 낫다고 확인되지 않아 앞으로 얼마나 유지될지는 예측하지 않습니다. 실측으로
          지금 상태가 이어진 시간만 표시합니다(빠진 정시가 있으면 거기서 끊음).
        </p>
      )}
    </Card>
  )
}

export function TodayPage({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  // 재생 모드도 수집 API로 값이 들어오므로 같은 화면을 쓴다
  const isLive = gh?.connection_type === 'api' || gh?.connection_type === 'replay'
  const { data: t, isLoading, error } = useToday(id, isLive)
  // 마지막 정시까지 최근 24시간 — 자정 직후에도 그래프가 비지 않게 날짜가 아니라 시간으로 자른다
  const end = t?.latest?.hour ?? null
  const { data: readings } = useReadingsRange(
    id,
    end ? localDate(recentStart(end)) : null,
    end ? localDate(localMs(end)) : null,
  )

  if (gh && !isLive) return <RequiresApi title="오늘" />
  if (isLoading) return <Loading label="최근 값을 불러오는 중" />
  if (error) return <ErrorState error={error} />
  if (!t || !t.latest) {
    return (
      <>
        <PageHeader title="오늘" sub={gh?.name} />
        <Card>
          <Empty
            title="아직 들어온 값이 없습니다"
            action={
              <ButtonLink to={`/g/${id}/setup/data`} variant="secondary">
                연결 방법 보기
              </ButtonLink>
            }
          >
            {gh?.connection_type === 'replay'
              ? '재생 스크립트(research/replay_ingest.py)를 실행하면 정시마다 여기에 표시됩니다.'
              : '센서 게이트웨이가 수집 API로 값을 보내면 정시마다 여기에 표시됩니다.'}
          </Empty>
        </Card>
      </>
    )
  }

  const latest = t.latest
  const stale = hoursAgo(latest.hour)
  const status = BAND_STATUS[latest.band_status]

  return (
    <>
      <PageHeader title="오늘" sub={`${gh?.name} · 마지막 정시 ${day(latest.hour)} ${hhmm(latest.hour)}`} />

      <div className={s.notices}>
        <ReplayNotice gh={gh} />
        {stale > STALE_HOURS && (
          <Notice tone="warn">
            마지막 정시 값이 {ago(stale)} 전입니다.{' '}
            {gh?.connection_type === 'replay'
              ? '재생 스크립트가 실행 중인지 확인하세요.'
              : '게이트웨이가 값을 보내고 있는지 확인하세요.'}
          </Notice>
        )}
        {t.model_set && t.model_set !== 'deployed' && (
          <Notice tone="brand">
            데모 모드 · <strong>{t.model_set.replace('loso:', '')}</strong>을(를) 학습에서 뺀 모델로 예측합니다.
          </Notice>
        )}
        {!gh?.has_co2 && <Notice tone="warn">{STATE.no_co2.desc}</Notice>}
      </div>

      <div className={s.top}>
        <Card title="현재 VPD" sub={`${hhmm(latest.measured_at)} 측정값 (정시의 첫 측정)`}>
          <div className={s.now}>
            <span className={`${s.nowValue} ${s[latest.band_status]}`}>
              {kpa(latest.vpd)}
              <span className={s.unit}>kPa</span>
            </span>
            <Badge tone={status.tone} dot>
              {status.label}
            </Badge>
          </div>
          <div className={s.sensors}>
            <span>
              온도<strong>{latest.temperature.toFixed(1)}°C</strong>
            </span>
            <span>
              습도<strong>{latest.humidity.toFixed(1)}%</strong>
            </span>
            <span>
              CO2<strong>{latest.co2 == null ? '–' : `${num(Math.round(latest.co2))} ppm`}</strong>
            </span>
          </div>
        </Card>
        <HoldCard t={t} />
      </div>

      <div className={s.horizons}>
        {t.forecasts.map((f) => (
          <ForecastCard key={f.horizon} f={f} />
        ))}
      </div>

      <div className={s.bottom}>
        <Card title="최근 24시간 VPD" sub="마지막 정시까지. 측정 없는 정시는 선을 끊습니다. 음영은 낮 09~17시.">
          {readings && (
            <RecentChart readings={readings} end={latest.hour} low={t.band.low} high={t.band.high} daytime={DAYTIME} />
          )}
        </Card>
        <Card title="AI 어드바이저" action={<Badge>준비 중</Badge>}>
          <p className={hintClass}>
            등록한 설비 안에서 조치 후보와 이유를 어드바이저 화면에서 보여줄 예정입니다. 실행 여부는 항상 사람이 정합니다.
          </p>
          <div style={{ marginTop: 12 }}>
            <ButtonLink to={`/g/${id}/advisor`} variant="secondary">
              어드바이저 열기
            </ButtonLink>
          </div>
        </Card>
      </div>
    </>
  )
}
