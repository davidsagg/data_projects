/*
 * Tooltip padrão dos gráficos.
 *
 * Um gráfico em HTML é interativo por natureza — a camada de hover é padrão,
 * não enfeite. O valor fica em tinta de texto e a cor da série aparece só no
 * quadradinho, para que texto nunca vista a cor da série.
 */

export default function VizTooltip({ active, payload, label, formatValue }) {
  if (!active || !payload?.length) return null

  return (
    <div className="viz-tooltip">
      {label !== undefined && <div className="viz-tooltip-title">{label}</div>}
      {payload
        .filter((entry) => entry.value !== null && entry.value !== undefined)
        .map((entry) => (
          <div className="viz-tooltip-row" key={entry.dataKey ?? entry.name}>
            <span className="viz-tooltip-label">
              <span
                className="viz-swatch"
                style={{ background: entry.color ?? entry.stroke }}
              />
              {entry.name}
            </span>
            <span className="viz-tooltip-value">
              {formatValue
                ? formatValue(entry.value, entry.dataKey, entry.payload)
                : entry.value}
            </span>
          </div>
        ))}
    </div>
  )
}
