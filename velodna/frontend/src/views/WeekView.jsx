/*
 * Visão Semana — o bloco de sete dias como ele realmente aconteceu.
 *
 * A semana é a unidade de periodização do ciclismo, e até aqui o projeto só a
 * tinha como uma soma de sete dias corridos calculada no cliente. Esta visão a
 * trata como o objeto que é: segunda a domingo, com volume, aderência ao plano,
 * distribuição de intensidade e a comparação com o que veio antes.
 *
 * Ordem de leitura: primeiro o que foi feito (volume e carga), depois como foi
 * feito (intensidade), depois a tendência (semanas anteriores) e por fim o
 * detalhe sessão a sessão.
 */
import { useEffect, useState } from "react"

import IntensityBar from "../components/training/IntensityBar"
import WeekLoadChart from "../components/training/WeekLoadChart"
import ChartFrame from "../components/viz/ChartFrame"
import StatTile from "../components/viz/StatTile"
import { api } from "../lib/api"
import { duration, fullDate, num, shortDate, watts } from "../lib/format"

/** Deslocamento em semanas aplicado à data de hoje. */
function referenceFor(offset) {
  const date = new Date()
  date.setDate(date.getDate() + offset * 7)
  return date.toISOString().slice(0, 10)
}

/** Rótulo do seletor de semana. */
function offsetLabel(offset) {
  if (offset === 0) return "Esta semana"
  if (offset === -1) return "Semana passada"
  return `${Math.abs(offset)} semanas atrás`
}

export default function WeekView() {
  const [offset, setOffset] = useState(0)
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    let cancelled = false
    setState({ loading: true })

    Promise.all([
      api.training.week({ reference: referenceFor(offset) }),
      api.training.weeks({ weeks: 12, reference: referenceFor(offset) }),
    ])
      .then(([week, weeks]) => {
        if (!cancelled) setState({ loading: false, week, weeks })
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error: String(error) })
      })

    return () => {
      cancelled = true
    }
  }, [offset])

  if (state.loading) return <p className="muted">Carregando…</p>
  if (state.error)
    return <p style={{ color: "var(--status-critical)" }}>Erro: {state.error}</p>

  const week = state.week
  if (!week) return <p className="muted">Sem dados para esta semana.</p>

  const compliance = week.compliance_pct
  const change = week.tss_change_pct

  return (
    <div style={{ display: "grid", gap: "var(--space-5)" }}>
      <header
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "var(--space-3)",
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: "var(--fs-lead)" }}>
            {shortDate(week.week_start)} — {fullDate(week.week_end)}
          </h1>
          <p className="card-subtitle" style={{ margin: 0 }}>
            {week.session_count} {week.session_count === 1 ? "sessão" : "sessões"} ·{" "}
            {week.rest_days} {week.rest_days === 1 ? "dia" : "dias"} de descanso
          </p>
        </div>

        <nav className="segmented" role="group" aria-label="Semana">
          {[-3, -2, -1, 0].map((value) => (
            <button
              key={value}
              aria-pressed={offset === value}
              onClick={() => setOffset(value)}
            >
              {offsetLabel(value)}
            </button>
          ))}
        </nav>
      </header>

      <section
        style={{
          display: "grid",
          gap: "var(--space-3)",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
        }}
      >
        <StatTile
          label="Carga"
          value={num(week.total_tss, 0)}
          unit="TSS"
          hero
          statusToken={
            week.ramp_is_safe === false ? "--status-warning" : undefined
          }
          context={
            change === null
              ? "sem semana anterior para comparar"
              : `${change > 0 ? "+" : ""}${num(change, 1)}% vs. semana anterior` +
                (week.ramp_is_safe === false ? " — rampa acima do seguro" : "")
          }
        />
        <StatTile
          label="Tempo"
          value={num(week.total_hours, 1)}
          unit="h"
          context={
            week.baseline_tss
              ? `média de 4 semanas: ${num(week.baseline_tss, 0)} TSS`
              : undefined
          }
        />
        <StatTile label="Distância" value={num(week.total_km, 0)} unit="km" />
        <StatTile
          label="Elevação"
          value={num(week.total_elevation_m, 0)}
          unit="m"
        />
        <StatTile
          label="Aderência ao plano"
          value={compliance === null ? "—" : num(compliance, 0)}
          unit={compliance === null ? undefined : "%"}
          statusToken={
            compliance === null
              ? undefined
              : compliance >= 80
                ? "--status-good"
                : "--status-warning"
          }
          context={
            compliance === null
              ? "nenhum treino planejado"
              : `${num(week.total_tss, 0)} de ${num(week.planned_tss, 0)} TSS planejados`
          }
        />
      </section>

      <ChartFrame
        title="Distribuição de intensidade"
        subtitle="Tempo em cada domínio, somando todas as sessões da semana"
      >
        <IntensityBar
          intensity={week.intensity}
          distribution={week.distribution}
        />
      </ChartFrame>

      <WeekLoadChart weeks={state.weeks} />

      <ChartFrame
        title="Sessões da semana"
        subtitle="Na ordem em que aconteceram"
      >
        {week.activities.length === 0 ? (
          <p className="muted">Nenhuma atividade registrada.</p>
        ) : (
          <table
            className="tabular"
            style={{ width: "100%", fontSize: "var(--fs-small)" }}
          >
            <thead>
              <tr style={{ textAlign: "left", color: "var(--text-muted)" }}>
                <th style={{ fontWeight: 500 }}>Dia</th>
                <th style={{ fontWeight: 500 }}>Esporte</th>
                <th style={{ fontWeight: 500, textAlign: "right" }}>Duração</th>
                <th style={{ fontWeight: 500, textAlign: "right" }}>Distância</th>
                <th style={{ fontWeight: 500, textAlign: "right" }}>NP</th>
                <th style={{ fontWeight: 500, textAlign: "right" }}>IF</th>
                <th style={{ fontWeight: 500, textAlign: "right" }}>TSS</th>
              </tr>
            </thead>
            <tbody>
              {week.activities.map((activity) => (
                <tr
                  key={activity.id}
                  style={{ borderTop: "1px solid var(--border)" }}
                >
                  <td>{shortDate(activity.date)}</td>
                  <td>{activity.sport_type}</td>
                  <td style={{ textAlign: "right" }}>
                    {duration(activity.moving_time_s || activity.elapsed_time_s)}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {activity.distance_m
                      ? `${num(activity.distance_m / 1000, 1)} km`
                      : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {watts(activity.normalized_power_w)}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {num(activity.intensity_factor, 2)}
                  </td>
                  <td style={{ textAlign: "right" }}>{num(activity.tss, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </ChartFrame>
    </div>
  )
}
