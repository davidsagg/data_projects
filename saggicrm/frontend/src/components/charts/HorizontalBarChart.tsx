interface BarDatum {
  label: string
  value: number
}

interface HorizontalBarChartProps {
  data: BarDatum[]
  formatValue?: (value: number) => string
}

export function HorizontalBarChart({ data, formatValue = String }: HorizontalBarChartProps) {
  const max = Math.max(1, ...data.map((d) => d.value))

  return (
    <div className="flex flex-col gap-3">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3">
          <div className="w-32 shrink-0 truncate text-right text-sm text-muted" title={d.label}>
            {d.label}
          </div>
          <div className="relative h-4 flex-1 rounded-full bg-border/40">
            <div
              className="h-4 rounded-full bg-accent"
              style={{ width: `${Math.max(4, (d.value / max) * 100)}%` }}
            />
          </div>
          <div className="w-8 shrink-0 text-sm font-medium text-text">{formatValue(d.value)}</div>
        </div>
      ))}
      {data.length === 0 && <p className="text-sm text-muted">Sem dados suficientes ainda.</p>}
    </div>
  )
}
