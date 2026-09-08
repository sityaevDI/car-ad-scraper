import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorText, FieldLabel, inputClass, primaryButtonClass } from '../components/AuthCard'
import { useInvalidateCurrentUser } from '../auth/useCurrentUser'
import { ApiError, authApi } from '../lib/api'

export function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const invalidateCurrentUser = useInvalidateCurrentUser()
  const navigate = useNavigate()

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('Пароли не совпадают')
      return
    }

    setIsSubmitting(true)
    try {
      await authApi.register(email, password)
      await invalidateCurrentUser()
      navigate('/', { state: { justRegistered: true } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось зарегистрироваться')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthCard title="Регистрация">
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
        <button type="submit" disabled={isSubmitting} className={primaryButtonClass}>
          {isSubmitting ? 'Создаём аккаунт…' : 'Зарегистрироваться'}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        Уже есть аккаунт?{' '}
        <Link to="/login" className="font-medium text-slate-900 hover:underline">
          Войти
        </Link>
      </p>
    </AuthCard>
  )
}
