import { cookies } from 'next/headers'

const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME || 'lumora_session'

/**
 * Request options for calling the FastAPI backend from a Server Component on behalf of the
 * signed-in user. Server Components must use these (never the browser-side caches in
 * workspace-service), so one user's data is never held in shared server memory.
 */
export async function serverAuthInit(): Promise<{ init: RequestInit; hasSession: boolean }> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value
  return {
    hasSession: Boolean(token),
    init: {
      cache: 'no-store',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  }
}
