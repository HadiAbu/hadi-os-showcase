import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, refreshAccessToken, setAccessToken, setOnAuthFailure } from '../lib/api'
import { AuthContext, type AuthUser } from './AuthContext'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [onboarded, setOnboarded] = useState(false)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    setOnAuthFailure(() => {
      setAccessToken(null)
      setUser(null)
      navigate('/login')
    })
  }, [navigate])

  const loadSession = useCallback(async () => {
    const me = await api.get('/auth/me')
    setUser(me.data)
    const state = await api.get('/onboarding/state')
    setOnboarded(Boolean(state.data.completed))
  }, [])

  // Bootstrap from the HttpOnly refresh cookie on first load.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const token = await refreshAccessToken()
      if (token) {
        try {
          if (!cancelled) await loadSession()
        } catch {
          if (!cancelled) setUser(null)
        }
      }
      if (!cancelled) setLoading(false)
    })()
    return () => {
      cancelled = true
    }
  }, [loadSession])

  const login = useCallback(
    async (email: string, password: string) => {
      const { data } = await api.post('/auth/login', { email, password })
      setAccessToken(data.access_token)
      await loadSession()
    },
    [loadSession],
  )

  const register = useCallback(
    async (email: string, password: string) => {
      await api.post('/auth/register', { email, password })
      await login(email, password)
    },
    [login],
  )

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      /* ignore — clear locally regardless */
    }
    setAccessToken(null)
    setUser(null)
    setOnboarded(false)
    navigate('/login')
  }, [navigate])

  const markOnboarded = useCallback(() => setOnboarded(true), [])

  const value = useMemo(
    () => ({ user, loading, onboarded, login, register, logout, markOnboarded }),
    [user, loading, onboarded, login, register, logout, markOnboarded],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
