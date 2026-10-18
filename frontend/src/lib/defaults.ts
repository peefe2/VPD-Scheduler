import type { GreenhouseInput } from '../api/types'

// 기본 대역 0.5~1.5 kPa: 문헌(Systemic effects of VPD on protected vegetables)의 주간 범위 (CLAUDE.md)
export const DEFAULT_GREENHOUSE: GreenhouseInput = {
  name: '',
  crop: '토마토',
  vpd_low: 0.5,
  vpd_high: 1.5,
  equipment: [],
  connection_type: 'csv',
  holdout_source: null,
}
