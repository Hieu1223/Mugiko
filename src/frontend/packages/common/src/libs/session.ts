import { apiRequest, isApiError } from './api'
import type { AuthType, Role, UserProfile } from './types'

export const SESSION_STORAGE_KEY = 'mugiko.session'

export interface SessionInfo {
  token: string | null
  userId: string
  name?: string
  bio?: string
  email?: string
  role: Role
  authType?: AuthType
  joinedAt?: string
}

export class TokenFormatError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'TokenFormatError'
  }
}

export function normalizeAnonymousToken(input: string): string {
  let value = input.trim().replace(/^Bearer\s+/i, '').trim()
  if (!value) throw new TokenFormatError('Paste a token first.')
  if (/\s/.test(value)) throw new TokenFormatError('A token cannot contain spaces.')

  if (/^(user|admin)-/i.test(value)) {
    throw new TokenFormatError('Only anonymous tokens are accepted for now.')
  }
  if (!value.startsWith('anonymous-')) value = `anonymous-${value}`
  if (value.length <= 'anonymous-'.length) {
    throw new TokenFormatError('That token looks incomplete.')
  }
  return value
}

export function maskToken(token: string | null): string {
  if (!token) return '—'
  if (token.length <= 18) return `${token.slice(0, 8)}…`
  return `${token.slice(0, 12)}…${token.slice(-4)}`
}

export function profileToSession(profile: UserProfile | null, token: string | null): SessionInfo {
  if (!profile) {
    return {
      token,
      userId: token ? token.replace(/^anonymous-/, '').slice(0, 24) : 'anonymous',
      role: 'anonymous',
      authType: 'anonymous',
    }
  }
  return {
    token,
    userId: profile.user_id,
    name: profile.name,
    bio: profile.bio,
    email: profile.email,
    role: profile.role,
    authType: profile.auth_type,
    joinedAt: profile.joined_at,
  }
}

export function readStoredSession(): SessionInfo | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<SessionInfo>
    if (!parsed || typeof parsed !== 'object' || !parsed.userId) return null
    return {
      token: typeof parsed.token === 'string' ? parsed.token : null,
      userId: parsed.userId,
      name: parsed.name,
      bio: parsed.bio,
      email: parsed.email,
      role: (parsed.role as Role) || 'anonymous',
      authType: parsed.authType,
      joinedAt: parsed.joinedAt,
    }
  } catch {
    return null
  }
}

export function writeStoredSession(session: SessionInfo | null) {
  try {
    if (!session) localStorage.removeItem(SESSION_STORAGE_KEY)
    else localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
  } catch {
    // Storage can be unavailable in private modes; the in-memory session still works.
  }
}

function tokenFromHeader(headers: Headers): string | null {
  const header = headers.get('authorization') || headers.get('Authorization')
  if (!header) return null
  const raw = header.replace(/^Bearer\s+/i, '').trim()
  if (!raw) return null
  if (/^(user|admin|anonymous)-/i.test(raw)) return raw
  return `anonymous-${raw}`
}

export interface BootstrapResult {
  session: SessionInfo
  capturedToken: boolean
}

/** Creates a fresh anonymous session. The API returns the new token in a response header. */
export async function bootstrapAnonymousSession(): Promise<BootstrapResult> {
  const result = await apiRequest<UserProfile>('/users/me', { auth: false })
  const token = tokenFromHeader(result.headers)
  const session = profileToSession(result.data, token)
  return { session, capturedToken: Boolean(token) }
}

export async function verifyToken(token: string): Promise<SessionInfo> {
  const result = await apiRequest<UserProfile>('/users/me', { token, auth: false })
  return profileToSession(result.data, token)
}

export function isUnauthorized(error: unknown): boolean {
  return isApiError(error) && error.status === 401
}

export function isForbidden(error: unknown): boolean {
  return isApiError(error) && error.status === 403
}
