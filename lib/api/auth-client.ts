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
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

/** Turns a FastAPI error body (string detail or validation list) into one readable message. */
function readError(body: any, fallback: string): string {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
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
    throw new AuthError(readError(body, `Request failed (${res.status})`), res.status)
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
  async register(name: string, email: string, password: string): Promise<AuthUser> {
    const res = await authRequest<{ user: AuthUser }>('/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    })
    setCachedUser(res.user)
    return res.user
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
