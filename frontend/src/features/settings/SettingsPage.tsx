import { useGreenhouse, useUpdateGreenhouse } from '../../api/hooks'
import { Badge, Button, ButtonLink, Card, Notice, PageHeader } from '../../components/ui'
import { GreenhouseForm } from '../onboarding/GreenhouseForm'
import s from '../onboarding/onboarding.module.css'

export function SettingsPage({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  const update = useUpdateGreenhouse(id)
  if (!gh) return null

  return (
    <>
      <PageHeader
        title="온실 설정"
        sub={gh.name}
        actions={update.isSuccess && <Badge tone="brand" dot>저장됨</Badge>}
      />
      <div className={s.grid}>
        <GreenhouseForm
          key={gh.id}
          initial={gh}
          error={update.error}
          onSubmit={(data) => update.mutate(data)}
          footer={
            <div className={s.actions}>
              <Button type="submit" disabled={update.isPending}>
                {update.isPending ? '저장 중…' : '저장'}
              </Button>
            </div>
          }
        />
        <aside className={s.col}>
          <Card title="데이터">
            <p className="muted" style={{ fontSize: 14, marginBottom: 14 }}>
              같은 시각의 값이 이미 있으면 새로 올린 값으로 바뀝니다.
            </p>
            <ButtonLink to={`/g/${id}/setup/data`} variant="secondary">
              CSV 더 올리기
            </ButtonLink>
          </Card>
          <Notice>
            대역을 바꾸면 지난 캘린더도 새 대역으로 다시 계산됩니다. 대역 변경 이력을 저장하는 기능은 아직 없습니다.
          </Notice>
        </aside>
      </div>
    </>
  )
}
