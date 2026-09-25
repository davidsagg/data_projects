/*
 * Contexto de saúde do dia da atividade.
 *
 * A spec pede que a atividade individual carregue o sono da noite anterior e o
 * HRV da manhã — é o mesmo cruzamento da timeline, agora no nível da sessão. Um
 * treino fraco com 5h de sono e HRV 12 ms abaixo da média não foi um treino
 * fraco; foi o treino possível naquele dia, e sem esses dois números ao lado a
 * interpretação erra.
 */
import { useEffect, useState } from "react"

import FeedbackForm from "../week/FeedbackForm"
import { api } from "../../lib/api"
import { num, shortDate } from "../../lib/format"

export default function DayContext({ activity }) {
  const [health, setHealth] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (!activity?.started_at) return undefined
    let cancelled = false

    api.health
      .daily(400)
      .then((rows) => {
        if (cancelled) return
        const day = activity.started_at.slice(0, 10)
        setHealth({
          morning: rows.find((r) => r.date === day) || null,
          baseline: averageOf(rows, "hrv_rmssd_ms", 30),
        })
      })
      .catch(() => !cancelled && setHealth(null))

    return () => {
      cancelled = true
    }
  }, [activity?.started_at])

  useEffect(() => {
    if (!activity?.id) return undefined
    let cancelled = false
    api.feedback
      .forActivity(activity.id)
      .then((r) => !cancelled && setFeedback(r))
      .catch(() => !cancelled && setFeedback(null))
    return () => {
      cancelled = true
    }
  }, [activity?.id, reload])

  // O bloco aparece mesmo sem dados do Garmin: o feedback subjetivo é
  // justamente o que preenche o dia em que o relógio não sincronizou.
  const day = activity?.started_at?.slice(0, 10)
  if (!day) return null

  const morning = health?.morning
  const baseline = health?.baseline
  const hrvDelta =
    morning?.hrv_rmssd_ms != null && baseline != null
      ? morning?.hrv_rmssd_ms - baseline
      : null

  return (
    <section className="card card--static" style={{ display: "grid", gap: "var(--space-5)" }}>
      <header>
        <h2 className="card-title">Como o corpo chegou neste treino</h2>
        <p className="card-subtitle">
          {morning
            ? `Medidas de ${shortDate(morning.date)}`
            : "Sem sincronização do Garmin neste dia"}
        </p>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "var(--space-8)",
        }}
      >
        <Item
          label="Sono"
          value={morning?.sleep_hours ? formatSleep(morning?.sleep_hours) : "—"}
          context={
            morning?.sleep_quality_score
              ? `qualidade ${morning?.sleep_quality_score}/100`
              : null
          }
        />
        <Item
          label="HRV"
          value={morning?.hrv_rmssd_ms ? `${num(morning?.hrv_rmssd_ms, 0)} ms` : "—"}
          context={
            hrvDelta != null
              ? `${hrvDelta > 0 ? "+" : ""}${num(hrvDelta, 1)} vs. base de 30 dias`
              : morning?.hrv_status?.toLowerCase() || null
          }
          statusToken={
            hrvDelta != null && hrvDelta < -5 ? "--status-warning" : undefined
          }
        />
        <Item
          label="FC repouso"
          value={morning?.resting_hr_bpm ? `${morning?.resting_hr_bpm} bpm` : "—"}
        />
        <Item
          label="Body battery"
          value={morning?.body_battery ?? "—"}
          context={morning?.stress_level ? `estresse ${morning?.stress_level}` : null}
        />
      </div>

      <div style={{ paddingTop: "var(--space-5)", borderTop: "1px solid var(--border-subtle)" }}>
        <FeedbackForm
          date={day}
          activityId={activity.id}
          initial={feedback}
          onSaved={() => setReload((n) => n + 1)}
        />
      </div>
    </section>
  )
}

function Item({ label, value, context, statusToken }) {
  return (
    <div style={{ display: "grid", gap: "var(--space-2)" }}>
      <span className="label">{label}</span>
      <span
        className="figure tabular"
        style={{
          fontSize: "var(--fs-lead)",
          color: statusToken ? `var(${statusToken})` : undefined,
        }}
      >
        {value}
      </span>
      {context && (
        <span style={{ fontSize: "var(--fs-small)", color: "var(--text-secondary)" }}>
          {context}
        </span>
      )}
    </div>
  )
}

function averageOf(rows, key, days) {
  const values = rows
    .slice(0, days)
    .map((r) => r[key])
    .filter((v) => v !== null && v !== undefined)
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
}

function formatSleep(hours) {
  const total = Math.round(hours * 60)
  return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`
}
