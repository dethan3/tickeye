import type { RiskResponse } from './generated'
import { apiRequest } from './request'

export function getCurrentRisk(signal?: AbortSignal): Promise<RiskResponse> {
  return apiRequest<RiskResponse>('/api/v1/risk/current', { signal })
}

export function recalculateRisk(): Promise<RiskResponse> {
  return apiRequest<RiskResponse>('/api/v1/risk/recalculate', { method: 'POST' })
}
