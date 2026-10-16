import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME || 'lumora_session'
const AUTH_PAGES = new Set(['/login', '/register', '/verify-email', '/forgot-password'])

/**
 * Optimistic route protection: send visitors without a session cookie to the sign-in page,
 * and signed-in users away from the auth pages. The API verifies the session on every request,
 * so this only decides which page to show.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value)

  if (pathname.startsWith('/dashboard') && !hasSession) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    url.search = `?next=${encodeURIComponent(pathname + search)}`
    return NextResponse.redirect(url)
  }

  if (AUTH_PAGES.has(pathname) && hasSession) {
    const url = request.nextUrl.clone()
    url.pathname = '/dashboard'
    url.search = ''
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/login', '/register', '/verify-email', '/forgot-password'],
}
