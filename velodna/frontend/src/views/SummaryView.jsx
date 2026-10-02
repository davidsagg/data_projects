/*
 * Resumo — dia e semana numa aba só.
 *
 * Antes eram duas telas que respondiam à mesma pergunta em horizontes vizinhos,
 * e trocar de aba para ver o contexto do dia era custo sem motivo. A ordem segue
 * o relatório semanal do TrainingPeaks, que resolveu bem essa sequência:
 *
 *   hoje          → prontidão e o que os sinais sugerem
 *   carga         → TSS, TSS/hora, NP e IF medianos, volume
 *   forma         → CTL/ATL/TSB, com a série dos últimos 60 dias
 *   timeline      → treino e saúde no mesmo eixo de sete dias
 *   zonas         → onde a carga caiu, em barra única com faixas de %FTP
 *   dia a dia     → cada treino, planejado versus executado
 *   tendência     → a semana contra as oito anteriores
 *
 * A densidade é deliberada. A versão anterior seguia "máximo 5 blocos" e
 * deixava 60% de tela vazia para quem tem 760 atividades registradas.
 */
import { useEffect, useState } from "react"

import DayDrawer from "../components/week/DayDrawer"
import SessionTable from "../components/week/SessionTable"
import WeekTimeline from "../components/week/WeekTimeline"
import WeekTrend from "../components/week/WeekTrend"
import ZoneBar from "../components/week/ZoneBar"
import MiniPMC from "../components/today/MiniPMC"
import RecommendationCard from "../components/today/RecommendationCard"
import ChartFrame from "../components/viz/ChartFrame"
import ErrorState from "../components/viz/ErrorState"
import HeroNumber from "../components/viz/HeroNumber"
import MetricCard from "../components/viz/MetricCard"
import GoalPill from "../components/viz/GoalPill"
import { api } from "../lib/api"
import { duration, formState, fullDate, num, shortDate } from "../lib/format"

const TREND_WEEKS = 8

/** Faixas de TSS/hora do guia: base, moderada, intensa. */
function intensityLabel(tssPerHour) {
  if (tssPerHour == null) return null
  if (tssPerHour < 45) return "semana de base/volume"
  if (tssPerHour < 55) return "semana moderada"
  return "semana com trabalho intenso"
}

function readinessTone(score) {
  if (score == null) return { token: null, label: "sem dados" }
  if (score >= 70) return { token: "--status-good", label: "recuperado" }
  if (score >= 50) return { token: null, label: "moderado" }
  if (score >= 35) return { token: "--status-warning", label: "fadigado" }
  return { token: "--status-critical", label: "muito fadigado" }
}

function referenceFor(offset) {
  const date = new Date()
  date.setDate(date.getDate() + offset * 7)
  return date.toISOString().slice(0, 10)
}

