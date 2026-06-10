const BASE = import.meta.env.VITE_API_BASE_URL as string | undefined

if (!BASE) {
  console.warn(
    'VITE_API_BASE_URL is not set; API calls may fail. Set it in apps/web/.env',
  )
}

export class MOError extends Error {
  readonly status: number
  readonly errorCode: string
  readonly detail: unknown

  constructor(status: number, errorCode: string, detail: unknown) {
    const message =
      typeof detail === 'string'
        ? detail
        : errorCode || `Request failed with status ${status}`
    super(message)
    this.name = 'MOError'
    this.status = status
    this.errorCode = errorCode
    this.detail = detail
  }
}

async function toMOError(res: Response): Promise<MOError> {
  let body: { error?: string; detail?: unknown } = {}
  try {
    body = (await res.json()) as { error?: string; detail?: unknown }
  } catch {
    /* ignore parse errors */
  }
  return new MOError(
    res.status,
    body.error ?? 'request_failed',
    body.detail ?? res.statusText,
  )
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE ?? ''}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    throw await toMOError(res)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return res.json() as Promise<T>
}

export function getApiBaseUrl(): string {
  return BASE ?? ''
}
