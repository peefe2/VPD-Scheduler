// 칸 색: 낮(09~17시) 대역 안 비율. 등간격 5단계로 확정 (2026-10-31) — 데이터 분포에 맞춘
// 값이 아니라 0%와 25% 간격이다. 0%(낮 내내 대역 밖)는 따로 구분한다.
export const LEVELS = [
  { min: 0, label: '0%' },
  { min: 1e-9, label: '~25%' },
  { min: 0.25, label: '25~50%' },
  { min: 0.5, label: '50~75%' },
  { min: 0.75, label: '75%~' },
] as const

export function level(ratio: number | null) {
  if (ratio == null) return 0
  let lv = 0
  LEVELS.forEach((l, i) => {
    if (ratio >= l.min) lv = i
  })
  return lv
}
