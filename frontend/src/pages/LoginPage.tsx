import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorText, FieldLabel, inputClass, primaryButtonClass } from '../components/AuthCard'
import { useInvalidateCurrentUser } from '../auth/useCurrentUser'
import { ApiError, authApi } from '../lib/api'

export function LoginPage() {
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
      setError(err instanceof ApiError ? err.message : 'Не удалось войти')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthCard title="Вход">
      {error && <ErrorText>{error}</ErrorText>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <FieldLabel htmlFor="email">Email</FieldLabel>
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
          <FieldLabel htmlFor="password">Пароль</FieldLabel>
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
            Забыли пароль?
          </Link>
        </div>
        <button type="submit" disabled={isSubmitting} className={primaryButtonClass}>
          {isSubmitting ? 'Входим…' : 'Войти'}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        Нет аккаунта?{' '}
        <Link to="/register" className="font-medium text-slate-900 hover:underline">
          Зарегистрироваться
        </Link>
      </p>
    </AuthCard>
  )
}
