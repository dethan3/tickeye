import type {
  CreateWatchlistRequest,
  UpdateWatchlistItemRequest,
  WatchlistItemInput,
  WatchlistResponse,
} from './generated'
import { apiRequest } from './request'

export function getWatchlists(signal?: AbortSignal): Promise<WatchlistResponse> {
  return apiRequest<WatchlistResponse>('/api/v1/watchlists', { signal })
}

export function createWatchlist(payload: CreateWatchlistRequest): Promise<WatchlistResponse> {
  return apiRequest<WatchlistResponse>('/api/v1/watchlists', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteWatchlist(watchlistId: number): Promise<WatchlistResponse> {
  return apiRequest<WatchlistResponse>(`/api/v1/watchlists/${watchlistId}`, {
    method: 'DELETE',
  })
}

export function addWatchlistItem(
  watchlistId: number,
  payload: WatchlistItemInput,
): Promise<WatchlistResponse> {
  return apiRequest<WatchlistResponse>(`/api/v1/watchlists/${watchlistId}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateWatchlistItem(
  watchlistId: number,
  itemId: number,
  payload: UpdateWatchlistItemRequest,
): Promise<WatchlistResponse> {
  return apiRequest<WatchlistResponse>(
    `/api/v1/watchlists/${watchlistId}/items/${itemId}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export function removeWatchlistItem(
  watchlistId: number,
  itemId: number,
): Promise<WatchlistResponse> {
  return apiRequest<WatchlistResponse>(
    `/api/v1/watchlists/${watchlistId}/items/${itemId}`,
    { method: 'DELETE' },
  )
}
