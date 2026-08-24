import type { HealthResponse } from './generated'

type ApiErrorBody = {
  error?: {
    message?: string
  }
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch('/api/v1/health', {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody
    throw new Error(body.error?.message ?? `服务返回异常（${response.status}）`)
  }

  return response.json() as Promise<HealthResponse>
}
