/*
 * Moldura comum dos gráficos: título, subtítulo, legenda e ação opcional.
 *
 * A legenda vive aqui, e não dentro de cada gráfico, para garantir a regra:
 * duas ou mais séries sempre têm legenda, então a identidade nunca depende
 * só da cor.
 *
 * O `table` opcional dá ao gráfico uma visão em tabela, aberta por um botão
 * discreto. É o alívio que o guia de dataviz exige quando uma cor fica abaixo
 * de 3:1 sobre a superfície, e é como se lê um valor exato sem passar o mouse
 * em treze barras. Formato: { columns: [{ key, label, num?, format? }], rows }.
 */
import { useState } from "react"

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

export function DataTable({ columns, rows }) {
  return (
    <div className="scroll-x">
      <table className="data">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? "num" : undefined}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id ?? i}>
              {columns.map((c) => (
                <td key={c.key} className={c.num ? "num" : undefined}>
                  {c.format ? c.format(row[c.key], row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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
  table,
}) {
  const [showTable, setShowTable] = useState(false)

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
        <div style={{ minWidth: 0, marginBottom: "var(--space-3)" }}>
          <h2 className="card-title">{title}</h2>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
        {action}
      </header>
      <Legend series={series} />
      {children}
      {table?.rows?.length > 0 && (
        <>
          <button
            type="button"
            className="table-toggle"
            aria-expanded={showTable}
            onClick={() => setShowTable((v) => !v)}
          >
            {showTable ? "Ocultar tabela" : "Ver como tabela"}
          </button>
          {showTable && <DataTable columns={table.columns} rows={table.rows} />}
        </>
      )}
    </section>
  )
}
