'use client'

import { useEffect, useState } from 'react'

export interface AuthUser {
  id: string
  email: string
  name: string
  created_at?: string | null
}

export class AuthError extends Error {
  status: number
  code?: string
  email?: string
  constructor(message: string, status: number, code?: string, email?: string) {
    super(message)
    this.status = status
    this.code = code
    this.email = email
  }
}

export interface RegisterResult {
  verificationRequired: boolean
  email: string
  emailSent: boolean
  user: AuthUser | null
}

export interface AuthConfig {
  email_verification_required: boolean
  password_reset_available: boolean
}

/** Turns a FastAPI error body (string detail or validation list) into one readable message. */
function readError(body: any, fallback: string): string {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message
  if (Array.isArray(detail) && detail.length > 0) {
    const msg = String(detail[0]?.msg || fallback)
    return msg.replace(/^Value error, /, '')
  }
  return fallback
}

async function authRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/v1/auth${path}`, {
    ...init,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
  })
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (res.status === 429) {
      throw new AuthError('Too many attempts. Please wait a few minutes and try again.', 429)
    }
    const detail = body?.detail
    throw new AuthError(
      readError(body, `Request failed (${res.status})`),
      res.status,
      detail && typeof detail === 'object' ? detail.code : undefined,
      detail && typeof detail === 'object' ? detail.email : undefined,
    )
  }
  return body as T
}

let cachedUser: AuthUser | null = null
let inflight: Promise<AuthUser | null> | null = null
const listeners = new Set<(u: AuthUser | null) => void>()

function setCachedUser(user: AuthUser | null) {
  cachedUser = user
  listeners.forEach((l) => l(user))
}

export const authClient = {
  async register(name: string, email: string, password: string): Promise<RegisterResult> {
    const res = await authRequest<{
      verification_required: boolean
      email: string
      email_sent: boolean
      user: AuthUser | null
    }>('/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    })
    if (res.user) setCachedUser(res.user)
    return {
      verificationRequired: res.verification_required,
      email: res.email,
      emailSent: res.email_sent,
      user: res.user,
    }
  },

  async config(): Promise<AuthConfig> {
    try {
      return await authRequest<AuthConfig>('/config')
    } catch {
      return { email_verification_required: false, password_reset_available: false }
    }
  },

  async verifyEmail(email: string, code: string): Promise<AuthUser> {
    const res = await authRequest<{ user: AuthUser }>('/verify-email', {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    })
    setCachedUser(res.user)
    return res.user
  },

  async resendVerification(email: string): Promise<string> {
    const res = await authRequest<{ message: string }>('/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
    return res.message
  },

  async forgotPassword(email: string): Promise<string> {
    const res = await authRequest<{ message: string }>('/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
    return res.message
  },

  async resetPassword(email: string, code: string, newPassword: string): Promise<AuthUser> {
    const res = await authRequest<{ user: AuthUser }>('/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email, code, new_password: newPassword }),
    })
    setCachedUser(res.user)
    return res.user
  },

  async updateProfile(name: string): Promise<AuthUser> {
    const user = await authRequest<AuthUser>('/me', { method: 'PATCH', body: JSON.stringify({ name }) })
    setCachedUser(user)
    return user
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    const res = await authRequest<{ user: AuthUser }>('/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    })
    setCachedUser(res.user)
  },

  async deleteAccount(password: string): Promise<void> {
    await authRequest<void>('/me', { method: 'DELETE', body: JSON.stringify({ password }) })
    setCachedUser(null)
  },

  async login(email: string, password: string): Promise<AuthUser> {
    const res = await authRequest<{ user: AuthUser }>('/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setCachedUser(res.user)
    return res.user
  },

  async logout(): Promise<void> {
    try {
      await authRequest<void>('/logout', { method: 'POST' })
    } finally {
      setCachedUser(null)
    }
  },

  /** Current user, or null when signed out. Cached for the lifetime of the page. */
  async me(): Promise<AuthUser | null> {
    if (cachedUser) return cachedUser
    if (!inflight) {
      inflight = authRequest<AuthUser>('/me')
        .then((u) => {
          setCachedUser(u)
          return u
        })
        .catch(() => null)
        .finally(() => {
          inflight = null
        })
    }
    return inflight
  },
}

/** React hook exposing the signed-in user (null while loading or when signed out). */
export function useCurrentUser(): AuthUser | null {
  const [user, setUser] = useState<AuthUser | null>(cachedUser)
  useEffect(() => {
    listeners.add(setUser)
    authClient.me().then(setUser)
    return () => {
      listeners.delete(setUser)
    }
  }, [])
  return user
}

export function initialsOf(name?: string | null): string {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

export function firstNameOf(name?: string | null): string {
  return (name || '').trim().split(/\s+/)[0] || 'there'
}
