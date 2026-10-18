import type { CalendarDay } from '../../api/types'

// 칸 색: 낮(09~17시) 대역 안 비율. 구간 기준은 임시값 (CLAUDE.md 캘린더 TODO — 프론트에서 정하기로 함).
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

// 밤 배지: 밤(나머지 15시간) 중 대역 아래 비율. 절반 이상이면 표시, 75% 이상이면 진하게.
export function nightStrength(d: CalendarDay): 'strong' | 'mid' | null {
  if (!d.night.sufficient || d.night.below_ratio == null) return null
  if (d.night.below_ratio >= 0.75) return 'strong'
  if (d.night.below_ratio >= 0.5) return 'mid'
  return null
}
