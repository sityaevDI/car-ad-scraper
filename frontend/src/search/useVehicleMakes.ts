import { useQuery } from '@tanstack/react-query'
import { vehiclesApi } from '../lib/vehicles'

export function useVehicleMakes() {
  const query = useQuery({
    queryKey: ['vehicle-makes'],
    queryFn: vehiclesApi.getMakes,
    staleTime: 5 * 60 * 1000,
  })
  return { makes: query.data ?? {}, isLoading: query.isLoading }
}
