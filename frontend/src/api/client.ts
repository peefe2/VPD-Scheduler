import type {
  BandReferences,
  AdviceAction,
  AdviceActionInput,
  BandVersion,
  AdviceLog,
  AdviceResponse,
  AdviceQuestion,
  AppConfig,
  Me,
  Backtest,
  CalendarResponse,
  ColumnMapping,
  CsvImportResult,
  CsvPreview,
  Greenhouse,
  GreenhouseInput,
  HourlyReading,
  IngestTokenStatus,
  IssuedIngestToken,
  TodayResponse,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* 본문이 JSON이 아님 */
    }
    throw new ApiError(res.status, detail)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

const qs = (visitor?: string) => (visitor ? `?visitor=${encodeURIComponent(visitor)}` : '')

export const api = {
  listGreenhouses: () => request<Greenhouse[]>('/greenhouses'),
  getGreenhouse: (id: number) => request<Greenhouse>(`/greenhouses/${id}`),
  createGreenhouse: (data: GreenhouseInput) => request<Greenhouse>('/greenhouses', json('POST', data)),
  updateGreenhouse: (id: number, data: Partial<GreenhouseInput>) =>
    request<Greenhouse>(`/greenhouses/${id}`, json('PATCH', data)),
  bands: (id: number) => request<BandVersion[]>(`/greenhouses/${id}/bands`),
  trainingSources: () => request<string[]>('/greenhouses/training-sources'),
  bandReferences: () => request<BandReferences>('/greenhouses/band-references'),
  ingestToken: (id: number) => request<IngestTokenStatus>(`/greenhouses/${id}/ingest-token`),
  issueIngestToken: (id: number) => request<IssuedIngestToken>(`/greenhouses/${id}/ingest-token`, { method: 'POST' }),

  previewCsv: (id: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<CsvPreview>(`/greenhouses/${id}/csv/preview`, { method: 'POST', body: form })
  },
  importCsv: (id: number, file: File, mapping: ColumnMapping) => {
    const form = new FormData()
    form.append('file', file)
    form.append('mapping', JSON.stringify(mapping))
    return request<CsvImportResult>(`/greenhouses/${id}/csv/import`, { method: 'POST', body: form })
  },

  readings: (id: number, start: string, end: string) =>
    request<HourlyReading[]>(`/greenhouses/${id}/readings?start=${start}&end=${end}`),
  backtest: (id: number) => request<Backtest>(`/greenhouses/${id}/backtest`),
  today: (id: number) => request<TodayResponse>(`/greenhouses/${id}/today`),
  // visitor: 로그인 안 한 방문자(공개 데모)의 브라우저별 id. 대화·조치 기록을 방문자마다 나눈다
  advice: (id: number, visitor?: string) => request<AdviceResponse>(`/greenhouses/${id}/advisor` + qs(visitor)),
  recordAction: (id: number, adviceId: number, body: AdviceActionInput, visitor?: string) =>
    request<AdviceAction>(`/greenhouses/${id}/advisor/${adviceId}/action`, json('POST', { ...body, visitor })),
  clearAction: (id: number, adviceId: number, visitor?: string) =>
    request<void>(`/greenhouses/${id}/advisor/${adviceId}/action` + qs(visitor), { method: 'DELETE' }),
  adviceLogs: (id: number, visitor?: string) => request<AdviceLog[]>(`/greenhouses/${id}/advisor/logs` + qs(visitor)),
  ask: (id: number, question: string, visitor?: string) =>
    request<AdviceQuestion>(`/greenhouses/${id}/advisor/ask`, json('POST', { question, visitor })),
  questions: (id: number, visitor?: string) =>
    request<AdviceQuestion[]>(`/greenhouses/${id}/advisor/questions` + qs(visitor)),
  config: () => request<AppConfig>('/config'),
  me: () => request<Me>('/auth/me'),
  signup: (email: string, password: string) => request<Me>('/auth/signup', json('POST', { email, password })),
  login: (email: string, password: string) => request<Me>('/auth/login', json('POST', { email, password })),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  calendar: (id: number, start?: string, end?: string) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    const qs = q.toString()
    return request<CalendarResponse>(`/greenhouses/${id}/calendar${qs ? `?${qs}` : ''}`)
  },
}
