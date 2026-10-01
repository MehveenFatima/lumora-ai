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
    // Document uploads are parsed, chunked and embedded inside the request, so they need longer than API calls.
    const isUpload = (req.headers.get('content-type') || '').includes('multipart/form-data')

    const fetchOptions: RequestInit = {
      method,
      headers,
      redirect: 'manual',
      signal: AbortSignal.timeout(isUpload ? 300000 : 60000),
    }

    // Attach body for modifying methods
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const contentType = req.headers.get('content-type') || ''
      if (contentType.includes('multipart/form-data')) {
        // Stream raw body array buffer to preserve multipart boundaries intact
        fetchOptions.body = await req.arrayBuffer()
      } else {
        const text = await req.text()
        if (text) {
          fetchOptions.body = text
        }
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
