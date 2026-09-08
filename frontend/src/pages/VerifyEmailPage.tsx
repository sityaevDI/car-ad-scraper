import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AuthCard, ErrorText, SuccessText } from '../components/AuthCard'
import { useInvalidateCurrentUser } from '../auth/useCurrentUser'
import { ApiError, authApi } from '../lib/api'

type Status = 'pending' | 'success' | 'error'

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<Status>(token ? 'pending' : 'error')
  const [error, setError] = useState<string | null>(token ? null : 'Ссылка недействительна: отсутствует токен')
  const invalidateCurrentUser = useInvalidateCurrentUser()
  const hasRun = useRef(false)

  useEffect(() => {
    if (hasRun.current || !token) return
    hasRun.current = true

    authApi
      .verifyEmail(token)
      .then(async () => {
        await invalidateCurrentUser()
        setStatus('success')
      })
      .catch((err) => {
        setStatus('error')
        setError(err instanceof ApiError ? err.message : 'Не удалось подтвердить email')
      })
  }, [token, invalidateCurrentUser])

  return (
    <AuthCard title="Подтверждение email">
      {status === 'pending' && <p className="text-sm text-slate-600">Подтверждаем адрес…</p>}
      {status === 'success' && <SuccessText>Email подтверждён.</SuccessText>}
      {status === 'error' && error && <ErrorText>{error}</ErrorText>}
      <Link to="/" className="mt-4 block text-center text-sm font-medium text-slate-900 hover:underline">
        На главную
      </Link>
    </AuthCard>
  )
}
