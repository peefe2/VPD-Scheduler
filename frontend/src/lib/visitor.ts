// 읽기 전용 공개 데모에서 이 브라우저의 대화만 보이게 하는 방문자 id.
// 저장이 막힌 브라우저(사생활 보호 창 등)에서는 탭을 닫으면 대화가 이어지지 않을 뿐 동작은 한다.
const KEY = 'vpd-visitor'
let memory: string | undefined

const newId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`

export function visitorId(): string {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved) return saved
    const id = newId()
    localStorage.setItem(KEY, id)
    return id
  } catch {
    memory ??= newId()
    return memory
  }
}
