const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const CSRF_COOKIE_NAME = 'csrf_token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (method !== 'GET') {
    const csrfToken = readCookie(CSRF_COOKIE_NAME)
    if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })

  if (response.status === 204) return undefined as T

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const message = (data && typeof data.detail === 'string' ? data.detail : null) ?? 'Something went wrong'
    throw new ApiError(response.status, message)
  }
  return data as T
}

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
