/*
 * Tendência de N semanas — barras verticais, uma por semana.
 *
 * Complementa a timeline: a timeline responde "como foi esta semana", esta
 * responde "esta semana é normal para mim?". Sem a segunda, 568 TSS não diz
 * nada — pode ser recorde ou rotina.
 */
import { dayMonth, num } from "../../lib/format"

export default function WeekTrend({ weeks, currentStart, onSelectWeek }) {
  if (!weeks?.length) {
    return <p className="muted" style={{ margin: 0 }}>Sem histórico.</p>
  }

  const values = weeks.map((w) => w.total_tss || 0)
  const max = Math.max(...values, 1)
  const average = values.reduce((a, b) => a + b, 0) / values.length

  const ramp = rampRate(values)

  return (
    <div style={{ display: "grid", gap: "var(--space-5)" }}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: "var(--space-2)",
          height: 96,
        }}
      >
        {weeks.map((week) => {
          const isCurrent = week.week_start === currentStart
          const height = Math.max((week.total_tss / max) * 88, 2)
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
                  background: isCurrent ? "var(--ctl)" : "var(--seq-250)",
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
