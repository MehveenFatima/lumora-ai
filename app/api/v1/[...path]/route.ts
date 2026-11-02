import { NextRequest, NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000'

const HOP_BY_HOP_HEADERS = new Set([
  'host',
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'content-length',
])

function sanitizeHeaders(headers: Headers): Headers {
  const sanitized = new Headers()
  headers.forEach((val, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      sanitized.set(key, val)
    }
  })
  return sanitized
}

async function handleProxy(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> | { path?: string[] } }) {
  const resolvedParams = await Promise.resolve(params)
  const pathArray = resolvedParams?.path || []
  const subPath = pathArray.join('/')
  const search = req.nextUrl.search || ''
  const targetUrl = `${BACKEND_API_URL}/api/v1/${subPath}${search}`
  const method = req.method
  const startTime = Date.now()

  try {
    const headers = sanitizeHeaders(req.headers)
    // Document uploads (whole files or parts of one) take longer than API calls.
    const contentType = req.headers.get('content-type') || ''
    const isUpload = contentType.includes('multipart/form-data') || contentType.includes('application/octet-stream')

    const fetchOptions: RequestInit = {
      method,
      headers,
      redirect: 'manual',
      signal: AbortSignal.timeout(isUpload ? 300000 : 60000),
    }

    // Attach body for modifying methods. Bodies are forwarded as raw bytes, so multipart
    // boundaries and binary upload parts arrive unchanged.
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const body = await req.arrayBuffer()
      if (body.byteLength > 0) {
        fetchOptions.body = body
      }
    }

    const backendRes = await fetch(targetUrl, fetchOptions)
    const elapsedMs = Date.now() - startTime

    // Structured server-side logging (never log secrets)
    console.log(
      `[Next.js API Proxy] ${method} /api/v1/${subPath} -> ${targetUrl} [${backendRes.status}] (${elapsedMs}ms)`
    )

    const resHeaders = new Headers()
    backendRes.headers.forEach((val, key) => {
      // Avoid content-encoding mismatch issues if Next.js compresses
      if (!['content-encoding', 'content-length', 'set-cookie'].includes(key.toLowerCase())) {
        resHeaders.set(key, val)
      }
    })
    // Forward session cookies individually (Headers.set would merge or drop them)
    for (const cookie of backendRes.headers.getSetCookie()) {
      resHeaders.append('set-cookie', cookie)
    }

    // 204/205/304 responses must not carry a body
    const data = [204, 205, 304].includes(backendRes.status) ? null : await backendRes.arrayBuffer()
    return new NextResponse(data, {
      status: backendRes.status,
      statusText: backendRes.statusText,
      headers: resHeaders,
    })
  } catch (err: any) {
    const elapsedMs = Date.now() - startTime
    console.error(
      `[Next.js API Proxy ERROR] ${method} /api/v1/${subPath} -> ${targetUrl} FAILED (${elapsedMs}ms): ${err?.message || err}`
    )

    return NextResponse.json(
      {
        error: 'Backend Service Unavailable',
        code: 'BACKEND_UNAVAILABLE',
        detail: `Backend proxy was unable to reach the upstream backend service. (${err?.message || 'Connection refused'})`,
        status: 503,
        timestamp: new Date().toISOString(),
      },
      { status: 503 }
    )
  }
}

export const GET = handleProxy
export const POST = handleProxy
export const PUT = handleProxy
export const DELETE = handleProxy
export const PATCH = handleProxy
export const OPTIONS = handleProxy

// Uploads parse and embed documents inside the request; allow up to 60 s on serverless hosts
export const maxDuration = 60
