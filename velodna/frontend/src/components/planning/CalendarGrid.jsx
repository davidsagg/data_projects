/*
 * Calendário de treino — semanas em linhas, dias em colunas.
 *
 * A grade existe para expor o **ritmo**: blocos de carga, dias de descanso e
 * furos aparecem como padrão espacial, coisa que uma lista cronológica não
 * mostra. O total da semana fica à direita porque é assim que se planeja
 * ciclismo — a semana é a unidade, não o dia.
 *
 * O estado de cada dia nunca é comunicado só pela cor: a célula traz o número
 * e o rótulo textual vai no `title`, e a legenda nomeia cada estado.
 */
import { useMemo } from "react"

import { num } from "../../lib/format"
import { DAY_STATUS } from "../../lib/planningStatus"

const WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


/** Agrupa os dias em semanas que começam na segunda-feira. */
function toWeeks(days) {
  if (!days?.length) return []

  const weeks = []
  let current = []

  days.forEach((day) => {
    const weekday = (new Date(`${day.date}T12:00:00`).getDay() + 6) % 7
    if (!current.length && weekday > 0) {
      // Preenche o início da primeira semana para alinhar as colunas.
      current = Array.from({ length: weekday }, () => null)
    }
    current.push(day)
    if (weekday === 6) {
      weeks.push(current)
      current = []
    }
  })

  if (current.length) weeks.push(current)
  return weeks
}

export default function CalendarGrid({ calendar }) {
  const weeks = useMemo(() => toWeeks(calendar?.days), [calendar])

  if (!weeks.length) {
    return (
      <section className="card">
        <h2 className="card-title">Calendário</h2>
        <p className="muted">Sem período carregado.</p>
      </section>
    )
  }

  const todayIso = new Date().toISOString().slice(0, 10)

  return (
    <section className="card">
      <h2 className="card-title">Calendário</h2>
      <p className="card-subtitle">
        {num(calendar.actual_tss, 0)} TSS realizados de{" "}
        {num(calendar.planned_tss, 0)} planejados no período
      </p>

      <div className="viz-legend" style={{ marginBottom: "var(--space-3)" }}>
        {Object.entries(DAY_STATUS)
          .filter(([key]) => key !== "in_progress")
          .map(([key, s]) => (
            <span className="viz-legend-item" key={key}>
              <span
                className="viz-swatch"
                style={{
                  background: s.token ? `var(${s.token})` : "transparent",
                  border: s.token ? "none" : "1px solid var(--axis)",
                }}
              />
              {s.label}
            </span>
          ))}
      </div>

      <div className="scroll-x">
        <table className="data" style={{ tableLayout: "fixed", minWidth: 620 }}>
          <thead>
            <tr>
              {WEEKDAYS.map((d) => (
                <th key={d} style={{ textAlign: "center" }}>
                  {d}
                </th>
              ))}
              <th style={{ width: 92 }}>semana</th>
            </tr>
          </thead>
          <tbody>
            {weeks.map((week, index) => {
              const weekActual = week.reduce(
                (acc, d) => acc + (d?.actual_tss || 0),
                0,
              )
              const weekPlanned = week.reduce(
                (acc, d) => acc + (d?.planned_tss || 0),
                0,
              )
              return (
                <tr key={index}>
                  {Array.from({ length: 7 }, (_, i) => week[i] ?? null).map(
                    (day, i) => (
                      <DayCell key={i} day={day} isToday={day?.date === todayIso} />
                    ),
                  )}
                  <td style={{ fontWeight: 600 }}>
                    {num(weekActual, 0)}
                    {weekPlanned > 0 && (
                      <span className="muted"> / {num(weekPlanned, 0)}</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/** Uma célula do calendário: dia do mês, TSS e marcação de estado. */
function DayCell({ day, isToday }) {
  if (!day) return <td />

  const status = DAY_STATUS[day.status] || DAY_STATUS.rest
  const dayOfMonth = Number(day.date.slice(8, 10))
  const title = [
    day.date,
    status.label,
    day.planned_tss ? `plano ${num(day.planned_tss, 0)} TSS` : null,
    day.actual_tss ? `feito ${num(day.actual_tss, 0)} TSS` : null,
  ]
    .filter(Boolean)
    .join(" · ")

  return (
    <td
      title={title}
      style={{
        textAlign: "center",
        verticalAlign: "top",
        padding: "var(--space-1)",
        outline: isToday ? "1px solid var(--text-secondary)" : undefined,
        borderRadius: isToday ? "var(--radius-sm)" : undefined,
      }}
    >
      <div style={{ fontSize: "var(--fs-micro)", color: "var(--text-muted)" }}>
        {dayOfMonth}
      </div>
      <div
        style={{
          height: 4,
          borderRadius: 2,
          margin: "2px auto",
          width: "70%",
          background: status.token ? `var(${status.token})` : "var(--gridline)",
        }}
      />
      <div style={{ fontWeight: day.actual_tss ? 600 : 400 }}>
        {day.actual_tss ? num(day.actual_tss, 0) : ""}
        {!day.actual_tss && day.planned_tss ? (
          <span className="muted">{num(day.planned_tss, 0)}</span>
        ) : null}
      </div>
    </td>
  )
}
