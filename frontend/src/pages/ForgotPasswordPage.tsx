import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { AuthCard, ErrorText, FieldLabel, inputClass, primaryButtonClass, SuccessText } from '../components/AuthCard'
import { ApiError, authApi } from '../lib/api'

export function ForgotPasswordPage() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSent, setIsSent] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await authApi.forgotPassword(email)
      setIsSent(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('auth2.sendFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthCard title={t('auth2.forgotTitle')}>
      {error && <ErrorText>{error}</ErrorText>}
      {isSent ? (
        <SuccessText>{t('auth2.sent')}</SuccessText>
      ) : (
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
          <button type="submit" disabled={isSubmitting} className={primaryButtonClass}>
            {isSubmitting ? t('auth2.sending') : t('auth2.sendLink')}
          </button>
        </form>
      )}
      <p className="mt-4 text-center text-sm text-slate-600">
        <Link to="/login" className="font-medium text-slate-900 hover:underline">
          {t('auth2.backToLogin')}
        </Link>
      </p>
    </AuthCard>
  )
}
