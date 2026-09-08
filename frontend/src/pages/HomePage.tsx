import { useLocation } from 'react-router-dom'
import { useCurrentUser } from '../auth/useCurrentUser'
import { SuccessText } from '../components/AuthCard'

export function HomePage() {
  const { user, isLoading } = useCurrentUser()
  const location = useLocation()
  const justRegistered = Boolean((location.state as { justRegistered?: boolean } | null)?.justRegistered)

  if (isLoading) return null

  return (
    <div className="mx-auto max-w-xl">
      {justRegistered && (
        <SuccessText>Аккаунт создан. Проверьте почту и подтвердите email, чтобы получить полный доступ.</SuccessText>
      )}
      {user ? (
        <p className="text-slate-700">
          Вы вошли как <span className="font-medium">{user.email}</span>. Поиск объявлений появится здесь на
          следующем этапе разработки.
        </p>
      ) : (
        <p className="text-slate-700">
          Добро пожаловать. Поиск объявлений будет доступен без регистрации — эта страница появится на следующем
          этапе. Пока можно создать аккаунт или войти в существующий.
        </p>
      )}
    </div>
  )
}
