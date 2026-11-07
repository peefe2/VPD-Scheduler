import { Link } from 'react-router-dom'
import { useGreenhouses, useMe } from '../../api/hooks'
import { LogoMark } from '../../components/Logo'
import { ButtonLink } from '../../components/ui'
import { DEFAULT_GREENHOUSE } from '../../lib/defaults'
import { LOSO } from '../../lib/research'
import s from './intro.module.css'

// 첫 화면 서비스 소개 (지도교수 피드백 2026-11-07: 처음 들어온 사람에게 서비스 이야기가 필요).
// 숫자는 CLAUDE.md의 값만 쓴다 — VPD 예시는 계산값, 성능은 LOSO 값, 대역 점유율은 연구 데이터.

const DEFAULT_BAND = { low: DEFAULT_GREENHOUSE.vpd_low, high: DEFAULT_GREENHOUSE.vpd_high }

// app/vpd.py와 같은 식
const vpdOf = (t: number, rh: number) => 0.6108 * Math.exp((17.27 * t) / (t + 237.3)) * (1 - rh / 100)

const SAME_TEMP = [90, 70, 50].map((rh) => {
  const v = vpdOf(25, rh)
  const status = v < DEFAULT_BAND.low ? 'below' : v > DEFAULT_BAND.high ? 'above' : 'in'
  return { rh, v, status } as const
})
const STATUS_TEXT = { below: '대역 아래 · 과습', in: '적정 대역 안', above: '대역 위 · 건조' } as const

// 캘린더 칸 예시 (낮 대역 안 비율 단계, 밤 대역 아래 %) — 실제 온실 값이 아니다
const SAMPLE_DAYS = [
  { d: 3, level: 1, night: 100 },
  { d: 4, level: 2, night: 96 },
  { d: 5, level: 4, night: 87 },
  { d: 6, level: 3, night: 100 },
  { d: 7, level: 0, night: 100 },
  { d: 8, level: 2, night: 93 },
  { d: 9, level: 3, night: 80 },
]

const plus1h = LOSO[0]

