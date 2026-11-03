import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { setApiToken, setUnauthorizedHandler, isApiError } from '../libs/api'
import {
  bootstrapAnonymousSession,
  normalizeAnonymousToken,
  readStoredSession,
  verifyToken,
  writeStoredSession,
  type SessionInfo,
} from '../libs/session'

type SessionStatus = 'loading' | 'ready' | 'error'

interface SessionContextValue {
  session: SessionInfo | null
  status: SessionStatus
  error: string | null
  notice: string | null
  /** Increments whenever the session/token changes so data hooks can refetch. */
  revision: number
  applyToken: (input: string) => Promise<SessionInfo>
  resetSession: () => Promise<void>
  refreshSession: () => Promise<void>
  dismissNotice: () => void
  clearError: () => void
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [status, setStatus] = useState<SessionStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const recovering = useRef(false)
  const booted = useRef(false)

  const commit = useCallback((next: SessionInfo | null) => {
    setSession(next)
    setApiToken(next?.token ?? null)
    writeStoredSession(next)
    setRevision((value) => value + 1)
  }, [])

  const recover = useCallback(async () => {
    if (recovering.current) return
    recovering.current = true
    try {
      setNotice('Session expired. A fresh anonymous session was created.')
      const { session: fresh, capturedToken } = await bootstrapAnonymousSession()
      commit(fresh)
      setStatus('ready')
      setError(null)
      if (!capturedToken) {
        setNotice('Connected, but the API did not return an anonymous token header.')
      }
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Could not reach the API.')
    } finally {
      recovering.current = false
    }
  }, [commit])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      void recover()
    })
    return () => setUnauthorizedHandler(null)
  }, [recover])

  useEffect(() => {
    if (booted.current) return
    booted.current = true

    const stored = readStoredSession()
    if (stored) {
      setSession(stored)
      setApiToken(stored.token)
      setStatus('ready')

      if (!stored.token) {
        void recover()
        return
      }

      // Revalidate in the background, without letting a 401 wipe a valid new session.
      verifyToken(stored.token)
        .then((fresh) => {
          setSession(fresh)
          setApiToken(fresh.token)
          writeStoredSession(fresh)
        })
        .catch((err) => {
          if (isApiError(err) && err.status === 401) {
            setNotice('The saved token was rejected. A fresh anonymous session was created.')
            void recover()
          }
          // Network errors keep the cached session usable.
        })
      return
    }

    bootstrapAnonymousSession()
      .then(({ session: fresh, capturedToken }) => {
        commit(fresh)
        setStatus('ready')
        if (!capturedToken) {
          setNotice('Connected, but the API did not return an anonymous token header.')
        }
      })
      .catch((err) => {
        setStatus('error')
        setError(err instanceof Error ? err.message : 'Could not reach the API.')
      })
  }, [commit, recover])

  const applyToken = useCallback(
    async (input: string) => {
      const normalized = normalizeAnonymousToken(input)
      const verified = await verifyToken(normalized)
      commit(verified)
      setStatus('ready')
      setError(null)
      setNotice('Token applied.')
      return verified
    },
    [commit],
  )

  const resetSession = useCallback(async () => {
    setNotice(null)
    setError(null)
    setStatus('loading')
    try {
      const { session: fresh } = await bootstrapAnonymousSession()
      commit(fresh)
      setStatus('ready')
      setNotice('A new anonymous session was created.')
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Could not reach the API.')
      throw err
    }
  }, [commit])

  const refreshSession = useCallback(async () => {
    if (!session?.token) return
    const verified = await verifyToken(session.token)
    setSession(verified)
    setApiToken(verified.token)
    writeStoredSession(verified)
  }, [session?.token])

  const value = useMemo<SessionContextValue>(
    () => ({
      session,
      status,
      error,
      notice,
      revision,
      applyToken,
      resetSession,
      refreshSession,
      dismissNotice: () => setNotice(null),
      clearError: () => setError(null),
    }),
    [session, status, error, notice, revision, applyToken, resetSession, refreshSession],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext)
  if (!context) throw new Error('useSession must be used inside SessionProvider')
  return context
}
