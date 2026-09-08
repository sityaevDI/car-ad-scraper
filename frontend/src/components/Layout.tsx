import { useState } from 'react'
import { Link, Outlet, useNavigate } from 'react-router-dom'
import { useCurrentUser, useInvalidateCurrentUser } from '../auth/useCurrentUser'
import { authApi } from '../lib/api'

export function Layout() {
  const { user, isLoading } = useCurrentUser()
  const invalidateCurrentUser = useInvalidateCurrentUser()
  const navigate = useNavigate()
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  async function handleLogout() {
    setIsLoggingOut(true)
    try {
      await authApi.logout()
      await invalidateCurrentUser()
      navigate('/')
    } finally {
      setIsLoggingOut(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-semibold text-slate-900">
            Car Aggregator
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            {isLoading ? null : user ? (
              <>
                <span className="text-slate-600">{user.email}</span>
                {!user.email_verified && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                    email не подтверждён
                  </span>
                )}
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                >
                  {isLoggingOut ? 'Выходим…' : 'Выйти'}
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="font-medium text-slate-700 hover:text-slate-900">
                  Войти
                </Link>
                <Link
                  to="/register"
                  className="rounded-md bg-slate-900 px-3 py-1.5 font-medium text-white hover:bg-slate-700"
                >
                  Регистрация
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
