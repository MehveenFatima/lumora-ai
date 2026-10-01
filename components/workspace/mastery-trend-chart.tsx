'use client'

import { useMemo, useRef, useState } from 'react'

export interface MasteryPoint {
  date: string // YYYY-MM-DD
  mastery_percentage: number
}

const W = 640
const H = 220
const PAD = { top: 12, right: 16, bottom: 26, left: 34 }

function formatDay(iso: string) {
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/**
 * Single-series line chart of workspace mastery per day (0–100 %).
 * Hover or arrow keys move a crosshair that snaps to the nearest day; a table view is available.
 */
export function MasteryTrendChart({ points }: { points: MasteryPoint[] }) {
  const [active, setActive] = useState<number | null>(null)
  const [showTable, setShowTable] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)

  const geo = useMemo(() => {
    const innerW = W - PAD.left - PAD.right
    const innerH = H - PAD.top - PAD.bottom
    const step = points.length > 1 ? innerW / (points.length - 1) : 0
    const xy = points.map((p, i) => ({
      x: PAD.left + (points.length > 1 ? i * step : innerW / 2),
      y: PAD.top + innerH - (Math.max(0, Math.min(100, p.mastery_percentage)) / 100) * innerH,
    }))
    const path = xy.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
    return { xy, path, innerH }
  }, [points])

  if (points.length < 2) {
    return (
      <p className="py-10 text-center text-xs italic text-muted-foreground">
        Answer quiz questions on at least two different days to see your mastery trend.
      </p>
    )
  }

  const handleMove = (clientX: number) => {
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    const x = ((clientX - rect.left) / rect.width) * W
    let nearest = 0
    geo.xy.forEach((p, i) => {
      if (Math.abs(p.x - x) < Math.abs(geo.xy[nearest].x - x)) nearest = i
    })
    setActive(nearest)
  }

  const activePoint = active !== null ? points[active] : null
  const activeXY = active !== null ? geo.xy[active] : null
  const last = geo.xy[geo.xy.length - 1]
  const labelIdx = Array.from(new Set([0, Math.floor((points.length - 1) / 2), points.length - 1]))

  return (
    <div>
      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="h-52 w-full touch-none outline-none"
          role="img"
          aria-label={`Mastery over ${points.length} days, from ${points[0].mastery_percentage}% to ${points[points.length - 1].mastery_percentage}%`}
          tabIndex={0}
          onPointerMove={(e) => handleMove(e.clientX)}
          onPointerLeave={() => setActive(null)}
          onFocus={() => setActive(points.length - 1)}
          onBlur={() => setActive(null)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft') setActive((a) => Math.max(0, (a ?? points.length - 1) - 1))
            if (e.key === 'ArrowRight') setActive((a) => Math.min(points.length - 1, (a ?? 0) + 1))
          }}
        >
          {[0, 25, 50, 75, 100].map((v) => {
            const y = PAD.top + geo.innerH - (v / 100) * geo.innerH
            return (
              <g key={v}>
                <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} stroke="var(--border)" strokeWidth={1} />
                <text x={PAD.left - 8} y={y + 3} textAnchor="end" className="fill-muted-foreground text-[10px]">
                  {v}
                </text>
              </g>
            )
          })}
          {labelIdx.map((i) => (
            <text
              key={i}
              x={geo.xy[i].x}
              y={H - 6}
              textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}
              className="fill-muted-foreground text-[10px]"
            >
              {formatDay(points[i].date)}
            </text>
          ))}

          <path d={geo.path} fill="none" stroke="var(--primary)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          <circle cx={last.x} cy={last.y} r={4} fill="var(--primary)" stroke="var(--card)" strokeWidth={2} />

          {activeXY && (
            <g pointerEvents="none">
              <line x1={activeXY.x} x2={activeXY.x} y1={PAD.top} y2={PAD.top + geo.innerH} stroke="var(--muted-foreground)" strokeWidth={1} strokeDasharray="3 3" />
              <circle cx={activeXY.x} cy={activeXY.y} r={4.5} fill="var(--primary)" stroke="var(--card)" strokeWidth={2} />
            </g>
          )}
        </svg>

        {activePoint && activeXY && (
          <div
            className="pointer-events-none absolute top-1 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs shadow-soft"
            style={{
              left: `${(activeXY.x / W) * 100}%`,
              transform: activeXY.x > W * 0.7 ? 'translateX(calc(-100% - 8px))' : 'translateX(8px)',
            }}
          >
            <span className="block font-semibold tabular-nums text-foreground">{activePoint.mastery_percentage}%</span>
            <span className="block text-[10px] text-muted-foreground">{formatDay(activePoint.date)}</span>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => setShowTable((s) => !s)}
        className="mt-2 text-[11px] font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      >
        {showTable ? 'Hide table' : 'View as table'}
      </button>
      {showTable && (
        <table className="mt-2 w-full text-xs">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="py-1 font-medium">Day</th>
              <th className="py-1 text-right font-medium">Mastery</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.date} className="border-t border-border/60">
                <td className="py-1 text-foreground">{formatDay(p.date)}</td>
                <td className="py-1 text-right tabular-nums text-foreground">{p.mastery_percentage}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
