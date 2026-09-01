'use client'

import { useId } from 'react'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

const weekly = [42, 48, 45, 58, 63, 61, 72, 78, 74, 83, 88, 92]
const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const subjects = [
  { name: 'Data Structures', value: 92, tone: 'bg-primary' },
  { name: 'Operating Systems', value: 78, tone: 'bg-chart-2' },
  { name: 'System Design', value: 64, tone: 'bg-chart-3' },
  { name: 'Aptitude & Reasoning', value: 48, tone: 'bg-chart-4' },
]

function buildPath(data: number[], width: number, height: number, pad: number) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const step = (width - pad * 2) / (data.length - 1)
  const points = data.map((d, i) => {
    const x = pad + i * step
    const y = height - pad - ((d - min) / range) * (height - pad * 2)
    return [x, y] as const
  })
  const line = points
    .map((p, i) => {
      if (i === 0) return `M ${p[0]},${p[1]}`
      const prev = points[i - 1]
      const cx = (prev[0] + p[0]) / 2
      return `C ${cx},${prev[1]} ${cx},${p[1]} ${p[0]},${p[1]}`
    })
    .join(' ')
  const area = `${line} L ${points[points.length - 1][0]},${height - pad} L ${points[0][0]},${height - pad} Z`
  return { line, area, points }
}

export function MasteryChart() {
  const gradientId = useId()
  const width = 620
  const height = 240
  const pad = 16
  const { line, area, points } = buildPath(weekly, width, height, pad)

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <section className="rounded-2xl border border-border bg-card p-5 shadow-soft lg:col-span-3">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-display text-base font-semibold text-foreground">Mastery over time</h3>
            <p className="mt-0.5 text-[13px] text-muted-foreground">Weighted across all active workspaces</p>
          </div>
          <Badge variant="success" size="md">
            +18% this quarter
          </Badge>
        </div>

        <div className="mt-5">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="h-[220px] w-full"
            preserveAspectRatio="none"
            role="img"
            aria-label="Line chart showing mastery increasing over twelve months"
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.35" />
                <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[0.25, 0.5, 0.75, 1].map((g) => (
              <line
                key={g}
                x1={pad}
                x2={width - pad}
                y1={(height - pad * 2) * g + pad}
                y2={(height - pad * 2) * g + pad}
                stroke="var(--border)"
                strokeDasharray="4 6"
              />
            ))}
            <path d={area} fill={`url(#${gradientId})`} />
            <path d={line} fill="none" stroke="var(--chart-1)" strokeWidth="2.5" strokeLinecap="round" />
            {points.map((p, i) => (
              <circle
                key={i}
                cx={p[0]}
                cy={p[1]}
                r={i === points.length - 1 ? 4.5 : 0}
                fill="var(--chart-1)"
                stroke="var(--card)"
                strokeWidth="2.5"
              />
            ))}
          </svg>
          <div className="mt-2 flex justify-between px-1 text-[11px] text-muted-foreground">
            {labels.filter((_, i) => i % 2 === 0).map((l) => (
              <span key={l}>{l}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-soft lg:col-span-2">
        <h3 className="font-display text-base font-semibold text-foreground">Mastery by subject</h3>
        <p className="mt-0.5 text-[13px] text-muted-foreground">Live estimate from adaptive quizzes</p>
        <div className="mt-5 flex flex-col gap-4">
          {subjects.map((s) => (
            <div key={s.name}>
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span className="font-medium text-foreground">{s.name}</span>
                <span className="tabular-nums text-muted-foreground">{s.value}%</span>
              </div>
              <Progress value={s.value} indicatorClassName={s.tone} />
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
