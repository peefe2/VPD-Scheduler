import type {
  Backtest,
  CalendarResponse,
  ColumnMapping,
  CsvImportResult,
  CsvPreview,
  Greenhouse,
  GreenhouseInput,
  HourlyReading,
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
  trainingSources: () => request<string[]>('/greenhouses/training-sources'),

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
  calendar: (id: number, start?: string, end?: string) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    const qs = q.toString()
    return request<CalendarResponse>(`/greenhouses/${id}/calendar${qs ? `?${qs}` : ''}`)
  },
}
