import type { CalendarDay } from '../api/types'

// 여러 날의 캘린더 집계를 합친다. 비율은 관측된 정시 기준.
export function summarize(days: CalendarDay[]) {
  const sum = (f: (d: CalendarDay) => number) => days.reduce((a, d) => a + f(d), 0)
  const dayObs = sum((d) => d.daytime.hours_observed)
  const nightObs = sum((d) => d.night.hours_observed)
  const ratio = (n: number, d: number) => (d > 0 ? n / d : null)
  return {
    days: days.length,
    observed: sum((d) => d.hours_observed),
    dayObserved: dayObs,
    dayInBand: ratio(sum((d) => d.daytime.hours_in_band), dayObs),
    dayBelow: ratio(sum((d) => d.daytime.hours_below), dayObs),
    dayAbove: ratio(sum((d) => d.daytime.hours_above), dayObs),
    nightBelow: ratio(sum((d) => d.night.hours_below), nightObs),
    hoursBelow: sum((d) => d.hours_below),
    hoursAbove: sum((d) => d.hours_above),
    hoursInBand: sum((d) => d.hours_in_band),
    sufficientDays: days.filter((d) => d.daytime.sufficient).length,
  }
}
