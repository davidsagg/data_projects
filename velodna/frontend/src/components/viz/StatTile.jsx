/*
 * Bloco de número — um valor com rótulo, unidade e contexto opcional.
 *
 * Nem todo dado quer um gráfico: um único valor comunica melhor como número
 * grande do que como barra de um item só.
 */
import { useCssVar } from "../../lib/useCssVar"

export default function StatTile({
  label,
  value,
  unit,
  context,
  statusToken,
  hero = false,
}) {
  const statusColor = useCssVar(statusToken)

  return (
    <div className="card" style={{ display: "grid", gap: "var(--space-1)" }}>
      <span className="label">{label}</span>
      <div className={hero ? "figure figure-hero" : "figure"}>
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {context && (
        <span
          style={{
            fontSize: "var(--fs-micro)",
            color: statusColor || "var(--text-muted)",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          {/* Estado nunca é comunicado só pela cor: vem sempre com rótulo. */}
          {statusColor && (
            <span
              className="viz-swatch"
              style={{ background: statusColor, borderRadius: "50%" }}
            />
          )}
          {context}
        </span>
      )}
    </div>
  )
}
