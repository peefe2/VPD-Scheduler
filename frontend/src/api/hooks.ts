import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api } from './client'
import { visitorId } from '../lib/visitor'
import type { AdviceActionInput, AdviceQuestion, ColumnMapping, GreenhouseInput } from './types'

export const keys = {
  greenhouses: ['greenhouses'] as const,
  greenhouse: (id: number) => ['greenhouses', id] as const,
  backtest: (id: number) => ['greenhouses', id, 'backtest'] as const,
  today: (id: number) => ['greenhouses', id, 'today'] as const,
  advice: (id: number, visitor?: string) => ['greenhouses', id, 'advice', visitor ?? ''] as const,
  adviceLogs: (id: number, visitor?: string) => ['greenhouses', id, 'advice-logs', visitor ?? ''] as const,
  questions: (id: number, visitor?: string) => ['greenhouses', id, 'questions', visitor ?? ''] as const,
  calendar: (id: number, start?: string, end?: string) =>
    ['greenhouses', id, 'calendar', start ?? '', end ?? ''] as const,
}

export const useGreenhouses = () => useQuery({ queryKey: keys.greenhouses, queryFn: api.listGreenhouses })

export const useGreenhouse = (id: number) =>
  useQuery({ queryKey: keys.greenhouse(id), queryFn: () => api.getGreenhouse(id) })

export const useBands = (id: number) =>
  useQuery({ queryKey: ['greenhouses', id, 'bands'], queryFn: () => api.bands(id) })

export const useTrainingSources = () =>
  useQuery({ queryKey: ['training-sources'], queryFn: api.trainingSources, staleTime: Infinity })

export const useBacktest = (id: number, enabled = true) =>
  useQuery({ queryKey: keys.backtest(id), queryFn: () => api.backtest(id), enabled })

// 수집 API는 정시마다 값이 들어오므로 1분마다 다시 읽는다
export const useToday = (id: number, enabled = true) =>
  useQuery({ queryKey: keys.today(id), queryFn: () => api.today(id), enabled, refetchInterval: 60_000 })

// 오늘 화면과 같은 주기로 다시 읽는다 (정시가 바뀌면 새 추천)
export const useAdvice = (id: number, enabled = true, visitor?: string) =>
  useQuery({
    queryKey: keys.advice(id, visitor),
    queryFn: () => api.advice(id, visitor),
    enabled,
    refetchInterval: 60_000,
  })

export const useAdviceLogs = (id: number, visitor?: string) =>
  useQuery({ queryKey: keys.adviceLogs(id, visitor), queryFn: () => api.adviceLogs(id, visitor) })

// 로그인 안 했으면(공개 데모 온실) 브라우저별 방문자 id로 대화·조치 기록을 나눈다. 로그인했으면 서버가 계정으로 나눈다.
export function useVisitor() {
  const { data: me, isLoading } = useMe()
  return { visitor: me === null ? visitorId() : undefined, ready: !isLoading }
}

// 이번 정시에 한 조치 기록. input이 null이면 기록 취소
export function useRecordAction(id: number, visitor?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { adviceId: number; input: AdviceActionInput | null }) => {
      if (v.input) await api.recordAction(id, v.adviceId, v.input, visitor)
      else await api.clearAction(id, v.adviceId, visitor)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['greenhouses', id, 'advice'] })
      qc.invalidateQueries({ queryKey: ['greenhouses', id, 'advice-logs'] })
    },
  })
}

// 로그인 안 했으면 null (401은 오류가 아니라 "로그인 전")
export const useMe = () =>
  useQuery({
    queryKey: ['me'],
    queryFn: () => api.me().catch((e) => (e instanceof ApiError && e.status === 401 ? null : Promise.reject(e))),
    staleTime: Infinity,
  })

// 계정이 바뀌면 보이는 온실·대화가 달라지므로 캐시를 모두 비우고 다시 읽는다
function useAuthMutation<A>(fn: (a: A) => Promise<unknown>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.resetQueries() })
}

export const useLogin = () => useAuthMutation((a: { email: string; password: string }) => api.login(a.email, a.password))
export const useSignup = () =>
  useAuthMutation((a: { email: string; password: string }) => api.signup(a.email, a.password))
export const useLogout = () => useAuthMutation(() => api.logout())

export const useConfig = () => useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: Infinity })

export const useQuestions = (id: number, visitor?: string) =>
  useQuery({ queryKey: keys.questions(id, visitor), queryFn: () => api.questions(id, visitor) })

export function useAsk(id: number, visitor?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (question: string) => api.ask(id, question, visitor),
    // 다시 읽는 사이 방금 질문이 잠깐 사라지지 않게 받은 답을 바로 붙인다
    onSuccess: (row) =>
      qc.setQueryData<AdviceQuestion[]>(keys.questions(id, visitor), (old) => [...(old ?? []), row]),
  })
}

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

export const useIngestToken = (id: number) =>
  useQuery({ queryKey: ['greenhouses', id, 'ingest-token'], queryFn: () => api.ingestToken(id) })

// 원문 토큰은 이 응답에만 있다 — 화면을 떠나면 다시 볼 수 없다
export function useIssueIngestToken(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.issueIngestToken(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['greenhouses', id, 'ingest-token'] }),
  })
}

export function useImportCsv(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ file, mapping }: { file: File; mapping: ColumnMapping }) => api.importCsv(id, file, mapping),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.greenhouse(id) }),
  })
}
