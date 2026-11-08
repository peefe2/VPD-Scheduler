import { useBands, useGreenhouse, useUpdateGreenhouse } from '../../api/hooks'
import { Badge, Button, ButtonLink, Card, Notice, PageHeader } from '../../components/ui'
import { connectionLabel } from '../../lib/labels'
import { GreenhouseForm } from '../onboarding/GreenhouseForm'
import s from '../onboarding/onboarding.module.css'

export function SettingsPage({ id }: { id: number }) {
  const { data: gh } = useGreenhouse(id)
  const update = useUpdateGreenhouse(id)
  const { data: bands } = useBands(id)
  if (!gh) return null
  // 지금 적용 중인 대역이 맨 위 ("처음부터"는 effective_from이 없어 맨 아래)
  const history = [...(bands ?? [])].sort((a, b) => (b.effective_from ?? '').localeCompare(a.effective_from ?? ''))
  if (gh.public) {
    return (
      <>
        <PageHeader title="온실 설정" sub={gh.name} />
        <Notice tone="info">공개 데모 온실은 누구나 볼 수 있지만 설정은 바꿀 수 없습니다. 로그인해서 내 온실을 만들어 보세요.</Notice>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="온실 설정"
        sub={gh.name}
        actions={update.isSuccess && <Badge tone="brand" dot>저장됨</Badge>}
      />
      {/* 다시 고치기 시작하면 "저장됨"을 내린다 */}
      <div className={s.grid} onChange={() => update.isSuccess && update.reset()}>
        <GreenhouseForm
          // 저장 후 새 값으로 폼을 다시 그려 "대역 바뀜" 표시가 남지 않게
          key={`${gh.id}-${gh.vpd_low}-${gh.vpd_high}`}
          initial={gh}
          askBandApply
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
          <Card title="데이터 연결" action={<Badge tone="neutral">{connectionLabel(gh.connection_type)}</Badge>}>
            {gh.connection_type === 'csv' && (
              <p className="muted" style={{ fontSize: 14, marginBottom: 14 }}>
                같은 시각의 값이 이미 있으면 새로 올린 값으로 바뀝니다.
              </p>
            )}
            <ButtonLink to={`/g/${id}/setup/data`} variant="secondary">
              {gh.connection_type === 'csv' ? 'CSV 더 올리기' : '연결 정보 보기'}
            </ButtonLink>
          </Card>
          <Card title="대역 변경 이력" sub="캘린더는 날짜마다 그때 대역으로 판정합니다.">
            <ul className={s.list}>
              {history.map((b, i) => (
                <li key={b.effective_from ?? 'start'} className={s.listRow}>
                  <span className={s.listKey}>{b.effective_from ? `${b.effective_from}부터` : '처음부터'}</span>
                  {i === 0 && <Badge tone="brand">적용 중</Badge>}
                  <span className={`${s.listVal} mono`}>
                    {b.low}~{b.high} kPa
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </aside>
      </div>
    </>
  )
}
