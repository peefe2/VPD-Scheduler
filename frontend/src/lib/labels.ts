import type { BandStatus, ConnectionType, Equipment, HorizonState } from '../api/types'

export const EQUIPMENT: { value: Equipment; label: string }[] = [
  { value: 'vent', label: '천창·측창 환기' },
  { value: 'exhaust_fan', label: '환기팬' },
  { value: 'shade_screen', label: '차광막' },
  { value: 'humidifier', label: '가습(포그·미스트)' },
  { value: 'dehumidifier', label: '제습기' },
  { value: 'heater', label: '난방' },
]

export const CONNECTIONS: { value: ConnectionType; label: string; tag: string; desc: string; disabled?: boolean }[] = [
  {
    value: 'csv',
    label: 'CSV 업로드',
    tag: '회고·검증',
    desc: '제어기나 로거에서 내려받은 파일을 올립니다. 캘린더 회고와 백테스트에 씁니다.',
  },
  {
    value: 'api',
    label: '수집 API',
    tag: '실시간',
    desc: '센서 게이트웨이가 정시에 값을 보냅니다. 실시간 경고와 AI 어드바이저는 이 방식에서만 가능합니다.',
  },
  {
    value: 'replay',
    label: '재생 모드',
    tag: '시연용',
    desc: '연구 데이터(학습 온실)를 날짜만 오늘로 옮겨 정시마다 흘려보냅니다. 그 온실을 학습에서 뺀 모델을 씁니다.',
  },
]

export const connectionLabel = (c: ConnectionType) => CONNECTIONS.find((x) => x.value === c)?.label ?? c

export type Tone = 'brand' | 'neutral' | 'info' | 'warn' | 'below' | 'above'

export const STATE: Record<HorizonState, { label: string; tone: Tone; desc: string }> = {
  model: { label: '모델 사용', tone: 'brand', desc: '이 온실에서 3주 연속 persistence보다 나아 모델 예측을 표시합니다.' },
  persistence: {
    label: 'persistence',
    tone: 'neutral',
    desc: '모델이 아직 이 온실에서 기준보다 낫다고 확인되지 않아 현재 값을 그대로 씁니다.',
  },
  learning: { label: '학습 중', tone: 'info', desc: '이력이 14일 미만이라 아직 판정하지 않습니다.' },
  no_co2: { label: 'CO2 없음', tone: 'warn', desc: 'CO2 없이 모델을 쓸 수 있는지는 검증되지 않아 persistence만 씁니다.' },
  reference: { label: '참고용', tone: 'neutral', desc: '+6h는 검증 표본이 적어 전환 판정에서 제외합니다.' },
}

export const BAND_STATUS: Record<BandStatus, { label: string; tone: Tone }> = {
  in: { label: '대역 안', tone: 'brand' },
  below: { label: '대역 아래', tone: 'below' },
  above: { label: '대역 위', tone: 'above' },
}
