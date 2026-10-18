export const pct = (v: number | null | undefined, digits = 0) =>
  v == null ? '–' : `${(v * 100).toFixed(digits)}%`

export const signedPct = (v: number | null | undefined, digits = 1) =>
  v == null ? '–' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}%`

export const kpa = (v: number | null | undefined, digits = 2) => (v == null ? '–' : v.toFixed(digits))

export const num = (v: number) => v.toLocaleString('ko-KR')

// 서버 시각은 온실 현지 시각(타임존 없음) — Date로 바꾸지 않고 문자열로 다룬다
export const day = (iso: string | null | undefined) => (iso ? iso.slice(0, 10) : '–')
export const shortDate = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`

export function daysBetween(a: string, b: string) {
  return Math.round((Date.parse(b.slice(0, 10)) - Date.parse(a.slice(0, 10))) / 86_400_000) + 1
}

export const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

export function monthKey(d: string) {
  return d.slice(0, 7)
}

export function monthRange(key: string) {
  const [y, m] = key.split('-').map(Number)
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate()
  return { start: `${key}-01`, end: `${key}-${String(last).padStart(2, '0')}`, days: last }
}

// 오늘 화면의 최근 24시간 창. 서버 시각은 온실 현지 시각(타임존 없음)이라 브라우저 현지 시각으로
// 읽어 시간 차이만 쓴다 (한국은 서머타임이 없어 시간 차이가 어긋나지 않음).
export const HOUR_MS = 3_600_000
export const RECENT_HOURS = 24
export const localMs = (iso: string) => new Date(iso).getTime()
export const recentStart = (end: string) => localMs(end) - (RECENT_HOURS - 1) * HOUR_MS

export function localDate(t: number) {
  const d = new Date(t)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
