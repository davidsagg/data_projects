/*
 * Visão Planejamento — o que foi planejado, o que foi feito e o que virá.
 */
import { useCallback, useEffect, useState } from "react"

import CalendarGrid from "../components/planning/CalendarGrid"
import ProjectionPanel from "../components/planning/ProjectionPanel"
import { api } from "../lib/api"
import { num } from "../lib/format"
import { statusLabel } from "../lib/planningStatus"

/** Intervalo do calendário: algumas semanas para trás e para a frente. */
function calendarRange(weeksBack = 6, weeksAhead = 2) {
  const today = new Date()
  const monday = new Date(today)
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7))

  const start = new Date(monday)
  start.setDate(monday.getDate() - weeksBack * 7)

  const end = new Date(monday)
  end.setDate(monday.getDate() + weeksAhead * 7 + 6)

  return { start: iso(start), end: iso(end) }
}

const iso = (d) => d.toISOString().slice(0, 10)

export default function PlanningView() {
  const [calendar, setCalendar] = useState(null)
  const [form, setForm] = useState({ date: iso(new Date()), name: "", planned_tss: "" })
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    api.planning.calendar(calendarRange()).then(setCalendar).catch(() => setCalendar(null))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const addWorkout = (event) => {
    event.preventDefault()
    setSaving(true)
    api.planning
      .addWorkout({
        date: form.date,
        name: form.name || null,
        planned_tss: form.planned_tss ? Number(form.planned_tss) : null,
      })
      .then(() => {
        setForm((f) => ({ ...f, name: "", planned_tss: "" }))
        load()
      })
      .finally(() => setSaving(false))
  }

  const reconcile = () => {
    api.planning.reconcile().then(load)
  }

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      <ProjectionPanel />

      {calendar ? <CalendarGrid calendar={calendar} /> : <p className="muted">Carregando…</p>}

      <section className="card">
        <h2 className="card-title">Planejar um treino</h2>
        <p className="card-subtitle">
          O TSS planejado alimenta a projeção e a aderência do calendário
        </p>

        <form
          onSubmit={addWorkout}
          className="toolbar"
          style={{ marginBottom: 0, alignItems: "flex-end" }}
        >
          <label style={labelStyle}>
            Data
            <input
              type="date"
              required
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
              style={{ ...inputStyle, width: 140 }}
            />
          </label>
          <label style={labelStyle}>
            Nome
            <input
              type="text"
              placeholder="Ex.: Intervalado 4×8"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              style={{ ...inputStyle, width: 180 }}
            />
          </label>
          <label style={labelStyle}>
            TSS
            <input
              type="number"
              min="0"
              value={form.planned_tss}
              onChange={(e) => setForm({ ...form, planned_tss: e.target.value })}
              style={inputStyle}
            />
          </label>
          <button type="submit" disabled={saving} style={buttonStyle}>
            {saving ? "Salvando…" : "Adicionar"}
          </button>
          <button type="button" onClick={reconcile} style={buttonStyle}>
            Conciliar com atividades
          </button>
        </form>
      </section>

      {calendar && <PlannedList calendar={calendar} />}
    </div>
  )
}

/** Treinos planejados do período, em tabela. */
function PlannedList({ calendar }) {
  const planned = calendar.days
    .filter((d) => d.planned_workouts?.length)
    .flatMap((d) => d.planned_workouts.map((w) => ({ ...w, day: d })))

  if (!planned.length) {
    return (
      <section className="card">
        <h2 className="card-title">Treinos planejados</h2>
        <p className="muted">Nenhum treino planejado no período.</p>
      </section>
    )
  }

  return (
    <section className="card">
      <h2 className="card-title">Treinos planejados</h2>
      <div className="scroll-x">
        <table className="data">
          <thead>
            <tr>
              <th>Data</th>
              <th>Treino</th>
              <th>TSS previsto</th>
              <th>TSS realizado</th>
              <th>Aderência</th>
              <th>Situação</th>
            </tr>
          </thead>
          <tbody>
            {planned.map((w) => (
              <tr key={w.id}>
                <td>{w.date}</td>
                <td>{w.name || "—"}</td>
                <td>{num(w.planned_tss, 0)}</td>
                <td>{num(w.day.actual_tss, 0)}</td>
                <td>
                  {w.day.compliance_pct !== null
                    ? `${num(w.day.compliance_pct, 0)}%`
                    : "—"}
                </td>
                <td>{statusLabel(w.day.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

const labelStyle = {
  display: "grid",
  gap: 2,
  fontSize: "var(--fs-micro)",
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.03em",
}

const inputStyle = {
  font: "inherit",
  fontSize: "var(--fs-small)",
  padding: "4px 6px",
  width: 84,
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "var(--surface-1)",
  color: "var(--text-primary)",
}

const buttonStyle = {
  font: "inherit",
  fontSize: "var(--fs-small)",
  fontWeight: 600,
  padding: "6px 14px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "var(--surface-sunken)",
  color: "var(--text-primary)",
  cursor: "pointer",
}
