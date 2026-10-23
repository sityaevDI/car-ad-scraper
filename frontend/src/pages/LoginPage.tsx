import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorText, FieldLabel, inputClass, primaryButtonClass } from '../components/AuthCard'
import { useInvalidateCurrentUser } from '../auth/useCurrentUser'
import { ApiError, authApi } from '../lib/api'

export function LoginPage() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const invalidateCurrentUser = useInvalidateCurrentUser()
  const navigate = useNavigate()

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await authApi.login(email, password)
      await invalidateCurrentUser()
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('auth.loginFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthCard title={t('auth.loginTitle')}>
      {error && <ErrorText>{error}</ErrorText>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <FieldLabel htmlFor="email">{t('auth.email')}</FieldLabel>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            className={inputClass}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <FieldLabel htmlFor="password">{t('auth.password')}</FieldLabel>
          <input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            className={inputClass}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className="text-right">
          <Link to="/forgot-password" className="text-sm text-slate-600 hover:underline">
            {t('auth.forgotPassword')}
          </Link>
        </div>
        <button type="submit" disabled={isSubmitting} className={primaryButtonClass}>
          {isSubmitting ? t('auth.loggingIn') : t('nav.login')}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        {t('auth.noAccount')}{' '}
        <Link to="/register" className="font-medium text-slate-900 hover:underline">
          {t('auth.signUp')}
        </Link>
      </p>
    </AuthCard>
  )
}
