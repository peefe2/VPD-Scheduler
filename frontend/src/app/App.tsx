import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import { useGreenhouse, useGreenhouses } from '../api/hooks'
import { ErrorState, Loading } from '../components/ui'
import { CalendarPage } from '../features/calendar/CalendarPage'
import { DataStep } from '../features/onboarding/DataStep'
import { GreenhouseStep } from '../features/onboarding/GreenhouseStep'
import { ReviewStep } from '../features/onboarding/ReviewStep'
import { RequiresApi } from '../features/placeholder/RequiresApi'
import { SettingsPage } from '../features/settings/SettingsPage'
import { TodayPage } from '../features/today/TodayPage'
import { TrustPage } from '../features/trust/TrustPage'
import { Layout } from './Layout'

function RootRedirect() {
  const { data, isLoading, error } = useGreenhouses()
  if (isLoading) return <Loading />
  if (error) return <ErrorState error={error} />
  return <Navigate to={data && data.length > 0 ? `/g/${data[0].id}/calendar` : '/onboarding'} replace />
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
      <Route element={<Layout />}>
        <Route index element={<RootRedirect />} />
        <Route path="onboarding" element={<GreenhouseStep />} />
        <Route path="g/:ghId">
          <Route index element={<Navigate to="calendar" replace />} />
          <Route path="setup/data" element={<WithGreenhouse render={(id) => <DataStep id={id} />} />} />
          <Route path="setup/review" element={<WithGreenhouse render={(id) => <ReviewStep id={id} />} />} />
          <Route path="calendar" element={<WithGreenhouse render={(id) => <CalendarPage id={id} />} />} />
          <Route path="trust" element={<WithGreenhouse render={(id) => <TrustPage id={id} />} />} />
          <Route path="settings" element={<WithGreenhouse render={(id) => <SettingsPage id={id} />} />} />
          <Route path="today" element={<WithGreenhouse render={(id) => <TodayPage id={id} />} />} />
          <Route path="advisor" element={<RequiresApi title="AI 어드바이저" />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
