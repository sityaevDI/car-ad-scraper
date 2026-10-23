import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { AuthCard, ErrorText, FieldLabel, inputClass, primaryButtonClass, SuccessText } from '../components/AuthCard'
import { ApiError, authApi } from '../lib/api'

export function ResetPasswordPage() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isDone, setIsDone] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError(t('auth.passwordsMismatch'))
      return
    }
    if (!token) {
      setError(t('auth2.tokenMissing'))
      return
    }

    setIsSubmitting(true)
    try {
      await authApi.resetPassword(token, password)
      setIsDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('auth2.resetFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthCard title={t('auth2.newPasswordTitle')}>
      {!token && <ErrorText>{t('auth2.tokenMissingDot')}</ErrorText>}
      {error && <ErrorText>{error}</ErrorText>}
      {isDone ? (
        <>
          <SuccessText>{t('auth2.passwordUpdated')}</SuccessText>
          <Link to="/login" className="block text-center text-sm font-medium text-slate-900 hover:underline">
            {t('auth2.toLogin')}
          </Link>
        </>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <FieldLabel htmlFor="password">{t('auth2.newPassword')}</FieldLabel>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              className={inputClass}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div>
            <FieldLabel htmlFor="confirmPassword">{t('auth.confirmPassword')}</FieldLabel>
            <input
              id="confirmPassword"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              className={inputClass}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>
          <button type="submit" disabled={isSubmitting || !token} className={primaryButtonClass}>
            {isSubmitting ? t('auth2.savingPassword') : t('auth2.savePassword')}
          </button>
        </form>
      )}
    </AuthCard>
  )
}
