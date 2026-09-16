import axios from 'axios'

/**
 * Shared Axios instance.
 *
 * - Access token lives in memory only (never localStorage). A page reload loses
 *   it; `AuthProvider` re-bootstraps from the HttpOnly refresh cookie.
 * - On a 401 from a non-auth endpoint, the response interceptor tries
 *   `/auth/refresh` once, retries the original request, and otherwise calls the
 *   registered auth-failure handler (which redirects to /login).
 */

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const api = axios.create({ baseURL: API_BASE, withCredentials: true })

let accessToken: string | null = null
export const setAccessToken = (t: string | null) => {
  accessToken = t
}
export const getAccessToken = () => accessToken

let onAuthFailure: () => void = () => {}
export const setOnAuthFailure = (fn: () => void) => {
  onAuthFailure = fn
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

let inFlightRefresh: Promise<string | null> | null = null

/** Raw refresh call (bypasses the instance so it can't recurse through the interceptor). */
async function doRefresh(): Promise<string | null> {
  try {
    const { data } = await axios.post(
      `${API_BASE}/auth/refresh`,
      {},
      { withCredentials: true },
    )
    setAccessToken(data.access_token)
    return data.access_token as string
  } catch {
    setAccessToken(null)
    return null
  }
}

/**
 * Refresh the access token, coalescing concurrent callers onto one request.
 * The AuthProvider bootstrap and the 401 interceptor both call this on a cold
 * load; without the single-flight guard they fire two `/auth/refresh` calls and,
 * because refresh tokens rotate (single-use), the loser 401s and drops the
 * session.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!inFlightRefresh) {
    inFlightRefresh = doRefresh().finally(() => {
      inFlightRefresh = null
    })
  }
  return inFlightRefresh
}

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config
    const status = error.response?.status
    const isAuthPath = typeof original?.url === 'string' && original.url.includes('/auth/')

    if (status === 401 && original && !original._retry && !isAuthPath) {
      original._retry = true
      const token = await refreshAccessToken()
      if (token) {
        original.headers = original.headers ?? {}
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      }
      onAuthFailure()
    }
    return Promise.reject(error)
  },
)
