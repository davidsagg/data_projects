/*
 * Card de métrica — um valor com rótulo, delta e contexto.
 *
 * Regra da spec que este componente impõe: nenhum número sem contexto. Se não
 * houver delta nem baseline, ao menos a unidade acompanha — "48" sozinho não
 * informa, "48 ms, +3 vs. média" informa.
 */
export default function MetricCard({
  label,
  value,
  unit,
  context,
  statusToken,
  onClick,
}) {
  const interactive = Boolean(onClick)

  return (
    <div
      className={interactive ? "card" : "card card--static"}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (interactive && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault()
          onClick()
        }
      }}
      style={{
        display: "grid",
        gap: "var(--space-3)",
        cursor: interactive ? "pointer" : "default",
      }}
    >
      <span className="card-title">{label}</span>

      <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-2)" }}>
        <span
          className="figure tabular"
          style={statusToken ? { color: `var(${statusToken})` } : undefined}
        >
          {value}
        </span>
        {unit && (
          <span style={{ fontSize: "var(--fs-body)", color: "var(--text-secondary)" }}>
            {unit}
          </span>
        )}
      </div>

      {context && (
        <span style={{ fontSize: "var(--fs-small)", color: "var(--text-secondary)" }}>
          {context}
        </span>
      )}
    </div>
  )
}
