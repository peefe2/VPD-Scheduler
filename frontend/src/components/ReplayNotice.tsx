import type { Greenhouse } from '../api/types'
import { Notice } from './ui'

// 재생 모드 온실: 연구 데이터를 날짜만 옮긴 것이라 실측처럼 보이지 않게 모든 화면에 표시한다
export function ReplayNotice({ gh }: { gh: Greenhouse | undefined }) {
  if (gh?.connection_type !== 'replay') return null
  return (
    <Notice tone="info">
      재생 데이터 · 연구 데이터 <strong>{gh.holdout_source}</strong>의 날짜만 오늘에 맞춰 옮겨 정시마다 흘려보내는
      중입니다. 이 온실의 실측이 아닙니다. 시각(낮·밤)은 원본 그대로입니다.
    </Notice>
  )
}
