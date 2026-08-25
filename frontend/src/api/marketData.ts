import type { DataQualityResponse, MarketRefreshResponse } from './generated'
import { apiRequest } from './request'

export function getDataQuality(signal?: AbortSignal): Promise<DataQualityResponse> {
  return apiRequest<DataQualityResponse>('/api/v1/data-quality', { signal })
}

export function refreshMarketData(
  instrumentIds: number[] | null = null,
): Promise<MarketRefreshResponse> {
  return apiRequest<MarketRefreshResponse>('/api/v1/market-data/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instrument_ids: instrumentIds }),
  })
}
