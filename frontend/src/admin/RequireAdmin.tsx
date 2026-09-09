import { Navigate, Outlet } from 'react-router-dom'
import { useCurrentUser } from '../auth/useCurrentUser'

export function RequireAdmin() {
  const { user, isLoading } = useCurrentUser()

  if (isLoading) return null
  if (!user || user.role !== 'admin') return <Navigate to="/" replace />

  return <Outlet />
}
