import { Link } from 'react-router-dom'
import s from './onboarding.module.css'

const STEPS = ['온실·작물 설정', '데이터 연결', '이력 확인과 시작']

export function Steps({ current, ghId }: { current: 1 | 2 | 3; ghId?: number }) {
  // 온실이 만들어진 뒤에만 2·3단계로 이동할 수 있다
  const href = (n: number) => (n === 1 ? (ghId ? `/g/${ghId}/settings` : null) : ghId ? `/g/${ghId}/setup/${n === 2 ? 'data' : 'review'}` : null)

  return (
    <ol className={s.steps} aria-label="온보딩 단계">
      {STEPS.map((label, i) => {
        const n = i + 1
        const state = n === current ? 'current' : n < current ? 'done' : 'todo'
        const to = href(n)
        const inner = (
          <>
            <span className={s.stepNum}>{state === 'done' ? '✓' : n}</span>
            <span className={s.stepLabel}>{label}</span>
          </>
        )
        return (
          <li key={label}>
            {to && n !== current ? (
              <Link to={to} className={s.step} data-state={state}>
                {inner}
              </Link>
            ) : (
              <span className={s.step} data-state={state} aria-current={n === current ? 'step' : undefined}>
                {inner}
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}
