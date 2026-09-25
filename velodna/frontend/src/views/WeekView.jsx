/*
 * Visão Semana — a tela principal do produto.
 *
 * Responde a uma pergunta só: "como foi minha semana e como meu corpo
 * respondeu?". Quatro blocos, na ordem em que a pergunta se desdobra:
 *
 *   1. O número protagonista — a carga da semana, com o delta que lhe dá escala
 *   2. A timeline unificada — treino e saúde no mesmo eixo
 *   3. Como a carga se distribuiu em intensidade
 *   4. Se esta semana é normal para este atleta
 *
 * O drill-down de um dia abre em drawer, sem sair da tela: o contexto da semana
 * é o que dá sentido ao dia, e tapá-lo com um modal perderia exatamente isso.
 */
import { useEffect, useState } from "react"

import WeekTimeline from "../components/week/WeekTimeline"
import WeekTrend from "../components/week/WeekTrend"
import ZoneBars from "../components/week/ZoneBars"
import DayDrawer from "../components/week/DayDrawer"
import HeroNumber from "../components/viz/HeroNumber"
import ErrorState from "../components/viz/ErrorState"
import { api } from "../lib/api"
import { duration, fullDate, num, shortDate } from "../lib/format"

const TREND_WEEKS = 8

/** Data de referência deslocada em N semanas a partir de hoje. */
function referenceFor(offset) {
  const date = new Date()
  date.setDate(date.getDate() + offset * 7)
  return date.toISOString().slice(0, 10)
}

const DISTRIBUTION_HINT = {
  polarizado: "muito fácil e muito forte, pouco no meio",
  piramidal: "base larga, afinando conforme a intensidade sobe",
  limiar: "concentrado em torno do limiar",
  base: "só volume aeróbico, sem trabalho intenso",
}

