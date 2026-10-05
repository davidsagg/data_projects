/*
 * Célula de métrica compacta — rótulo, valor, etiqueta de estado e tendência.
 *
 * Substitui o MetricCard no Resumo. O card antigo trazia a régua de leitura
 * ("perto de 40 indica base...") como um bloco de texto fixo, e doze blocos
 * desses empurravam a semana para fora da tela. A régua continua lá, num ⓘ que
 * abre ao passar o mouse ou focar: é material de consulta, não de leitura
 * diária. O estado vai numa etiqueta colorida, no mesmo vocabulário do Panorama
 * — ícone e fundo carregam o tom, o texto diz o que é.
 */
import { Pill } from "./GoalPill"
import Sparkline from "./Sparkline"

export default function StatCell({
  label,
  value,
  unit,
  sub,
  tone,
  pill,
  trend,
  trendToken = "--ctl",
  hint,
  accentToken,
}) {
  return (
    <div
      className="card card--static"
      style={{
        display: "grid",
        gap: 4,
        alignContent: "start",
        padding: "var(--space-3) var(--space-4)",
        // A cor da série acompanha o card numa borda fina à esquerda: a mesma
        // cor da linha no gráfico de tendência e nos gráficos do Fitness.
        borderLeft: accentToken ? `3px solid var(${accentToken})` : undefined,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
        <span className="label" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {label}
        </span>
        {hint && (
          <span
            className="hint-dot"
            tabIndex={0}
            role="note"
            aria-label={hint}
            data-hint={hint}
          >
            i
          </span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: 6, flexWrap: "wrap" }}>
        <span className="figure" style={{ fontSize: "1.5rem" }}>
          {value}
          {unit && <span className="unit">{unit}</span>}
        </span>
        {trend?.length > 1 && (
          <span style={{ marginLeft: "auto", alignSelf: "center" }}>
            <Sparkline values={trend} token={trendToken} width={72} height={20} />
          </span>
        )}
      </div>

      {sub && (
        <span
          style={{
            fontSize: "var(--fs-micro)",
            color: "var(--text-tertiary)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {sub}
        </span>
      )}

      {pill && <Pill tone={tone}>{pill}</Pill>}
    </div>
  )
}
