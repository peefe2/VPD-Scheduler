import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import { useGreenhouse, useGreenhouses, useMe } from '../api/hooks'
import { ErrorState, Loading } from '../components/ui'
import { AuthPage } from '../features/auth/AuthPage'
import { CalendarPage } from '../features/calendar/CalendarPage'
import { DataStep } from '../features/onboarding/DataStep'
import { IntroPage } from '../features/intro/IntroPage'
import { GreenhouseStep } from '../features/onboarding/GreenhouseStep'
import { ReviewStep } from '../features/onboarding/ReviewStep'
import { SettingsPage } from '../features/settings/SettingsPage'
import { TodayPage } from '../features/today/TodayPage'
import { AdvisorPage } from '../features/advisor/AdvisorPage'
import { TrustPage } from '../features/trust/TrustPage'
import { Layout } from './Layout'

// 로그인 전이면 서비스 소개. 로그인했으면 내 첫 온실, 없으면 공개(데모) 온실, 그것도 없으면 온실 등록
function Home() {
  const { data, isLoading, error } = useGreenhouses()
  const me = useMe()
  if (isLoading || me.isLoading) return <Loading />
  if (error) return <ErrorState error={error} />
  if (!me.data) return <IntroPage />
  const first = data?.find((g) => !g.public) ?? data?.[0]
  if (first) return <Navigate to={`/g/${first.id}/calendar`} replace />
  return <Navigate to="/onboarding" replace />
}

// 온실 등록은 로그인해야 한다
function RequireLogin({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading } = useMe()
  if (isLoading) return <Loading />
  return me ? <>{children}</> : <Navigate to="/login" replace />
}

// :ghId 아래 화면은 온실을 불러온 뒤에 그린다
function WithGreenhouse({ render }: { render: (id: number) => React.ReactNode }) {
  const id = Number(useParams().ghId)
  const { isLoading, error } = useGreenhouse(id)
  if (isLoading) return <Loading />
  if (error) return <ErrorState error={error} />
  return <>{render(id)}</>
}

export function App() {
  return (
    <Routes>
      {/* 소개·로그인은 사이드바 없이 한 장으로 */}
      <Route index element={<Home />} />
      <Route path="about" element={<IntroPage />} />
      <Route path="login" element={<AuthPage mode="login" />} />
      <Route path="signup" element={<AuthPage mode="signup" />} />
      <Route element={<Layout />}>
        <Route
          path="onboarding"
          element={
            <RequireLogin>
              <GreenhouseStep />
            </RequireLogin>
          }
        />
        <Route path="g/:ghId">
          <Route index element={<Navigate to="calendar" replace />} />
          <Route path="setup/data" element={<WithGreenhouse render={(id) => <DataStep id={id} />} />} />
          <Route path="setup/review" element={<WithGreenhouse render={(id) => <ReviewStep id={id} />} />} />
          <Route path="calendar" element={<WithGreenhouse render={(id) => <CalendarPage id={id} />} />} />
          <Route path="trust" element={<WithGreenhouse render={(id) => <TrustPage id={id} />} />} />
          <Route path="settings" element={<WithGreenhouse render={(id) => <SettingsPage id={id} />} />} />
          <Route path="today" element={<WithGreenhouse render={(id) => <TodayPage id={id} />} />} />
          <Route path="advisor" element={<WithGreenhouse render={(id) => <AdvisorPage id={id} />} />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
