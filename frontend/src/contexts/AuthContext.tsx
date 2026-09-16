import { createContext } from 'react'

export interface AuthUser {
  id: string
  email: string
}

export interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  onboarded: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  markOnboarded: () => void
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null)
