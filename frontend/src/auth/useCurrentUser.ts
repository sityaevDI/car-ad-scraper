import { useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from '../lib/api'

export const CURRENT_USER_QUERY_KEY = ['me'] as const

export function useCurrentUser() {
  // No throwOnError: anonymous browsing is the primary scenario (see docs/adr/03_FRONTEND.md),
  // so a failed /me call — whether an expected 401 or a network hiccup — should just render the
  // guest UI, never crash the page (there's no error boundary above <Layout>).
  const query = useQuery({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: authApi.me,
    retry: false,
  })
  // React Query keeps the last successful `data` around after a failed refetch (e.g. logout
  // causing the next /me call to 401) — only trust it when this fetch actually succeeded.
  return { user: query.isSuccess ? query.data : undefined, isLoading: query.isLoading }
}

export function useInvalidateCurrentUser() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY })
}
