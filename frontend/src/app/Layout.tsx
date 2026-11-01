import { Link, NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useConfig, useGreenhouses, useLogout, useMe } from '../api/hooks'
import { Icon, type IconName } from '../components/Icon'
import { Notice } from '../components/ui'
import { connectionLabel } from '../lib/labels'
import s from './Layout.module.css'

const NAV: { to: string; label: string; icon: IconName; tag?: string }[] = [
  { to: 'today', label: '오늘', icon: 'today', tag: 'API' },
  { to: 'calendar', label: '캘린더', icon: 'calendar' },
  { to: 'trust', label: '모델 신뢰도', icon: 'trust' },
  { to: 'advisor', label: 'AI 어드바이저', icon: 'advisor', tag: 'API' },
  { to: 'settings', label: '온실 설정', icon: 'settings' },
]

export function Layout() {
  const { ghId } = useParams()
  const { data: greenhouses } = useGreenhouses()
  const readonly = useConfig().data?.readonly ?? false
  const { data: me, isLoading: meLoading } = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const location = useLocation()
  const current = greenhouses?.find((g) => g.id === Number(ghId))

  // 온실을 바꿔도 같은 화면(캘린더 등)에 머문다
  const switchTo = (id: string) => {
    const section = location.pathname.split('/')[3] ?? 'calendar'
    navigate(`/g/${id}/${NAV.some((n) => n.to === section) ? section : 'calendar'}`)
  }

  return (
    <div className={s.shell}>
      <aside className={s.side}>
        <Link to="/" className={s.brand}>
          <span className={s.brandDot} aria-hidden="true" />
          VPD 캘린더
        </Link>

        <nav className={s.nav} aria-label="주 메뉴">
          {NAV.map((item) =>
            ghId ? (
              <NavLink key={item.to} to={`/g/${ghId}/${item.to}`} className={s.navItem}>
                <Icon name={item.icon} />
                {item.label}
                {item.tag && <span className={s.navTag}>{item.tag}</span>}
              </NavLink>
            ) : (
              // 온실을 고르기 전에는 이동할 곳이 없다
              <span key={item.to} className={s.navItem} aria-disabled="true">
                <Icon name={item.icon} />
                {item.label}
              </span>
            ),
          )}
        </nav>

        <div className={s.ghBox}>
          <label className={s.ghLabel} htmlFor="gh-switch">
            온실
          </label>
          {greenhouses && greenhouses.length > 0 ? (
            <select
              id="gh-switch"
              className={s.ghSelect}
              value={current?.id ?? ''}
              onChange={(e) => switchTo(e.target.value)}
            >
              {!current && <option value="">선택</option>}
              {greenhouses.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.public ? `${g.name} · 공개 데모` : g.name}
                </option>
              ))}
            </select>
          ) : (
            <span className={s.ghMeta}>등록된 온실이 없습니다</span>
          )}
          {current && (
            <span className={s.ghMeta}>
              {current.crop} · {connectionLabel(current.connection_type)}
            </span>
          )}
          {!readonly && me && (
            <Link to="/onboarding" className={s.newGh}>
              <Icon name="plus" size={15} />새 온실 등록
            </Link>
          )}
        </div>

        {!meLoading && (
          <div className={s.account}>
            {me ? (
              <>
                <span className={s.accountEmail} title={me.email}>
                  {me.email}
                </span>
                <button
                  type="button"
                  className={s.accountAction}
                  disabled={logout.isPending}
                  onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/', { replace: true }) })}
                >
                  로그아웃
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className={s.accountAction}>
                  로그인
                </Link>
                <Link to="/signup" className={s.accountAction}>
                  회원가입
                </Link>
              </>
            )}
          </div>
        )}
      </aside>

      <main className={s.main}>
        <div className={s.content}>
          {readonly && (
            <div style={{ marginBottom: 16 }}>
              <Notice tone="info">
                읽기 전용 데모입니다. 둘러보기와 AI 어드바이저 질문하기만 할 수 있고, 온실 추가·수정과 기록은
                막혀 있습니다. 질문한 대화는 이 브라우저에서만 보입니다.
              </Notice>
            </div>
          )}
          {!readonly && !meLoading && !me && !['/login', '/signup'].includes(location.pathname) && (
            <div style={{ marginBottom: 16 }}>
              <Notice tone="info">
                로그인하지 않으면 공개 데모 온실만 볼 수 있습니다(보기·AI 질문하기). <Link to="/login">로그인</Link>하거나{' '}
                <Link to="/signup">회원가입</Link>하면 내 온실을 만들 수 있습니다.
              </Notice>
            </div>
          )}
          <Outlet />
        </div>
      </main>
    </div>
  )
}
