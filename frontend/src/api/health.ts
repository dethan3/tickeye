import type { HealthResponse } from './generated'
import { apiRequest } from './request'

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/api/v1/health', { signal })
}
