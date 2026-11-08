import { useSyncExternalStore } from 'react'

const narrow = window.matchMedia('(max-width: 720px)')

// 휴대폰 폭인지. 그래프 좌표계처럼 CSS로 바꿀 수 없는 값에 쓴다.
export const useNarrow = () =>
  useSyncExternalStore(
    (notify) => {
      narrow.addEventListener('change', notify)
      return () => narrow.removeEventListener('change', notify)
    },
    () => narrow.matches,
  )
