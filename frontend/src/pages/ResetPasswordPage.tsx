import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AuthCard, ErrorText, FieldLabel, inputClass, primaryButtonClass, SuccessText } from '../components/AuthCard'
import { ApiError, authApi } from '../lib/api'

export function ResetPasswordPage() {
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
      setError('Пароли не совпадают')
      return
    }
    if (!token) {
      setError('Ссылка недействительна: отсутствует токен')
      return
    }

    setIsSubmitting(true)
    try {
      await authApi.resetPassword(token, password)
      setIsDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сбросить пароль')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthCard title="Новый пароль">
      {!token && <ErrorText>Ссылка недействительна: отсутствует токен.</ErrorText>}
      {error && <ErrorText>{error}</ErrorText>}
      {isDone ? (
        <>
          <SuccessText>Пароль обновлён. Теперь можно войти с новым паролем.</SuccessText>
          <Link to="/login" className="block text-center text-sm font-medium text-slate-900 hover:underline">
            Ко входу
          </Link>
        </>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <FieldLabel htmlFor="password">Новый пароль</FieldLabel>
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
            <FieldLabel htmlFor="confirmPassword">Повторите пароль</FieldLabel>
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
            {isSubmitting ? 'Сохраняем…' : 'Сохранить пароль'}
          </button>
        </form>
      )}
    </AuthCard>
  )
}
