'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { User } from '@/types'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  setUser: (user: User) => void
  setTokens: (access: string, refresh: string) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      loading: false,

      login: async (email: string, password: string) => {
              set({ loading: true })
              const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ username: email, password }),
              })

              if (!res.ok) {
                const err = await res.json()
                set({ loading: false })
                throw new Error(err.detail || 'Login failed')
              }

              const data = await res.json()
              set({
                accessToken: data.access_token,
                refreshToken: data.refresh_token,
                isAuthenticated: true,
                loading: false,
              })

              // Fetch user info
              const userRes = await fetch('/api/auth/me', {
                headers: { Authorization: `Bearer ${data.access_token}` },
              })
              if (userRes.ok) {
                const user = await userRes.json()
                set({ user })
              }
            },

            logout: () => {
              set({
                user: null,
                accessToken: null,
                refreshToken: null,
                isAuthenticated: false,
                loading: false,
              })
            },

      setUser: (user: User) => set({ user, isAuthenticated: true, loading: false }),
      setTokens: (access: string, refresh: string) => set({ accessToken: access, refreshToken: refresh, isAuthenticated: true, loading: false }),
    }),
    {
      name: 'sigmaflow-auth',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

// Auth Context for React components
interface AuthContextType {
  user: User | null
  accessToken: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { user, accessToken, login, logout, loading } = useAuthStore()
  const [mounted, setMounted] = useState(false)

  // Initialize auth from localStorage on mount
  useEffect(() => {
    setMounted(true)
    const storedToken = localStorage.getItem('sigmaflow-auth')
    if (storedToken) {
      try {
        const parsed = JSON.parse(storedToken)
        if (parsed.state?.accessToken && parsed.state?.user) {
          useAuthStore.getState().setTokens(
            parsed.state.accessToken,
            parsed.state.refreshToken
          )
          useAuthStore.getState().setUser(parsed.state.user)
        }
      } catch (e) {
        localStorage.removeItem('sigmaflow-auth')
      }
    }
  }, [])

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600" />
      </div>
    )
  }

  return (
    <AuthContext.Provider value={{ user, accessToken, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const { user, accessToken, refreshToken, isAuthenticated, login, logout, setUser, setTokens, loading } = useAuthStore()
  
  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    login,
    logout,
    setUser,
    setTokens,
    loading,
  }
}