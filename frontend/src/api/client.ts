import type {
  AdviceDecision,
  BandVersion,
  AdviceLog,
  AdviceResponse,
  AskResponse,
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

export const api = {
  listGreenhouses: () => request<Greenhouse[]>('/greenhouses'),
  getGreenhouse: (id: number) => request<Greenhouse>(`/greenhouses/${id}`),
  createGreenhouse: (data: GreenhouseInput) => request<Greenhouse>('/greenhouses', json('POST', data)),
  updateGreenhouse: (id: number, data: Partial<GreenhouseInput>) =>
    request<Greenhouse>(`/greenhouses/${id}`, json('PATCH', data)),
  bands: (id: number) => request<BandVersion[]>(`/greenhouses/${id}/bands`),
  trainingSources: () => request<string[]>('/greenhouses/training-sources'),
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
  advice: (id: number) => request<AdviceResponse>(`/greenhouses/${id}/advisor`),
  decide: (id: number, adviceId: number, candidateIndex: number, decision: AdviceDecision | null) =>
    request<{ advice_id: number; decisions: Record<string, AdviceDecision> }>(
      `/greenhouses/${id}/advisor/${adviceId}/decisions`,
      json('POST', { candidate_index: candidateIndex, decision }),
    ),
  adviceLogs: (id: number) => request<AdviceLog[]>(`/greenhouses/${id}/advisor/logs`),
  ask: (id: number, question: string) => request<AskResponse>(`/greenhouses/${id}/advisor/ask`, json('POST', { question })),
  calendar: (id: number, start?: string, end?: string) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    const qs = q.toString()
    return request<CalendarResponse>(`/greenhouses/${id}/calendar${qs ? `?${qs}` : ''}`)
  },
}
