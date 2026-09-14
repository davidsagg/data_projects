/*
 * Visão Hoje — o estado do atleta agora e o que ele sugere fazer.
 *
 * Ordem de leitura: prontidão e recomendação primeiro, alertas logo abaixo
 * (só aparecem quando existem), depois a semana e por fim as tendências de
 * saúde, que são leitura de fundo e não de decisão imediata.
 */
import { useEffect, useState } from "react"

import ReadinessHero from "../components/health/ReadinessHero"
import HRVChart from "../components/health/HRVChart"
import WellnessChart from "../components/health/WellnessChart"
import CorrelationPanel from "../components/health/CorrelationPanel"
import StatTile from "../components/viz/StatTile"
import { api } from "../lib/api"
import { duration, formState, fullDate, km, num } from "../lib/format"

const SEVERITY_TOKEN = {
  danger: "--status-critical",
  warning: "--status-warning",
  info: null,
}

export default function TodayView() {
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    let cancelled = false

    Promise.all([
      api.health.readiness(),
      api.health.daily(365),
      api.health.alerts(),
      api.fitness.pmc(),
      api.planning.calendar(),
      api.activities.list(),
    ])
      .then(([readiness, health, alerts, pmc, calendar, activities]) => {
        if (cancelled) return
        setState({ loading: false, readiness, health, alerts, pmc, calendar, activities })
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error: String(error) })
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (state.loading) return <p className="muted">Carregando…</p>
  if (state.error)
    return <p style={{ color: "var(--status-critical)" }}>Erro: {state.error}</p>

  const today = state.health?.[0]
  const latestLoad = state.pmc?.[state.pmc.length - 1]
  const form = formState(latestLoad?.tsb)
  const week = summarizeWeek(state.calendar)
  const recent = (state.activities || []).slice(-5).reverse()

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      <ReadinessHero readiness={state.readiness} health={today} />

      {state.alerts?.length > 0 && (
        <section className="card">
          <h2 className="card-title">Alertas ativos</h2>
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: "var(--space-2)" }}>
            {state.alerts.map((alert) => (
              <li
                key={alert.type}
                style={{ display: "flex", gap: "var(--space-2)", alignItems: "baseline" }}
              >
                {/* Severidade nunca é só cor: vem com rótulo. */}
                <span
                  style={{
                    fontSize: "var(--fs-micro)",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    color: `var(${SEVERITY_TOKEN[alert.severity] || "--text-muted"})`,
                    minWidth: 64,
                  }}
                >
                  {alert.severity}
                </span>
                <span style={{ color: "var(--text-secondary)" }}>{alert.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        <StatTile
          label="Forma · TSB"
          value={num(latestLoad?.tsb, 1)}
          context={form.label}
          statusToken={form.token}
        />
        <StatTile label="Fitness · CTL" value={num(latestLoad?.ctl, 1)} />
        <StatTile
          label="TSS da semana"
          value={num(week.actual, 0)}
          context={week.planned > 0 ? `${num(week.compliance, 0)}% do plano` : "sem plano"}
          statusToken={
            week.planned > 0 && week.compliance < 80 ? "--status-warning" : null
          }
        />
        <StatTile label="Treinos na semana" value={num(week.sessions, 0)} />
        <StatTile
          label="Sono (média 7d)"
          value={num(averageOf(state.health, "sleep_hours", 7), 1)}
          unit="h"
        />
      </div>

      <HRVChart health={state.health} />
      <WellnessChart health={state.health} />
      <CorrelationPanel />

      <section className="card">
        <h2 className="card-title">Atividades recentes</h2>
        <div className="scroll-x">
          <table className="data">
            <thead>
              <tr>
                <th>Data</th>
                <th>Esporte</th>
                <th>Distância</th>
                <th>Duração</th>
                <th>NP</th>
                <th>IF</th>
                <th>TSS</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((a) => (
                <tr key={a.id}>
                  <td>{fullDate(a.started_at)}</td>
                  <td>{a.sport_type}</td>
                  <td>{km(a.distance_m)}</td>
                  <td>{duration(a.elapsed_time_s)}</td>
                  <td>{a.normalized_power_w ? `${num(a.normalized_power_w)} W` : "—"}</td>
                  <td>{num(a.intensity_factor, 2)}</td>
                  <td>{num(a.tss, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

/** Resume os últimos sete dias do calendário. */
function summarizeWeek(calendar) {
  const empty = { planned: 0, actual: 0, compliance: 0, sessions: 0 }
  if (!calendar?.days?.length) return empty

  const today = new Date().toISOString().slice(0, 10)
  const week = calendar.days.filter((d) => d.date <= today).slice(-7)

  const planned = week.reduce((acc, d) => acc + (d.planned_tss || 0), 0)
  const actual = week.reduce((acc, d) => acc + (d.actual_tss || 0), 0)
  const sessions = week.reduce((acc, d) => acc + (d.activities?.length || 0), 0)

  return {
    planned,
    actual,
    sessions,
    compliance: planned > 0 ? (actual / planned) * 100 : 0,
  }
}

/** Média dos N registros mais recentes de uma chave. */
function averageOf(health, key, days) {
  if (!health?.length) return null
  const values = health
    .slice(0, days)
    .map((h) => h[key])
    .filter((v) => v !== null && v !== undefined)
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
}
