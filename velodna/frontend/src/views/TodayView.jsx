/*
 * Visão Hoje — o estado do atleta agora.
 *
 * Responde: "como estou hoje e o que devo fazer?". Três blocos, hierarquia
 * Whoop: um número domina a tela, quatro indicadores de contexto logo abaixo
 * com peso igual entre si, e a leitura do coach por último.
 *
 * A tela não repete a semana — ela aponta para ela. Quem quer a semana clica no
 * link do rodapé; duplicar o conteúdo aqui faria duas telas responderem à mesma
 * pergunta, que é o problema que a reorganização veio resolver.
 */
import { useEffect, useState } from "react"

import HeroNumber from "../components/viz/HeroNumber"
import MetricCard from "../components/viz/MetricCard"
import ErrorState from "../components/viz/ErrorState"
import { api } from "../lib/api"
import { formState, num, shortDate } from "../lib/format"

const SEVERITY_TOKEN = {
  danger: "--status-critical",
  warning: "--status-warning",
  info: null,
}

/** Faixas de prontidão — o rótulo acompanha a cor, nunca a substitui. */
function readinessTone(score) {
  if (score == null) return { token: null, label: "sem dados" }
  if (score >= 70) return { token: "--status-good", label: "recuperado" }
  if (score >= 50) return { token: null, label: "moderado" }
  if (score >= 35) return { token: "--status-warning", label: "fadigado" }
  return { token: "--status-critical", label: "muito fadigado" }
}

export default function TodayView({ onGoToWeek }) {
  const [state, setState] = useState({ loading: true })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false

    Promise.all([
      api.health.readiness(),
      api.health.daily(30),
      api.health.alerts(),
      api.fitness.pmc(),
    ])
      .then(([readiness, health, alerts, pmc]) => {
        if (!cancelled) setState({ loading: false, readiness, health, alerts, pmc })
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error })
      })

    return () => {
      cancelled = true
    }
  }, [attempt])

  if (state.loading) return <TodaySkeleton />
  if (state.error)
    return (
      <ErrorState
        error={state.error}
        onRetry={() => setAttempt((n) => n + 1)}
      />
    )

  const latestHealth = state.health?.[0]
  const latestLoad = state.pmc?.[state.pmc.length - 1]
  const form = formState(latestLoad?.tsb)
  const score = state.readiness?.score
  const tone = readinessTone(score)

  const hrvAverage = averageOf(state.health, "hrv_rmssd_ms", 7)
  const hrvDelta =
    latestHealth?.hrv_rmssd_ms != null && hrvAverage != null
      ? latestHealth.hrv_rmssd_ms - hrvAverage
      : null

  const healthIsStale = isStale(latestHealth?.date)

  return (
    <div className="page">
      <section className="section">
        <h1 className="label" style={{ margin: 0 }}>
          Hoje ·{" "}
          {new Date().toLocaleDateString("pt-BR", {
            weekday: "long",
            day: "2-digit",
            month: "long",
          })}
        </h1>

        <div style={{ padding: "var(--space-8) 0" }}>
          <HeroNumber
            value={score == null ? "—" : num(score, 0)}
            label="prontidão"
            statusToken={tone.token}
            context={
              state.readiness?.recommendation
                ? `${tone.label} — ${state.readiness.recommendation.toLowerCase()}`
                : "Sem dados de saúde suficientes para calcular."
            }
          />
        </div>

        {healthIsStale && (
          <p
            style={{
              margin: 0,
              fontSize: "var(--fs-small)",
              color: "var(--status-warning)",
            }}
          >
            Última sincronização de saúde em {shortDate(latestHealth.date)}. Rode{" "}
            <code>scripts/sync_garmin_health.py</code> para atualizar.
          </p>
        )}

        <hr className="rule" />
      </section>

      {state.alerts?.length > 0 && (
        <section className="section">
          <span className="label">Alertas</span>
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: "var(--space-3)" }}>
            {state.alerts.map((alert, index) => (
              <li
                key={index}
                style={{
                  display: "flex",
                  gap: "var(--space-3)",
                  alignItems: "baseline",
                  fontSize: "var(--fs-body)",
                }}
              >
                <span
                  className="viz-swatch"
                  style={{
                    background: `var(${SEVERITY_TOKEN[alert.severity] || "--text-tertiary"})`,
                    borderRadius: "50%",
                  }}
                />
                <span style={{ color: "var(--text-secondary)" }}>{alert.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section
        className="section"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}
      >
        <MetricCard
          label="Sono"
          value={latestHealth?.sleep_hours ? formatSleep(latestHealth.sleep_hours) : "—"}
          context={
            latestHealth?.sleep_quality_score
              ? `qualidade ${latestHealth.sleep_quality_score}/100`
              : "sem registro"
          }
        />
        <MetricCard
          label="HRV"
          value={latestHealth?.hrv_rmssd_ms ? num(latestHealth.hrv_rmssd_ms, 0) : "—"}
          unit={latestHealth?.hrv_rmssd_ms ? "ms" : undefined}
          context={
            hrvDelta != null
              ? `${hrvDelta > 0 ? "+" : ""}${num(hrvDelta, 1)} vs. média de 7 dias`
              : "sem baseline"
          }
        />
        <MetricCard
          label="Forma"
          value={latestLoad?.tsb != null ? num(latestLoad.tsb, 0) : "—"}
          unit={latestLoad?.tsb != null ? "TSB" : undefined}
          statusToken={form.token}
          context={
            latestLoad?.ctl != null
              ? `${form.label} · CTL ${num(latestLoad.ctl, 0)}`
              : form.label
          }
        />
        <MetricCard
          label="Body battery"
          value={latestHealth?.body_battery ?? "—"}
          context={
            latestHealth?.resting_hr_bpm
              ? `FC repouso ${latestHealth.resting_hr_bpm} bpm`
              : "sem registro"
          }
        />
      </section>

      <section style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={onGoToWeek}
          style={{
            appearance: "none",
            border: 0,
            background: "transparent",
            color: "var(--text-secondary)",
            font: "inherit",
            fontSize: "var(--fs-body)",
            cursor: "pointer",
            padding: 0,
          }}
        >
          ver semana completa →
        </button>
      </section>
    </div>
  )
}

function TodaySkeleton() {
  return (
    <div className="page" aria-busy="true">
      <div className="section">
        <div className="skeleton" style={{ height: 14, width: 240 }} />
        <div className="skeleton" style={{ height: 64, width: 160 }} />
        <div className="skeleton" style={{ height: 14, width: 340 }} />
      </div>
      <div className="section" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton" style={{ height: 150, borderRadius: "var(--radius)" }} />
        ))}
      </div>
    </div>
  )
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

/** Indica dado de saúde parado há mais de três dias. */
function isStale(date) {
  if (!date) return false
  const days = (Date.now() - new Date(`${date}T12:00:00`)) / 86400000
  return days > 3
}

function formatSleep(hours) {
  const total = Math.round(hours * 60)
  return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`
}