export default function WeekView({ onOpenActivity }) {
  const [offset, setOffset] = useState(0)
  const [state, setState] = useState({ loading: true })
  const [attempt, setAttempt] = useState(0)
  const [selectedDay, setSelectedDay] = useState(null)

  useEffect(() => {
    let cancelled = false
    setState({ loading: true })
    setSelectedDay(null)

    Promise.all([
      api.training.week({ reference: referenceFor(offset) }),
      api.training.weeks({ weeks: TREND_WEEKS, reference: referenceFor(offset) }),
    ])
      .then(([week, weeks]) => !cancelled && setState({ loading: false, week, weeks }))
      .catch((error) => !cancelled && setState({ loading: false, error }))

    return () => {
      cancelled = true
    }
  }, [offset, attempt])

  if (state.loading) return <WeekSkeleton />
  if (state.error)
    return (
      <ErrorState
        error={state.error}
        onRetry={() => setAttempt((n) => n + 1)}
      />
    )

  const week = state.week
  if (!week) return <p className="muted">Sem dados para esta semana.</p>

  const hasLoad = week.total_tss > 0

  return (
    <>
      <div className="page">
        {/* ── 1. Cabeçalho e número protagonista ───────────────────────── */}
        <section className="section">
          <header
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              gap: "var(--space-5)",
              flexWrap: "wrap",
            }}
          >
            <h1
              className="label"
              style={{ margin: 0, fontSize: "var(--fs-micro)" }}
            >
              Semana {shortDate(week.week_start)} – {fullDate(week.week_end)}
            </h1>

            <nav className="segmented" role="group" aria-label="Navegar semanas">
              <button onClick={() => setOffset((o) => o - 1)}>◀ anterior</button>
              <button
                onClick={() => setOffset((o) => Math.min(o + 1, 0))}
                disabled={offset >= 0}
                style={offset >= 0 ? { opacity: 0.4, cursor: "default" } : undefined}
              >
                próxima ▶
              </button>
            </nav>
          </header>

          <div style={{ padding: "var(--space-8) 0" }}>
            <HeroNumber
              value={num(week.total_tss, 0)}
              label="TSS na semana"
              delta={week.tss_change_pct}
              deltaLabel="vs. semana anterior"
              statusToken={
                week.ramp_is_safe === false ? "--status-warning" : undefined
              }
              context={
                hasLoad
                  ? [
                      `${duration(week.total_hours * 3600)} de treino`,
                      `${num(week.total_km, 0)} km`,
                      `${num(week.total_elevation_m, 0)} m de elevação`,
                      week.avg_sleep_hours
                        ? `média de ${formatSleep(week.avg_sleep_hours)} de sono`
                        : null,
                    ]
                      .filter(Boolean)
                      .join("  ·  ")
                  : "Nenhuma atividade registrada nesta semana."
              }
            />
            {week.ramp_is_safe === false && (
              <p
                style={{
                  margin: "var(--space-4) 0 0",
                  fontSize: "var(--fs-small)",
                  color: "var(--status-warning)",
                }}
              >
                Aumento acima de 15% — a faixa em que o risco de lesão sobe.
              </p>
            )}
          </div>

          <hr className="rule" />
        </section>

        {/* ── 2. Timeline unificada ────────────────────────────────────── */}
        <section className="section">
          <WeekTimeline days={week.days} onSelectDay={setSelectedDay} />
        </section>

        {/* ── 3 e 4. Intensidade e tendência ───────────────────────────── */}
        <section
          className="section"
          style={{
            gridTemplateColumns: "minmax(0, 1.3fr) minmax(0, 1fr)",
            alignItems: "start",
          }}
        >
          <div className="card card--static" style={{ display: "grid", gap: "var(--space-5)" }}>
            <header>
              <h2 className="card-title">Distribuição de intensidade</h2>
              <p className="card-subtitle">
                {week.distribution}
                {DISTRIBUTION_HINT[week.distribution]
                  ? ` — ${DISTRIBUTION_HINT[week.distribution]}`
                  : ""}
              </p>
            </header>
            <ZoneBars zoneSeconds={week.zone_seconds} />

            {/* Resumo em três domínios — a leitura de polarização em números,
                sem gastar um bloco a mais da tela. */}
            {week.intensity?.easy && (
              <div
                style={{
                  display: "flex",
                  gap: "var(--space-8)",
                  paddingTop: "var(--space-4)",
                  borderTop: "1px solid var(--border-subtle)",
                  fontSize: "var(--fs-small)",
                  color: "var(--text-secondary)",
                }}
              >
                <span className="tabular">
                  fácil {num(week.intensity.easy.pct, 1)}%
                </span>
                <span className="tabular">
                  limiar {num(week.intensity.threshold.pct, 1)}%
                </span>
                <span className="tabular">
                  forte {num(week.intensity.hard.pct, 1)}%
                </span>
              </div>
            )}
          </div>

          <div className="card card--static" style={{ display: "grid", gap: "var(--space-5)" }}>
            <header>
              <h2 className="card-title">{TREND_WEEKS} semanas</h2>
              <p className="card-subtitle">
                {week.baseline_tss
                  ? `Base de 4 semanas: ${num(week.baseline_tss, 0)} TSS`
                  : "Histórico recente de carga"}
              </p>
            </header>
            <WeekTrend
              weeks={state.weeks}
              currentStart={week.week_start}
              onSelectWeek={(target) => {
                const diff = Math.round(
                  (new Date(target.week_start) - new Date(week.week_start)) /
                    (7 * 86400000),
                )
                setOffset((o) => o + diff)
              }}
            />
          </div>
        </section>
      </div>

      <DayDrawer
        day={selectedDay}
        activities={week.activities}
        onClose={() => setSelectedDay(null)}
        onOpenActivity={onOpenActivity}
        onFeedbackSaved={() => setAttempt((n) => n + 1)}
      />
    </>
  )
}

/** Skeleton — nunca spinner, conforme o checklist da spec. */
function WeekSkeleton() {
  return (
    <div className="page" aria-busy="true">
      <div className="section">
        <div className="skeleton" style={{ height: 14, width: 220 }} />
        <div className="skeleton" style={{ height: 64, width: 200 }} />
        <div className="skeleton" style={{ height: 14, width: 420 }} />
      </div>
      <div className="skeleton" style={{ height: 380, borderRadius: "var(--radius)" }} />
      <div
        className="section"
        style={{ gridTemplateColumns: "1.3fr 1fr" }}
      >
        <div className="skeleton" style={{ height: 260, borderRadius: "var(--radius)" }} />
        <div className="skeleton" style={{ height: 260, borderRadius: "var(--radius)" }} />
      </div>
    </div>
  )
}

function formatSleep(hours) {
  const total = Math.round(hours * 60)
  return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`
}
