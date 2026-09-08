import { apiFetch } from './client'

// make -> models
export type MakesResponse = Record<string, string[]>

export const vehiclesApi = {
  getMakes: () => apiFetch<MakesResponse>('/api/v1/vehicles/makes'),
}
