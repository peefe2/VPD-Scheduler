import { Link, NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useGreenhouses } from '../api/hooks'
import { Icon, type IconName } from '../components/Icon'
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
                  {g.name}
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
          <Link to="/onboarding" className={s.newGh}>
            <Icon name="plus" size={15} />새 온실 등록
          </Link>
        </div>
      </aside>

      <main className={s.main}>
        <div className={s.content}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
