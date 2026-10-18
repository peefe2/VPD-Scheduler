// 연구 데이터 검증값 (CLAUDE.md "지평별 LOSO 값", "이탈 탐지 검증", 2026-10-12, 결함 168행 제외).
// 화면에 쓰는 성능 수치는 이것뿐이다. 배포 모델로 학습 온실을 다시 잰 값은 쓰지 않는다.

export const LOSO = [
  { horizon: '+1h', a: 9.7, aImproved: '6곳 중 5곳', b: -10.9 },
  { horizon: '+3h', a: 17.2, aImproved: '6곳 중 5곳', b: -16.9 },
  { horizon: '+6h', a: 21.3, aImproved: '6곳 중 6곳', b: -14.5, reference: true },
] as const

// 기본 대역 0.5~1.5 기준 +1h 이탈 재현율 @오경보 10%
export const ONSET_1H = {
  a: { model: 0.56, trend: 0.5, edge: 0.27 },
  b: { model: 0.36, trend: 0.3, edge: 0.44 },
} as const
