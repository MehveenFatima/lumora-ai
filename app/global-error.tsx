'use client'

/** Last-resort error page when the root layout itself fails; it must render its own document. */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, minHeight: '100dvh', display: 'grid', placeItems: 'center', background: '#080B12', color: '#E6E9F0', fontFamily: 'system-ui, sans-serif' }}>
        <div style={{ textAlign: 'center', padding: 24, maxWidth: 420 }}>
          <h1 style={{ fontSize: 22, margin: '0 0 8px' }}>LumoraAI could not load</h1>
          <p style={{ color: '#9AA3B2', fontSize: 14, lineHeight: 1.6, margin: '0 0 20px' }}>
            Please try again in a moment.
          </p>
          <button
            onClick={reset}
            style={{ background: '#3B82F6', color: '#080B12', border: 0, borderRadius: 12, padding: '10px 20px', fontWeight: 600, fontSize: 14, cursor: 'pointer' }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  )
}
