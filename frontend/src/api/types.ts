// 백엔드 응답 타입 (backend/app/routers/*). 필드 이름은 API와 똑같이 둔다.

export type Equipment =
  | 'vent'
  | 'exhaust_fan'
  | 'shade_screen'
  | 'humidifier'
  | 'dehumidifier'
  | 'heater'

export type ConnectionType = 'replay' | 'csv' | 'api'

export interface GreenhouseInput {
  name: string
  crop: string
  vpd_low: number
  vpd_high: number
  equipment: Equipment[]
  connection_type: ConnectionType
  holdout_source?: string | null
  // 대역을 바꿀 때만: "today" 오늘부터 적용(지난 캘린더 유지), "all" 처음부터 적용(정정)
  band_apply?: 'today' | 'all'
}

export interface BandVersion {
  effective_from: string | null // null = 처음부터
  low: number
  high: number
}

export interface Greenhouse extends GreenhouseInput {
  id: number
  has_co2: boolean
  created_at: string
  holdout_source: string | null
}

export interface ColumnMapping {
  timestamp: string
  temperature: string
  humidity: string
  co2?: string | null
}

export interface CsvPreview {
  columns: string[]
  rows: Record<string, string>[]
  total_rows: number
  guessed_mapping: Record<keyof ColumnMapping, string | null>
}

export interface CsvImportResult {
  rows_read: number
  rows_bad_timestamp: number
  rows_humidity_out_of_range: number
  hours_imported: number
  hours_skipped_late: number
  start: string | null
  end: string | null
  co2_included: boolean
  enough_history: boolean
}

export type HorizonState = 'learning' | 'persistence' | 'model' | 'no_co2' | 'reference'
export type Verdict = 'better' | 'not_better' | 'insufficient'

export interface Bucket {
  index: number
  start: string
  end: string
  n: number
  rmse_model: number | null
  rmse_persistence: number | null
  improvement_pct: number | null
  verdict: Verdict
  state_after: HorizonState | null
}

export interface HorizonStatus {
  horizon: 1 | 3 | 6
  state: HorizonState
  buckets: Bucket[]
  next_judgment_at: string | null
  reason: string
}

export interface Backtest {
  greenhouse_id: number
  history_start: string | null
  history_end: string | null
  hours: number
  model_set: string // "deployed" | "loso:<온실>"
  horizons: HorizonStatus[]
}

export interface DayPart {
  hours_observed: number
  hours_in_band: number
  hours_below: number
  hours_above: number
  sufficient: boolean
}

export interface CalendarDay {
  date: string
  band: { low: number; high: number } // 그날 유효했던 대역
  hours_observed: number
  hours_in_band: number
  hours_below: number
  hours_above: number
  in_band_ratio: number | null
  daytime: DayPart & { in_band_ratio: number | null }
  night: DayPart & { below_ratio: number | null }
  vpd_min: number | null
  vpd_max: number | null
  vpd_mean: number | null
}

export interface CalendarResponse {
  greenhouse_id: number
  band: { low: number; high: number }
  bands: BandVersion[]
  daytime_hours: [number, number]
  min_hours: { daytime: number; night: number }
  days: CalendarDay[]
}

export interface HourlyReading {
  hour: string
  temperature: number
  humidity: number
  co2: number | null
  vpd: number
}

export type BandStatus = 'below' | 'in' | 'above'

export interface TodayForecast {
  horizon: 1 | 3 | 6
  target_at: string
  state: HorizonState // 백테스트 자동 전환 상태
  source: 'model' | 'persistence' // 실제로 보여주는 값의 출처
  reference: boolean
  vpd: number
  band_status: BandStatus
  note: string
}

export interface TodayResponse {
  greenhouse_id: number
  connection_type: ConnectionType
  band: { low: number; high: number }
  model_set: string | null
  latest: {
    hour: string
    measured_at: string
    temperature: number
    humidity: number
    co2: number | null
    vpd: number
    band_status: BandStatus
  } | null
  run_hours: number
  basis: 'model' | 'persistence' | null
  forecasts: TodayForecast[]
}

export type AdviceDecision = 'done' | 'skipped'

export interface AdviceCandidate {
  index: number
  equipment: Equipment | null
  title: string
  reason: string
  decision: AdviceDecision | null
}

export interface FactSheet {
  greenhouse: { name: string; crop: string; band: { low: number; high: number }; equipment: Equipment[] }
  observed_at: string
  current: {
    vpd: number
    temperature: number
    humidity: number
    co2: number | null
    band_status: BandStatus
    run_hours: number
  }
  forecasts: { horizon: 1 | 3 | 6; vpd: number; band_status: BandStatus; reference: boolean }[]
  mode: 'model' | 'persistence'
}

export type AdviceResponse =
  | { available: false; reason: string }
  | {
      available: true
      advice_id: number
      observed_at: string
      mode: 'model' | 'persistence'
      source: 'rule' | 'llm'
      summary: string
      fact_sheet: FactSheet
      candidates: AdviceCandidate[]
      guardrail: { passed: boolean; violations: string[]; fallback_reason: string }
    }

export interface AdviceLog {
  advice_id: number
  observed_at: string
  title: string
  equipment: Equipment | null
  decision: AdviceDecision
  decided_at: string
  source: 'rule' | 'llm'
  vpd_at: number
  status_at: BandStatus
  vpd_after_2h: number | null
  status_after_2h: BandStatus | null
}

export interface AskResponse {
  answer: string
  source: 'rule' | 'llm'
  note?: string
  violations: string[]
}
