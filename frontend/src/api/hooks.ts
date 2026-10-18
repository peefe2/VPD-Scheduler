import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ColumnMapping, GreenhouseInput } from './types'

export const keys = {
  greenhouses: ['greenhouses'] as const,
  greenhouse: (id: number) => ['greenhouses', id] as const,
  backtest: (id: number) => ['greenhouses', id, 'backtest'] as const,
  today: (id: number) => ['greenhouses', id, 'today'] as const,
  calendar: (id: number, start?: string, end?: string) =>
    ['greenhouses', id, 'calendar', start ?? '', end ?? ''] as const,
}

export const useGreenhouses = () => useQuery({ queryKey: keys.greenhouses, queryFn: api.listGreenhouses })

export const useGreenhouse = (id: number) =>
  useQuery({ queryKey: keys.greenhouse(id), queryFn: () => api.getGreenhouse(id) })

export const useTrainingSources = () =>
  useQuery({ queryKey: ['training-sources'], queryFn: api.trainingSources, staleTime: Infinity })

export const useBacktest = (id: number, enabled = true) =>
  useQuery({ queryKey: keys.backtest(id), queryFn: () => api.backtest(id), enabled })

// 수집 API는 정시마다 값이 들어오므로 1분마다 다시 읽는다
export const useToday = (id: number, enabled = true) =>
  useQuery({ queryKey: keys.today(id), queryFn: () => api.today(id), enabled, refetchInterval: 60_000 })

export const useCalendar = (id: number, start?: string, end?: string) =>
  useQuery({
    queryKey: keys.calendar(id, start, end),
    queryFn: () => api.calendar(id, start, end),
    placeholderData: (prev) => prev,
  })

export const useReadings = (id: number, date: string | null) =>
  useQuery({
    queryKey: ['greenhouses', id, 'readings', date],
    queryFn: () => api.readings(id, date!, date!),
    enabled: !!date,
  })

export const useReadingsRange = (id: number, start: string | null, end: string | null) =>
  useQuery({
    queryKey: ['greenhouses', id, 'readings', start, end],
    queryFn: () => api.readings(id, start!, end!),
    enabled: !!start && !!end,
  })

export function useCreateGreenhouse() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: GreenhouseInput) => api.createGreenhouse(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.greenhouses }),
  })
}

export function useUpdateGreenhouse(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<GreenhouseInput>) => api.updateGreenhouse(id, data),
    // 대역이 바뀌면 캘린더도, holdout이 바뀌면 백테스트도 다시 계산된다
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.greenhouses }),
  })
}

export function useImportCsv(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ file, mapping }: { file: File; mapping: ColumnMapping }) => api.importCsv(id, file, mapping),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.greenhouse(id) }),
  })
}
