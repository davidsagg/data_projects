/*
 * Card de métrica — um valor com rótulo, contexto e a régua para lê-lo.
 *
 * Regra que este componente impõe: nenhum número sem contexto. "48" sozinho não
 * informa; "48 ms, +3 vs. média" informa.
 *
 * O `hint` é a régua — a faixa de referência que o guia do atleta traz como
 * "exemplo" em cada bloco. Sem ela, "TSS/hora 43" é um número que o atleta tem
 * de lembrar como interpretar; com ela, lê-se na hora. Fica num rodapé
 * visualmente rebaixado, porque é material de consulta e não de decisão.
 */
import Sparkline from "./Sparkline"

export default function MetricCard({
  label,
  value,
  unit,
  context,
  statusToken,
  onClick,
  trend,
  trendToken = "--ctl",
  trendBand,
  hint,
  badge,
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
      <span className="label">{label}</span>

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

      {trend?.length > 1 && (
        <Sparkline values={trend} token={trendToken} band={trendBand} />
      )}

      {context && (
        <span style={{ fontSize: "var(--fs-small)", color: "var(--text-secondary)" }}>
          {context}
        </span>
      )}

      {badge}

      {hint && (
        <span
          style={{
            fontSize: "var(--fs-micro)",
            lineHeight: 1.5,
            color: "var(--text-tertiary)",
            background: "var(--surface-sunken)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            padding: "var(--space-2) var(--space-3)",
            marginTop: "var(--space-1)",
          }}
        >
          {hint}
        </span>
      )}
    </div>
  )
}
