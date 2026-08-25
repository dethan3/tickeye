export type ApiErrorDetail = {
  code: string
  message: string
  field?: string | null
  row?: number | null
}

type ApiErrorBody = {
  error?: {
    code?: string
    message?: string
    details?: ApiErrorDetail[]
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: ApiErrorDetail[]

  constructor(status: number, body: ApiErrorBody) {
    super(body.error?.message ?? `服务返回异常（${status}）`)
    this.name = 'ApiError'
    this.status = status
    this.code = body.error?.code ?? 'unknown_error'
    this.details = body.error?.details ?? []
  }
}

export async function apiRequest<ResponseBody>(
  path: string,
  init?: RequestInit,
): Promise<ResponseBody> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody
    throw new ApiError(response.status, body)
  }
  return response.json() as Promise<ResponseBody>
}
