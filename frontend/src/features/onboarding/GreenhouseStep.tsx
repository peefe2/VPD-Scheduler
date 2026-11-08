import { useNavigate } from 'react-router-dom'
import { useCreateGreenhouse } from '../../api/hooks'
import { Button, Card, PageHeader } from '../../components/ui'
import { DEFAULT_GREENHOUSE } from '../../lib/defaults'
import { GreenhouseForm } from './GreenhouseForm'
import s from './onboarding.module.css'
import { Steps } from './Steps'

export function GreenhouseStep() {
  const create = useCreateGreenhouse()
  const navigate = useNavigate()

  return (
    <>
      <PageHeader title="온실 등록" sub="온실과 작물, 적정 대역을 정합니다." />
      <Steps current={1} />
      <div className={s.grid}>
        <GreenhouseForm
          initial={DEFAULT_GREENHOUSE}
          error={create.error}
          onSubmit={(data) => create.mutate(data, { onSuccess: (gh) => navigate(`/g/${gh.id}/setup/data`) })}
          footer={
            <div className={s.actions}>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? '저장 중…' : '다음 · 데이터 연결'}
              </Button>
            </div>
          }
        />
        <aside className={s.col}>
          <Card title="이 정보가 쓰이는 곳">
            <ul className={s.list}>
              <li>
                <span className={s.listKey}>적정 대역</span>
                <span className={s.listVal}>대역 안 시간과 캘린더 색의 기준</span>
              </li>
              <li>
                <span className={s.listKey}>보유 설비</span>
                <span className={s.listVal}>AI 어드바이저가 조치 후보를 고르는 범위</span>
              </li>
              <li>
                <span className={s.listKey}>온실 단위 관리</span>
                <span className={s.listVal}>데이터, 백테스트, 모델 상태가 온실별로 따로 관리됩니다</span>
              </li>
            </ul>
          </Card>
          <Card title="다음 단계">
            <ul className={s.list}>
              <li>
                <span className={s.listKey}>2 · 데이터 연결</span>
                <span className={s.listVal}>CSV 파일을 올리거나 수집 API를 연결합니다</span>
              </li>
              <li>
                <span className={s.listKey}>3 · 이력 확인과 시작</span>
                <span className={s.listVal}>이력으로 백테스트를 돌려 모델 상태를 정합니다</span>
              </li>
            </ul>
          </Card>
        </aside>
      </div>
    </>
  )
}
