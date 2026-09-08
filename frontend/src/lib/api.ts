import { apiFetch } from './client'

export { ApiError } from './client'

export interface UserOut {
  id: string
  email: string
  email_verified: boolean
  created_at: string
  last_login_at: string | null
}

export interface MessageOut {
  detail: string
}

export const authApi = {
  register: (email: string, password: string) =>
    apiFetch<UserOut>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),

  login: (email: string, password: string) =>
    apiFetch<UserOut>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  logout: () => apiFetch<void>('/api/v1/auth/logout', { method: 'POST' }),

  verifyEmail: (token: string) =>
    apiFetch<MessageOut>('/api/v1/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) }),

  forgotPassword: (email: string) =>
    apiFetch<MessageOut>('/api/v1/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),

  resetPassword: (token: string, newPassword: string) =>
    apiFetch<MessageOut>('/api/v1/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  me: () => apiFetch<UserOut>('/api/v1/me'),
}
