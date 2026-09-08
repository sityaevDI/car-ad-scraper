import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, authApi } from '../lib/api'

export const CURRENT_USER_QUERY_KEY = ['me'] as const

export function useCurrentUser() {
  const query = useQuery({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: authApi.me,
    retry: false,
    // Anonymous visitors always get a 401 here — that's an expected state, not a failure.
    throwOnError: (error) => !(error instanceof ApiError && error.status === 401),
  })
  // React Query keeps the last successful `data` around after a failed refetch (e.g. logout
  // causing the next /me call to 401) — only trust it when this fetch actually succeeded.
  return { user: query.isSuccess ? query.data : undefined, isLoading: query.isLoading }
}

export function useInvalidateCurrentUser() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY })
}
