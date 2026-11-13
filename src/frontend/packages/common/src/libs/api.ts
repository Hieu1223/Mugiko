const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

let authToken: string | null = null
let unauthorizedHandler: (() => void) | null = null

export class ApiError extends Error {
  status: number
  detail: string
  payload: unknown

  constructor(status: number, detail: string, payload?: unknown) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.payload = payload
  }
}

export interface RequestOptions {
  method?: string
  body?: unknown
  query?: Record<string, string | number | boolean | null | undefined>
  signal?: AbortSignal
  headers?: HeadersInit
  /** false skips the Authorization header entirely. */
  auth?: boolean
  /** Use this token instead of the current session token. */
  token?: string | null
  /** Absolute API base (e.g. http://localhost:8090/api/v1). Defaults to VITE_API_BASE_URL. */
  base?: string
}

export interface ApiResult<T> {
  data: T
  status: number
  headers: Headers
}

export function setApiToken(token: string | null) {
  authToken = token
}

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler
}

export function apiUrl(path: string, query?: RequestOptions['query'], base = API_BASE): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  const params = new URLSearchParams()
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
    }
  }
  const search = params.toString()
  return `${base}${cleanPath}${search ? `?${search}` : ''}`
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function errorDetail(error: unknown, fallback = 'Something went wrong.'): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Your session is not valid anymore.'
    if (error.status === 403) return 'This action needs a full user account.'
    if (error.status === 404) return 'Not found.'
    return error.detail || fallback
  }
  if (error instanceof TypeError) {
    return 'The API could not be reached. Check that the backend is running.'
  }
  if (error instanceof Error) return error.message || fallback
  return fallback
}

async function parseBody(response: Response): Promise<unknown> {
  const type = response.headers.get('content-type') || ''
  if (response.status === 204) return undefined
  if (type.includes('application/json')) {
    try {
      return await response.json()
    } catch {
      return undefined
    }
  }
  const text = await response.text()
  return text || undefined
}

function detailFrom(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join(', ')
    }
  }
  if (typeof payload === 'string' && payload) return payload
  return fallback
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  const { method = 'GET', body, query, signal, auth = true, token, base } = options
  const headers = new Headers(options.headers)
  const effectiveToken = token !== undefined ? token : auth ? authToken : null

  if (effectiveToken) headers.set('Authorization', `Bearer ${effectiveToken}`)
  if (body !== undefined && !(body instanceof FormData)) headers.set('Content-Type', 'application/json')

  const response = await fetch(apiUrl(path, query, base), {
    method,
    headers,
    signal,
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
  })

  const payload = await parseBody(response)

  if (!response.ok) {
    if (response.status === 401 && auth && effectiveToken) unauthorizedHandler?.()
    throw new ApiError(
      response.status,
      detailFrom(payload, `Request failed (${response.status}).`),
      payload,
    )
  }

  return { data: payload as T, status: response.status, headers: response.headers }
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const result = await apiRequest<T>(path, options)
  return result.data
}

export interface ServerEvent {
  event: string
  data: string
}

export interface StreamOptions {
  query?: RequestOptions['query']
  signal?: AbortSignal
  headers?: HeadersInit
  auth?: boolean
  token?: string | null
}

const EVENT_STREAM_CONTENT_TYPE = 'text/event-stream'

/**
 * Reads a Server-Sent Events response with fetch. EventSource cannot send the
 * Authorization header the API requires, so the stream is parsed by hand.
 * Return false from onEvent to stop reading early.
 */
export async function streamServerEvents(
  path: string,
  options: StreamOptions,
  onEvent: (event: ServerEvent) => boolean | void,
): Promise<void> {
  const { query, signal, auth = true, token } = options
  const headers = new Headers(options.headers)
  const effectiveToken = token !== undefined ? token : auth ? authToken : null

  if (effectiveToken) headers.set('Authorization', `Bearer ${effectiveToken}`)
  headers.set('Accept', EVENT_STREAM_CONTENT_TYPE)
  headers.set('Cache-Control', 'no-cache')

  const response = await fetch(apiUrl(path, query), { headers, signal })

  if (!response.ok) {
    const payload = await parseBody(response)
    if (response.status === 401 && auth && effectiveToken) unauthorizedHandler?.()
    throw new ApiError(
      response.status,
      detailFrom(payload, `Request failed (${response.status}).`),
      payload,
    )
  }

  if (!response.body) {
    throw new ApiError(response.status, 'Streaming is not supported.', undefined)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = ''
  let dataLines: string[] = []
  let stopped = false

  const dispatch = () => {
    const data = dataLines.join('\n')
    const event = eventName || 'message'
    eventName = ''
    dataLines = []
    if (!data || stopped) return
    if (onEvent({ event, data }) === false) stopped = true
  }

  const readLine = (line: string) => {
    if (!line) {
      dispatch()
      return
    }
    if (line.startsWith(':')) return
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') eventName = value
    else if (field === 'data') dataLines.push(value)
  }

  const drainLines = (flush: boolean) => {
    while (buffer) {
      const cr = buffer.indexOf('\r')
      const lf = buffer.indexOf('\n')
      if (cr === -1 && lf === -1) break

      let index: number
      let skip: number
      if (cr !== -1 && (lf === -1 || cr < lf)) {
        // A trailing CR may be the first half of a CRLF pair split across
        // chunks; wait for the next chunk unless the stream has ended.
        if (cr === buffer.length - 1 && !flush) break
        index = cr
        skip = buffer[cr + 1] === '\n' ? 2 : 1
      } else {
        index = lf
        skip = 1
      }

      const line = buffer.slice(0, index)
      buffer = buffer.slice(index + skip)
      readLine(line)
      if (stopped) return
    }
  }

  try {
    while (!stopped) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      drainLines(false)
      if (stopped) break
    }

    buffer += decoder.decode()
    drainLines(true)
  } finally {
    if (stopped) await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}

export async function checkHealth(): Promise<boolean> {
  const url = (import.meta.env.VITE_HEALTH_URL as string | undefined) || '/health'
  try {
    const response = await fetch(url)
    if (!response.ok) return false
    const data = (await response.json()) as { status?: string }
    return data.status === 'ok' || response.ok
  } catch {
    return false
  }
}
