import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { AuthCard, ErrorText, SuccessText } from '../components/AuthCard'
import { useInvalidateCurrentUser } from '../auth/useCurrentUser'
import { ApiError, authApi } from '../lib/api'

type Status = 'pending' | 'success' | 'error'

export function VerifyEmailPage() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<Status>(token ? 'pending' : 'error')
  const [error, setError] = useState<string | null>(token ? null : t('auth2.tokenMissing'))
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
        setError(err instanceof ApiError ? err.message : t('auth2.verifyFailed'))
      })
  }, [token, invalidateCurrentUser, t])

  return (
    <AuthCard title={t('auth2.verifyTitle')}>
      {status === 'pending' && <p className="text-sm text-slate-600">{t('auth2.verifying')}</p>}
      {status === 'success' && <SuccessText>{t('auth2.verified')}</SuccessText>}
      {status === 'error' && error && <ErrorText>{error}</ErrorText>}
      <Link to="/" className="mt-4 block text-center text-sm font-medium text-slate-900 hover:underline">
        {t('auth2.toHome')}
      </Link>
    </AuthCard>
  )
}
