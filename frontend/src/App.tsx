import { Route, Routes } from 'react-router-dom'
import { RequireAdmin } from './admin/RequireAdmin'
import { Layout } from './components/Layout'
import { AdminJobsPage } from './pages/AdminJobsPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ListingDetailPage } from './pages/ListingDetailPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { SearchPage } from './pages/SearchPage'
import { VerifyEmailPage } from './pages/VerifyEmailPage'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<SearchPage />} />
        <Route path="/listings/:id" element={<ListingDetailPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route element={<RequireAdmin />}>
          <Route path="/admin/jobs" element={<AdminJobsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