export default function SummaryView({ onGoToFitness, onOpenActivity }) {
  const [offset, setOffset] = useState(0)
  const [state, setState] = useState({ loading: true })
  const [selectedDay, setSelectedDay] = useState(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true }))
    setSelectedDay(null)

    Promise.all([
      api.today(),
      api.training.week({ reference: referenceFor(offset) }),
      api.training.weeks({ weeks: TREND_WEEKS, reference: referenceFor(offset) }),
      api.health.daily(45),
      api.health.alerts(),
      api.goals.list(),
    ])
      .then(([today, week, weeks, health, alerts, goals]) => {
        if (!cancelled)
          setState({ loading: false, today, week, weeks, health, alerts, goals })
      })
      .catch((error) => !cancelled && setState({ loading: false, error }))

    return () => {
      cancelled = true
    }
  }, [offset, attempt])

  if (state.loading && !state.week) return <SummarySkeleton />
  if (state.error)
    return <ErrorState error={state.error} onRetry={() => setAttempt((n) => n + 1)} />

  const { today, week } = state
  if (!week) return <p className="muted">Sem dados.</p>

  const isCurrentWeek = offset === 0
  const readiness = today?.readiness
  const tone = readinessTone(readiness?.score)
  const form = formState(today?.form?.tsb)
  const series = (key) => [...(state.health || [])].reverse().map((h) => h[key])
  const hoursGoal = state.goals?.find((g) => g.metric === "weekly_hours")

  return (
    <>
      <div className="page">
        {/* ── Hoje: estado e sugestão ──────────────────────────────────── */}
        {isCurrentWeek && today && (
          <section
            className="section"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))",
              alignItems: "start",
              gap: "var(--space-8)",
            }}
          >
            <div style={{ display: "grid", gap: "var(--space-4)" }}>
              <h1 className="label" style={{ margin: 0 }}>
                Hoje ·{" "}
                {new Date().toLocaleDateString("pt-BR", {
                  weekday: "long",
                  day: "2-digit",
                  month: "long",
                })}
              </h1>
              <HeroNumber
                value={readiness?.score == null ? "—" : num(readiness.score, 0)}
                label="prontidão"
                statusToken={tone.token}
                context={tone.label}
              />
              <div
                style={{
                  display: "flex",
                  gap: "var(--space-5)",
                  flexWrap: "wrap",
                  fontSize: "var(--fs-small)",
                  color: "var(--text-secondary)",
                }}
              >
                {readiness?.sleep_hours && (
                  <span className="tabular">
                    sono {formatSleep(readiness.sleep_hours)}
                  </span>
                )}
                {readiness?.hrv_rmssd_ms && (
                  <span className="tabular">
                    HRV {num(readiness.hrv_rmssd_ms, 0)} ms
                  </span>
                )}
                {readiness?.resting_hr_bpm && (
                  <span className="tabular">
                    FC rep. {readiness.resting_hr_bpm}
                  </span>
                )}
                {readiness?.body_battery && (
                  <span className="tabular">bateria {readiness.body_battery}</span>
                )}
              </div>
              {readiness?.is_stale && (
                <p
                  style={{
                    margin: 0,
                    fontSize: "var(--fs-small)",
                    color: "var(--status-warning)",
                  }}
                >
                  Saúde medida em {shortDate(readiness.measured_on)}.
                </p>
              )}
            </div>

            <RecommendationCard
              recommendation={today.recommendation}
              week={today.week}
            />
          </section>
        )}

        {state.alerts?.length > 0 && isCurrentWeek && (
          <section className="section">
            <span className="label">Alertas</span>
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: "var(--space-2)" }}>
              {state.alerts.map((alert, i) => (
                <li key={i} style={{ display: "flex", gap: "var(--space-3)", alignItems: "baseline", fontSize: "var(--fs-body)" }}>
                  <span
                    className="viz-swatch"
                    style={{
                      background:
                        alert.severity === "danger"
                          ? "var(--status-critical)"
                          : "var(--status-warning)",
                      borderRadius: "50%",
                    }}
                  />
                  <span style={{ color: "var(--text-secondary)" }}>{alert.message}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ── Carga da semana ──────────────────────────────────────────── */}
        {/* Fixo abaixo do cabeçalho: a página é longa, e ter de rolar de
              volta ao topo para trocar de semana quebra a leitura dos detalhes.
              O `top` acompanha a altura da barra de navegação. */}
        <header
          style={{
            position: "sticky",
              top: 56,
              zIndex: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "var(--space-4)",
              flexWrap: "wrap",
              padding: "var(--space-3) 0",
              background: "var(--surface-page)",
              borderBottom: "1px solid var(--border-subtle)",
            }}
          >
            <h2 className="label" style={{ margin: 0 }}>
              Semana {shortDate(week.week_start)} – {fullDate(week.week_end)}
            </h2>
            <nav className="segmented" role="group" aria-label="Navegar semanas">
              <button onClick={() => setOffset((o) => o - 1)}>◀ anterior</button>
              <button
                onClick={() => setOffset(0)}
                disabled={offset === 0}
                style={offset === 0 ? { opacity: 0.4, cursor: "default" } : undefined}
              >
                esta semana
              </button>
              <button
                onClick={() => setOffset((o) => Math.min(o + 1, 0))}
                disabled={offset >= 0}
                style={offset >= 0 ? { opacity: 0.4, cursor: "default" } : undefined}
              >
                próxima ▶
              </button>
            </nav>
        </header>

        <section className="section">
          <div className="metric-grid">
            <MetricCard
              label="TSS"
              value={num(week.total_tss, 0)}
              statusToken={week.ramp_is_safe === false ? "--status-warning" : undefined}
              context={
                week.tss_change_pct === null
                  ? "sem semana anterior"
                  : `${week.tss_change_pct > 0 ? "▲" : "▼"} ${num(Math.abs(week.tss_change_pct), 1)}% vs. anterior`
              }
              hint="Custo total da semana: duração × intensidade. Uma semana de volume moderado soma entre 250 e 450 TSS."
            />
            <MetricCard
              label="TSS / hora"
              value={week.tss_per_hour ? num(week.tss_per_hour, 0) : "—"}
              context={intensityLabel(week.tss_per_hour) || "intensidade média"}
              hint="TSS ÷ horas pedaladas. Perto de 40 indica base/volume; acima de 55–60, bastante trabalho de limiar ou intervalos."
            />
            <MetricCard
              label="NP mediana"
              value={week.np_median ? num(week.np_median, 0) : "—"}
              unit={week.np_median ? "W" : undefined}
              context="treino típico da semana"
              hint="Potência ajustada: pesa mais os picos e variações que a média simples, refletindo o custo fisiológico real."
            />
            <MetricCard
              label="IF mediano"
              value={week.if_median ? num(week.if_median, 2) : "—"}
              context={
                week.if_median == null
                  ? "sem potência"
                  : week.if_median < 0.75
                    ? "base/recuperação"
                    : week.if_median < 0.85
                      ? "moderado/tempo"
                      : "intenso"
              }
              hint="NP ÷ FTP. Abaixo de 0,75 é base/recuperação; 0,75–0,85 moderado/tempo; acima de 0,85 bem intenso."
            />
            <MetricCard
              label="Volume"
              value={duration(week.total_hours * 3600)}
              context={`${num(week.total_km, 0)} km · ${num(week.total_elevation_m, 0)} m`}
              badge={weekGoalPill(week, hoursGoal, isCurrentWeek)}
              hint="Tempo em movimento, distância e elevação acumulados na semana."
            />
            <MetricCard
              label="Sessões"
              value={week.session_count}
              context={`${week.rest_days} ${week.rest_days === 1 ? "dia" : "dias"} de descanso`}
              hint="Treinos registrados na semana, incluindo os que não são de bike."
            />
          </div>

          {/* Segunda linha: a saúde ao lado da carga. Separá-las em telas
              diferentes é o que o produto veio resolver. */}
          <div className="metric-grid">
            <MetricCard
              label="Sono médio"
              value={week.avg_sleep_hours ? formatSleep(week.avg_sleep_hours) : "—"}
              context={
                readiness?.sleep_quality_score
                  ? `qualidade hoje ${readiness.sleep_quality_score}/100`
                  : "média da semana"
              }
              trend={series("sleep_hours")}
              trendToken="--sleep"
              hint="Média das noites da semana. Abaixo de 7h de forma sustentada costuma aparecer no HRV e no desempenho."
            />
            <MetricCard
              label="HRV médio"
              value={week.avg_hrv_ms ? num(week.avg_hrv_ms, 0) : "—"}
              unit={week.avg_hrv_ms ? "ms" : undefined}
              context={
                readiness?.hrv_rmssd_ms
                  ? `hoje ${num(readiness.hrv_rmssd_ms, 0)} ms`
                  : "média da semana"
              }
              trend={series("hrv_rmssd_ms")}
              trendToken="--hrv"
              hint="Variabilidade cardíaca ao acordar. O valor absoluto varia entre pessoas — o que informa é a tendência contra a própria base."
            />
            <MetricCard
              label="FC de repouso"
              value={readiness?.resting_hr_bpm ?? "—"}
              unit={readiness?.resting_hr_bpm ? "bpm" : undefined}
              context="45 dias"
              trend={series("resting_hr_bpm")}
              trendToken="--atl"
              hint="Sobe com fadiga acumulada, calor, álcool ou infecção. Uma alta de 5+ bpm sobre a base merece atenção."
            />
            <MetricCard
              label="Body battery"
              value={readiness?.body_battery ?? "—"}
              context="45 dias"
              trend={series("body_battery")}
              trendToken="--ctl"
              hint="Estimativa de energia disponível do Garmin, de 0 a 100, a partir de HRV, sono e estresse."
            />
            <MetricCard
              label="Forma · TSB"
              value={today?.form?.tsb != null ? num(today.form.tsb, 0) : "—"}
              statusToken={form.token}
              context={form.label}
              trend={(today?.pmc || []).slice(-45).map((d) => d.tsb)}
              trendToken="--tsb-positive"
              hint="CTL − ATL. Bem negativo é fadiga acumulada (esperado em semana pesada); perto de zero ou positivo, corpo descansado."
            />
            <MetricCard
              label="Prontidão"
              value={readiness?.score == null ? "—" : num(readiness.score, 0)}
              statusToken={tone.token}
              context={tone.label}
              hint="Combina sono, HRV, body battery e TSB. Diferente do TSB, considera recuperação real, não só carga estimada."
            />
          </div>

          {week.ramp_is_safe === false && (
            <p style={{ margin: 0, fontSize: "var(--fs-small)", color: "var(--status-warning)" }}>
              Aumento acima de 15% sobre a semana anterior — a faixa em que o
              risco de lesão sobe.
            </p>
          )}
        </section>

        {/* ── Fitness, fadiga e forma ──────────────────────────────────── */}
        {today?.pmc?.length > 0 && (
          <section className="section">
            <MiniPMC pmc={today.pmc} onOpenFitness={onGoToFitness} />
          </section>
        )}

        {/* ── Timeline treino × saúde ──────────────────────────────────── */}
        <section className="section">
          <WeekTimeline days={week.days} onSelectDay={setSelectedDay} />
        </section>

        {/* ── Zonas ────────────────────────────────────────────────────── */}
        <section className="section">
          <ChartFrame
            title="Zonas de potência"
            subtitle="Onde o tempo de treino da semana foi distribuído"
          >
            <ZoneBar
              zoneSeconds={week.zone_seconds}
              intensity={week.intensity}
              distribution={week.distribution}
            />
          </ChartFrame>
        </section>

        {/* ── Dia a dia ────────────────────────────────────────────────── */}
        <section className="section">
          <ChartFrame
            title="Dia a dia"
            subtitle={
              week.planned_tss > 0
                ? `Planejado × executado · aderência de ${num(week.compliance_pct, 0)}% na semana`
                : "Cada treino da semana, na ordem em que aconteceram"
            }
          >
            <SessionTable
              activities={week.activities}
              onOpenActivity={onOpenActivity}
            />
          </ChartFrame>
        </section>

        {/* ── Tendência ────────────────────────────────────────────────── */}
        <section className="section">
          <ChartFrame
            title={`Últimas ${TREND_WEEKS} semanas`}
            subtitle={
              week.baseline_tss
                ? `Base de 4 semanas: ${num(week.baseline_tss, 0)} TSS`
                : "Histórico recente de carga"
            }
          >
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
          </ChartFrame>
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

function SummarySkeleton() {
  return (
    <div className="page" aria-busy="true">
      <div className="section" style={{ gridTemplateColumns: "0.75fr 1.25fr" }}>
        <div className="skeleton" style={{ height: 180, borderRadius: "var(--radius)" }} />
        <div className="skeleton" style={{ height: 180, borderRadius: "var(--radius)" }} />
      </div>
      <div className="section" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="skeleton" style={{ height: 130, borderRadius: "var(--radius)" }} />
        ))}
      </div>
      <div className="skeleton" style={{ height: 230, borderRadius: "var(--radius)" }} />
      <div className="skeleton" style={{ height: 340, borderRadius: "var(--radius)" }} />
      <div className="skeleton" style={{ height: 260, borderRadius: "var(--radius)" }} />
    </div>
  )
}

/**
 * Etiqueta da meta de volume para a semana exibida.
 *
 * A meta é semanal, então a semana se mede contra ela diretamente — não contra
 * a média do ciclo, que é o que o Panorama mostra. Semana em curso diz quanto
 * falta; semana fechada diz o percentual cumprido.
 */
function weekGoalPill(week, goal, inProgress) {
  if (!goal) return null
  const done = week.total_hours
  const pct = (done / goal.target) * 100
  const status = done >= goal.target ? "achieved" : pct >= 90 ? "near" : "far"
  const text =
    status === "achieved"
      ? `meta ${num(goal.target, 0)} h atingida`
      : inProgress
        ? `faltam ${num(goal.target - done, 1)} h · meta ${num(goal.target, 0)} h`
        : `${num(pct, 0)}% da meta · ${num(goal.target, 0)} h`
  return (
    <GoalPill goal={{ ...goal, status: inProgress && status === "far" ? "unknown" : status }}>
      {text}
    </GoalPill>
  )
}

function formatSleep(hours) {
  const total = Math.round(hours * 60)
  return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`
}
