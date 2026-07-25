interface Point {
  label: string
  value: number
}

interface TimeSeriesChartProps {
  data: Point[]
  height?: number
}

export function TimeSeriesChart({ data, height = 180 }: TimeSeriesChartProps) {
  if (data.length === 0) {
    return <p className="text-sm text-muted">Sem dados suficientes ainda.</p>
  }

  const width = 640
  const padding = { top: 16, right: 16, bottom: 28, left: 16 }
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom
  const max = Math.max(1, ...data.map((d) => d.value))

  const stepX = data.length > 1 ? innerW / (data.length - 1) : 0
  const points = data.map((d, i) => ({
    x: padding.left + stepX * i,
    y: padding.top + innerH - (d.value / max) * innerH,
    ...d,
  }))

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
  const areaPath = `${linePath} L${points[points.length - 1].x},${padding.top + innerH} L${points[0].x},${padding.top + innerH} Z`
  const last = points[points.length - 1]
  const labelStep = Math.max(1, Math.ceil(points.length / 8))

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ height }}>
      <line
        x1={padding.left}
        y1={padding.top + innerH}
        x2={width - padding.right}
        y2={padding.top + innerH}
        stroke="var(--color-border)"
        strokeWidth={1}
      />
      <path d={areaPath} fill="var(--color-accent)" opacity={0.1} stroke="none" />
      <path d={linePath} fill="none" stroke="var(--color-accent)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last.x} cy={last.y} r={4} fill="var(--color-accent)" stroke="var(--color-surface)" strokeWidth={2} />
      <text x={last.x} y={last.y - 10} textAnchor="end" fontSize={12} fontWeight={600} fill="var(--color-text)">
        {last.value}
      </text>
      {points.map((p, i) => {
        const isLast = i === points.length - 1
        if (!isLast && i % labelStep !== 0) return null
        return (
          <text
            key={p.label}
            x={p.x}
            y={height - 8}
            textAnchor="middle"
            fontSize={11}
            fill="var(--color-muted)"
          >
            {p.label}
          </text>
        )
      })}
    </svg>
  )
}
