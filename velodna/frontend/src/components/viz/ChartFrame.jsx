/*
 * Moldura comum dos gráficos: título, subtítulo, legenda e ação opcional.
 *
 * A legenda vive aqui, e não dentro de cada gráfico, para garantir a regra:
 * duas ou mais séries sempre têm legenda, então a identidade nunca depende
 * só da cor.
 */

export function Legend({ series }) {
  if (!series || series.length < 2) return null
  return (
    <div className="viz-legend">
      {series.map((s) => (
        <span className="viz-legend-item" key={s.label}>
          <span className="viz-swatch" style={{ background: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  )
}

export default function ChartFrame({
  title,
  subtitle,
  series,
  action,
  children,
  style,
}) {
  return (
    <section className="card" style={style}>
      <header
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "var(--space-3)",
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <h2 className="card-title">{title}</h2>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
        {action}
      </header>
      <Legend series={series} />
      {children}
    </section>
  )
}
