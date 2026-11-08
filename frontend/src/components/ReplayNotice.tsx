import type { Greenhouse } from '../api/types'
import { Notice } from './ui'

// 데이터 출처 안내 한 줄 (2026-11-07: 재생 안내와 데모 모델 안내를 합침 — 띠가 쌓이지 않게).
// - 재생 온실: 연구 데이터를 날짜만 옮긴 것이라 실측처럼 보이지 않게 모든 화면에 표시한다.
// - 학습 온실 데이터(holdout): 그 온실을 학습에서 뺀 모델을 쓴다는 표시.
export function ReplayNotice({
  gh,
  modelSet,
}: {
  gh: Greenhouse | undefined
  modelSet?: string | null // 백테스트·오늘 응답의 model_set ("deployed" | "loso:<온실>")
}) {
  const replay = gh?.connection_type === 'replay'
  const loso = modelSet && modelSet !== 'deployed' ? modelSet.replace('loso:', '') : null
  if (!replay && !loso) return null
  return (
    <Notice tone="info">
      {replay ? (
        <>
          재생 데이터 · 연구 데이터 <strong>{gh!.holdout_source}</strong>의 날짜만 오늘로 옮겨 흘려보내는 중이라 이
          온실의 실측이 아닙니다(낮·밤 시각은 원본 그대로).
          {loso && <> 예측은 이 온실을 학습에서 뺀 모델로 합니다.</>}
        </>
      ) : (
        <>
          데모 모드 · <strong>{loso}</strong>을(를) 학습에서 뺀 모델로 계산합니다.
        </>
      )}
    </Notice>
  )
}