export function IntroPage() {
  const { data: greenhouses } = useGreenhouses()
  const { data: me } = useMe()
  const demo = greenhouses?.find((g) => g.public)
  const mine = greenhouses?.find((g) => !g.public)
  const demoTo = demo
    ? `/g/${demo.id}/${demo.connection_type === 'csv' ? 'calendar' : 'today'}`
    : greenhouses?.[0]
      ? `/g/${greenhouses[0].id}/calendar`
      : null
  const second = me
    ? mine
      ? { to: `/g/${mine.id}/calendar`, label: '내 온실로 가기' }
      : { to: '/onboarding', label: '내 온실 등록하기' }
    : { to: '/signup', label: '회원가입하고 내 온실 등록' }

  const actions = (
    <div className={s.actions}>
      {demoTo && <ButtonLink to={demoTo}>데모 온실 둘러보기</ButtonLink>}
      <ButtonLink to={second.to} variant="secondary">
        {second.label}
      </ButtonLink>
    </div>
  )

  return (
    <div className={s.page}>
      <header className={s.top}>
        <Link to="/about" className={s.brand}>
          <LogoMark />
          VPD 캘린더
        </Link>
        {!me && (
          <nav className={s.topLinks} aria-label="계정">
            <Link to="/login">로그인</Link>
            <Link to="/signup">회원가입</Link>
          </nav>
        )}
      </header>

      <section className={s.hero}>
        <p className={s.eyebrow}>스마트팜 의사결정 지원 캘린더</p>
        <h1 className={s.title}>
          온도와 습도를 따로 보지 말고,
          <br />
          작물이 느끼는 공기로 보세요.
        </h1>
        <p className={s.lead}>
          VPD 캘린더는 온실의 온도·습도로 <strong>수증기압차(VPD)</strong>를 계산해, 날마다 적정 범위 안에 있었는지
          돌아보게 합니다. 이 온실에서 검증된 경우에만 1·3시간 뒤를 예측하고, 등록한 설비 안에서 조치 후보를
          보여 줍니다. 결정은 항상 사람이 합니다.
        </p>
        {actions}
      </section>

      <section className={s.section}>
        <p className={s.step}>1 · 문제</p>
        <h2 className={s.h2}>같은 25°C라도 작물에게는 전혀 다른 하루입니다</h2>
        <p className={s.text}>
          VPD는 공기가 더 머금을 수 있는 수분의 여유입니다. 낮으면 잎이 수분을 내보내지 못해 병이 생기기 쉽고, 높으면
          기공을 닫아 광합성이 줄어듭니다. 온도 하나, 습도 하나만 봐서는 이 차이가 보이지 않습니다.
        </p>
        <div className={s.compare}>
          {SAME_TEMP.map((x) => (
            <div key={x.rh} className={s.compareCard} data-status={x.status}>
              <span className={s.compareCond}>25°C · 습도 {x.rh}%</span>
              <span className={s.compareValue}>
                {x.v.toFixed(2)}
                <span className={s.unit}>kPa</span>
              </span>
              <span className={s.compareStatus}>{STATUS_TEXT[x.status]}</span>
            </div>
          ))}
        </div>
        <p className={s.note}>
          기본 적정 대역 {DEFAULT_BAND.low}~{DEFAULT_BAND.high} kPa (시설채소 문헌 기준, 온실마다 바꿀 수 있음)
        </p>
      </section>

      <section className={s.section}>
        <p className={s.step}>2 · 실제 온실</p>
        <h2 className={s.h2}>연구 데이터의 온실들은 낮에도 대부분 과습했습니다</h2>
        <div className={s.facts}>
          <div className={s.fact}>
            <span className={s.factValue}>42%</span>
            <span className={s.factLabel}>일반 농가 6곳, 낮(09~17시) 중 적정 대역 안</span>
          </div>
          <div className={s.fact}>
            <span className={s.factValue}>16%</span>
            <span className={s.factLabel}>정밀 환경제어 온실 4곳, 낮 중 적정 대역 안</span>
          </div>
        </div>
        <p className={s.text}>
          나머지 시간은 대부분 대역 아래(과습)였습니다. 그런데 이런 흐름은 그날그날의 숫자만 봐서는 잘 드러나지
          않습니다. 그래서 하루 단위로 쌓아 보는 캘린더에서 시작합니다.
        </p>
        <p className={s.note}>AI Hub 농가 6곳·2024 경진대회 온실 4곳, 가을·겨울 데이터, 대역 0.5~1.5 kPa 기준</p>
      </section>

      <section className={s.section}>
        <p className={s.step}>3 · 이렇게 씁니다</p>
        <h2 className={s.h2}>연결하고, 돌아보고, 판단합니다</h2>
        <ol className={s.flow}>
          <li className={s.flowItem}>
            <span className={s.flowNum}>1</span>
            <h3 className={s.h3}>연결</h3>
            <p className={s.flowText}>
              온실 정보와 보유 설비를 등록하고, 지난 기록 CSV를 올리거나 센서를 수집 API로 연결합니다.
            </p>
          </li>
          <li className={s.flowItem}>
            <span className={s.flowNum}>2</span>
            <h3 className={s.h3}>돌아보기 · 캘린더</h3>
            <p className={s.flowText}>
              칸 색은 낮 시간 중 적정 대역 안에 있던 비율, 칸 아래 숫자는 밤 과습 비율입니다.
            </p>
            <div className={s.sample} aria-label="캘린더 칸 예시">
              {SAMPLE_DAYS.map((x) => (
                <span key={x.d} className={s.sampleDay}>
                  <span
                    className={s.sampleCell}
                    data-dark={x.level >= 3 || undefined}
                    style={{ background: `var(--scale-${x.level})` }}
                  >
                    {x.d}
                  </span>
                  <span className={s.sampleNight}>{x.night}%</span>
                </span>
              ))}
            </div>
            <p className={s.note}>예시 화면 (실제 온실 값 아님) · 칸 아래 = 밤 과습 %</p>
          </li>
          <li className={s.flowItem}>
            <span className={s.flowNum}>3</span>
            <h3 className={s.h3}>판단 · 오늘과 AI 어드바이저</h3>
            <p className={s.flowText}>
              지금 VPD와 그 상태가 몇 시간째인지 보여 주고, 등록한 설비 안에서 조치 후보 3개와 이유를 냅니다. 실행했는지
              기록하면 2시간 뒤 실측 VPD가 옆에 붙습니다.
            </p>
          </li>
        </ol>
      </section>

      <section className={s.section}>
        <p className={s.step}>4 · 믿을 수 있게</p>
        <h2 className={s.h2}>AI 예측은 이 온실에서 확인된 뒤에만 씁니다</h2>
        <p className={s.text}>
          연구 데이터로 1시간 뒤 예측을 검증했더니, 현재 값을 그대로 쓰는 방법보다 일반 농가에서는 오차가{' '}
          {plus1h.a}% 줄었지만 정밀 환경제어 온실에서는 오히려 {Math.abs(plus1h.b)}% 늘었습니다. 온실마다 결과가
          달라서, 예측을 쓸지는 각 온실의 실측으로 정합니다.
        </p>
        <ol className={s.trust}>
          <li>
            <strong>처음 14일</strong>
            <span>학습 중 · 현재 값만 표시</span>
          </li>
          <li>
            <strong>주마다 비교</strong>
            <span>모델과 현재 값 방식의 오차를 7일 단위로</span>
          </li>
          <li>
            <strong>3주 연속 나을 때</strong>
            <span>모델 예측 사용 (빨라야 35일째)</span>
          </li>
          <li>
            <strong>한 주라도 못하면</strong>
            <span>즉시 현재 값 방식으로 복귀</span>
          </li>
        </ol>
        <p className={s.note}>온실 하나씩 학습에서 빼고 잰 값(LOSO), 모델 신뢰도 화면에서 온실별 결과를 볼 수 있습니다.</p>
      </section>

      <section className={s.section}>
        <p className={s.step}>5 · 하지 않는 것</p>
        <h2 className={s.h2}>설비는 사람이 움직입니다</h2>
        <ul className={s.donts}>
          <li>설비를 자동으로 켜거나 끄지 않습니다. 조치 후보는 검토할 방안일 뿐입니다.</li>
          <li>VPD가 언제 대역을 벗어날지 시각을 예고하지 않습니다.</li>
          <li>AI 답변에 근거 없는 숫자나 등록하지 않은 설비가 나오면 막고 규칙 기반 안내로 바꿉니다.</li>
        </ul>
      </section>

      <section className={s.closing}>
        <h2 className={s.h2}>공개 데모 온실에서 먼저 둘러보세요</h2>
        <p className={s.text}>
          데모 온실은 연구 데이터를 오늘 날짜로 옮겨 재생합니다. 로그인하지 않아도 화면을 보고 AI에게 질문할 수
          있습니다.
        </p>
        {actions}
      </section>

      <footer className={s.footer}>2026 이매지니어 프로젝트 · 국립순천대학교 인공지능공학전공 씩씩이들</footer>
    </div>
  )
}
