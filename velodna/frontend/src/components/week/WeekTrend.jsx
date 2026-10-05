/*
 * Tendência de N semanas — barras verticais, uma por semana.
 *
 * Complementa a timeline: a timeline responde "como foi esta semana", esta
 * responde "esta semana é normal para mim?". Sem a segunda, 568 TSS não diz
 * nada — pode ser recorde ou rotina.
 */
import { dayMonth, num } from "../../lib/format"

/* Cor por estado da semana contra a média do período — o que o olho procura
   numa série de oito barras é o pico e o buraco, não a semana normal. */
const PEAK_RATIO = 1.15
const LIGHT_RATIO = 0.6

/* A referência é a mediana das outras semanas, não a média de todas: a semana
   em curso (ainda com 0 TSS na segunda-feira) puxaria a média para baixo e
   faria metade da série parecer pico. */
function barToken(tss, reference) {
  if (!reference) return "--ctl"
  if (tss >= reference * PEAK_RATIO) return "--status-warning"
  if (tss <= reference * LIGHT_RATIO) return "--seq-250"
  return "--ctl"
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b)
  if (!sorted.length) return null
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

const LEGEND = [
  { token: "--ctl", label: "normal" },
  { token: "--status-warning", label: `pico (≥ ${Math.round((PEAK_RATIO - 1) * 100)}% acima da mediana)` },
  { token: "--seq-250", label: "leve (≤ 60% da mediana)" },
]

export default function WeekTrend({ weeks, currentStart, onSelectWeek }) {
  if (!weeks?.length) {
    return <p className="muted" style={{ margin: 0 }}>Sem histórico.</p>
  }

  const values = weeks.map((w) => w.total_tss || 0)
  const max = Math.max(...values, 1)
  const average = values.reduce((a, b) => a + b, 0) / values.length
  const reference = median(
    weeks.filter((w) => w.week_start !== currentStart).map((w) => w.total_tss || 0),
  )

  const ramp = rampRate(values)

  return (
    <div style={{ display: "grid", gap: "var(--space-2)" }}>
      <div className="viz-legend" style={{ margin: 0 }}>
        {LEGEND.map((item) => (
          <span className="viz-legend-item" key={item.token}>
            <span className="viz-swatch" style={{ background: `var(${item.token})` }} />
            {item.label}
          </span>
        ))}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: "var(--space-2)",
          height: 80,
        }}
      >
        {weeks.map((week) => {
          const isCurrent = week.week_start === currentStart
          const height = Math.max((week.total_tss / max) * 74, 2)
          return (
            <button
              key={week.week_start}
              title={`${week.week_start}: ${num(week.total_tss, 0)} TSS`}
              onClick={() => onSelectWeek?.(week)}
              style={{
                appearance: "none",
                border: 0,
                padding: 0,
                background: "transparent",
                flex: 1,
                height: "100%",
                display: "flex",
                alignItems: "flex-end",
                cursor: onSelectWeek ? "pointer" : "default",
              }}
            >
              <span
                style={{
                  display: "block",
                  width: "100%",
                  height,
                  background: `var(${barToken(week.total_tss, reference)})`,
                  // A semana em foco ganha contorno, não outra cor: a cor já
                  // diz o estado dela, e um quarto azul confundiria com "normal".
                  boxShadow: isCurrent ? "0 0 0 2px var(--surface-1), 0 0 0 4px var(--text-primary)" : "none",
                  borderRadius: "var(--radius-sm) var(--radius-sm) 0 0",
                  /* A semana em foco ganha peso, não outra cor solta. */
                  outline: isCurrent ? "none" : "none",
                }}
              />
            </button>
          )
        })}
      </div>

      {/* Sem rótulo, oito barras flutuam sem dizer qual semana é qual. */}
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        {weeks.map((week) => (
          <span
            key={week.week_start}
            className="tabular"
            style={{
              flex: 1,
              textAlign: "center",
              fontSize: "var(--fs-micro)",
              color:
                week.week_start === currentStart
                  ? "var(--text-primary)"
                  : "var(--text-tertiary)",
            }}
          >
            {dayMonth(week.week_start)}
          </span>
        ))}
      </div>

      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        {weeks.map((week) => (
          <span
            key={week.week_start}
            className="tabular"
            style={{
              flex: 1,
              textAlign: "center",
              fontSize: "var(--fs-micro)",
              color: "var(--text-secondary)",
            }}
          >
            {num(week.total_tss, 0)}
          </span>
        ))}
      </div>

      <div
        style={{
          display: "flex",
          gap: "var(--space-8)",
          fontSize: "var(--fs-small)",
          color: "var(--text-secondary)",
        }}
      >
        <span className="tabular">média {num(average, 0)} TSS</span>
        {reference != null && <span className="tabular">mediana das outras {num(reference, 0)} TSS</span>}
        {ramp !== null && (
          <span className="tabular">
            ramp rate {ramp > 0 ? "+" : ""}
            {num(ramp, 1)}/semana
          </span>
        )}
      </div>
    </div>
  )
}

/**
 * Inclinação média por semana, via regressão linear simples.
 *
 * A diferença entre a primeira e a última semana seria mais simples e pior: uma
 * semana de recuperação no fim inverteria o sinal de um bloco inteiro de subida.
 */
function rampRate(values) {
  const n = values.length
  if (n < 3) return null

  const meanX = (n - 1) / 2
  const meanY = values.reduce((a, b) => a + b, 0) / n

  let numerator = 0
  let denominator = 0
  values.forEach((y, x) => {
    numerator += (x - meanX) * (y - meanY)
    denominator += (x - meanX) ** 2
  })

  return denominator === 0 ? null : numerator / denominator
}
