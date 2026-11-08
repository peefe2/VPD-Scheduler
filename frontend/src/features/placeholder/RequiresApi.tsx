import { useParams } from 'react-router-dom'
import { useGreenhouse } from '../../api/hooks'
import { Icon } from '../../components/Icon'
import { ButtonLink, Card, Empty, PageHeader } from '../../components/ui'

export function RequiresApi({ title }: { title: string }) {
  const { ghId } = useParams()
  const { data: gh } = useGreenhouse(Number(ghId))
  const action = (
    <ButtonLink to={`/g/${ghId}/calendar`} variant="secondary">
      캘린더로 가기
    </ButtonLink>
  )
  return (
    <>
      <PageHeader title={title} />
      <Card>
        {gh?.connection_type === 'api' || gh?.connection_type === 'replay' ? (
          <Empty title="아직 준비 중인 화면입니다" action={action}>
            수집 API로 들어온 값은 오늘 화면과 캘린더에서 볼 수 있습니다.
          </Empty>
        ) : (
          <Empty
            title={
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Icon name="lock" /> 수집 API 연결이 필요합니다
              </span>
            }
            action={action}
          >
            실시간 값이 정시마다 들어와야 쓸 수 있는 화면입니다. CSV로 올린 이력은 캘린더에서 볼 수 있습니다.
          </Empty>
        )}
      </Card>
    </>
  )
}
