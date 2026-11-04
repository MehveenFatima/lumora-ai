import { ImageResponse } from 'next/og'

export const alt = 'LumoraAI — Adaptive Learning, Reimagined'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

/** Link-preview card shown when the site is shared (WhatsApp, LinkedIn, Slack, X). */
export default function OpengraphImage() {
  const features = ['AI tutor grounded in your notes', 'Adaptive quizzes', 'Flashcards', 'Knowledge-gap study plan']
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: 72,
          background: 'linear-gradient(135deg, #080B12 0%, #0F1A33 60%, #13306B 100%)',
          color: '#F3F5F9',
          fontFamily: 'sans-serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: 18,
              background: '#2563EB',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 40,
              fontWeight: 700,
            }}
          >
            L
          </div>
          <div style={{ display: 'flex', fontSize: 40, fontWeight: 700 }}>
            Lumora<span style={{ color: '#60A5FA' }}>AI</span>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ fontSize: 68, fontWeight: 800, lineHeight: 1.08, letterSpacing: -1.5 }}>
            Learn smarter. Adapt faster.
          </div>
          <div style={{ fontSize: 68, fontWeight: 800, lineHeight: 1.08, color: '#60A5FA', letterSpacing: -1.5 }}>
            Master what matters.
          </div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
          {features.map((f) => (
            <div
              key={f}
              style={{
                display: 'flex',
                padding: '10px 20px',
                borderRadius: 999,
                border: '1px solid rgba(148, 163, 184, 0.35)',
                background: 'rgba(15, 23, 42, 0.6)',
                fontSize: 24,
                color: '#CBD5E1',
              }}
            >
              {f}
            </div>
          ))}
        </div>
      </div>
    ),
    size
  )
}
