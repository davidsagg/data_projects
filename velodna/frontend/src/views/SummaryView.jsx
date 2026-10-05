/*
 * Resumo — dia e semana numa aba só.
 *
 * Antes eram duas telas que respondiam à mesma pergunta em horizontes vizinhos,
 * e trocar de aba para ver o contexto do dia era custo sem motivo. A ordem segue
 * o relatório semanal do TrainingPeaks, que resolveu bem essa sequência:
 *
 *   hoje          → prontidão e o que os sinais sugerem
 *   carga         → TSS, TSS/hora, NP e IF medianos, volume
 *   timeline      → treino e saúde no mesmo eixo de sete dias
 *   zonas         → onde a carga caiu, em barra única com faixas de %FTP
 *   dia a dia     → cada treino, planejado versus executado
 *   tendência     → a semana contra as oito anteriores
 *   fitness       → os meses: carga (CTL/ATL/TSB), curva de potência, FTP,
 *                   eficiência e saúde — era a aba Fitness
 *
 * A densidade é deliberada. A versão anterior seguia "máximo 5 blocos" e
 * deixava 60% de tela vazia para quem tem 760 atividades registradas.
 */
import { useEffect, useState } from "react"

import DayDrawer from "../components/week/DayDrawer"
import SessionTable from "../components/week/SessionTable"
import WeekGrid from "../components/week/WeekGrid"
import WeekTrend from "../components/week/WeekTrend"
import ZoneBar from "../components/week/ZoneBar"
import RecommendationCard from "../components/today/RecommendationCard"
import FitnessSection from "../components/fitness/FitnessSection"
import ChartFrame from "../components/viz/ChartFrame"
import ErrorState from "../components/viz/ErrorState"
import StatCell from "../components/viz/StatCell"
import { Pill } from "../components/viz/GoalPill"
import { api } from "../lib/api"
import { duration, formState, fullDate, num, shortDate, toDate } from "../lib/format"

const TREND_WEEKS = 8

/** Faixas de TSS/hora do guia: base, moderada, intensa. */
function intensityLabel(tssPerHour) {
  if (tssPerHour == null) return null
  if (tssPerHour < 45) return "base/volume"
  if (tssPerHour < 55) return "moderada"
  return "trabalho intenso"
}

function readinessTone(score) {
  if (score == null) return { token: null, label: "sem dados" }
  if (score >= 70) return { token: "--status-good", label: "recuperado" }
  if (score >= 50) return { token: null, label: "moderado" }
  if (score >= 35) return { token: "--status-warning", label: "fadigado" }
  return { token: "--status-critical", label: "muito fadigado" }
}

/* Data local, não `toISOString()`: esta é UTC e, depois das 21h em Brasília,
   já devolve o dia seguinte — no domingo à noite, a semana errada. */
const isoLocal = (date) => date.toLocaleDateString("sv-SE")

function referenceFor(offset) {
  const date = new Date()
  date.setDate(date.getDate() + offset * 7)
  return isoLocal(date)
}

/**
 * Data em que os sinais "de momento" (prontidão, forma, bateria, base de 45
 * dias) são lidos: hoje na semana em curso, o domingo nas semanas passadas.
 * Sem isso o Resumo de três semanas atrás mostrava a carga daquela semana ao
 * lado do TSB de hoje.
 */
function asOfFor(offset) {
  if (offset >= 0) return undefined
  const date = new Date()
  date.setDate(date.getDate() + offset * 7)
  date.setDate(date.getDate() + 6 - ((date.getDay() + 6) % 7))
  return isoLocal(date)
}

function mean(values) {
  const valid = values.filter((v) => v != null)
  return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null
}

export default function SummaryView({ onOpenActivity, athleteWeightKg }) {
  const [offset, setOffset] = useState(0)
  const [state, setState] = useState({ loading: true })
  const [selectedDay, setSelectedDay] = useState(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true }))
    setSelectedDay(null)

    const asOf = asOfFor(offset)

    Promise.all([
      api.today({ reference: asOf }),
      api.training.week({ reference: referenceFor(offset) }),
      api.training.weeks({ weeks: TREND_WEEKS, reference: referenceFor(offset) }),
      api.health.daily(45, asOf),
      api.health.alerts({ reference: asOf }),
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
  const baseline = healthBaseline(state.health)
  const avgRestingHr = mean(week.days.map((d) => d.resting_hr_bpm))
  const avgSleepQuality = mean(week.days.map((d) => d.sleep_quality_score))
  const momentLabel = isCurrentWeek ? "hoje" : "no fim da semana"

  return (
    <>
      {/* Respiro menor no topo: hoje, a navegação e as doze métricas da semana
          têm de caber na primeira tela de um notebook, sem rolar. */}
      <div className="page" style={{ paddingTop: "var(--space-5)" }}>
        {/* ── Hoje: estado e sugestão ──────────────────────────────────── */}
        {/* Fica no lugar em qualquer semana — sumir ao voltar uma semana fazia
            a página inteira saltar — e acompanha a semana em foco: numa semana
            passada mostra o estado no domingo dela. */}
        {today && (
          <section className="today-row hug-next">
            <div
              className="card card--static"
              style={{
                display: "grid",
                gap: "var(--space-2)",
                alignContent: "start",
                borderLeft: `3px solid var(${tone.token || "--accent"})`,
              }}
            >
              <span className="label">
                {isCurrentWeek ? "Hoje" : "Fim da semana"} ·{" "}
                {toDate(today.date).toLocaleDateString("pt-BR", {
                  weekday: "long",
                  day: "2-digit",
                  month: "long",
                })}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
                <span className="figure" style={{ fontSize: "2.5rem" }}>
                  {readiness?.score == null ? "—" : num(readiness.score, 0)}
                </span>
                <div style={{ display: "grid", gap: 4 }}>
                  <span className="muted" style={{ fontSize: "var(--fs-small)" }}>prontidão</span>
                  <Pill tone={TONE_BY_TOKEN[tone.token]}>{tone.label}</Pill>
                </div>
              </div>
              <div
                className="tabular"
                style={{
                  display: "flex",
                  gap: "var(--space-4)",
                  flexWrap: "wrap",
                  fontSize: "var(--fs-small)",
                  color: "var(--text-secondary)",
                }}
              >
                {readiness?.sleep_hours && <span>sono {formatSleep(readiness.sleep_hours)}</span>}
                {readiness?.hrv_rmssd_ms && <span>HRV {num(readiness.hrv_rmssd_ms, 0)} ms</span>}
                {readiness?.resting_hr_bpm && <span>FC rep. {readiness.resting_hr_bpm}</span>}
                {readiness?.body_battery && <span>bateria {readiness.body_battery}</span>}
              </div>
              {readiness?.is_stale && (
                <span style={{ fontSize: "var(--fs-micro)", color: "var(--status-warning)" }}>
                  Saúde medida em {shortDate(readiness.measured_on)}.
                </span>
              )}
            </div>

            <RecommendationCard
              recommendation={today.recommendation}
              week={today.week}
              label={isCurrentWeek ? "Hoje sugere" : "Os sinais sugeriam"}
            />
          </section>
        )}

        {state.alerts?.length > 0 && (
          <section className="section hug-next">
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

        {/* ── Semana ───────────────────────────────────────────────────── */}
        {/* Embrulhada num bloco próprio para o cabeçalho fixo da semana parar
            aqui: ao rolar até a seção de meses, "◀ anterior" não diz respeito
            ao que está na tela. */}
        <div style={{ display: "grid", gap: "var(--section-gap)" }}>
        {/* ── Carga da semana ──────────────────────────────────────────── */}
        {/* Fixo abaixo do cabeçalho: a página é longa, e ter de rolar de
              volta ao topo para trocar de semana quebra a leitura dos detalhes.
              O `top` acompanha a altura da barra de navegação. */}
        <header
          className="hug-next"
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
            <StatCell
              label="TSS"
              value={num(week.total_tss, 0)}
              accentToken="--ctl"
              sub={week.baseline_tss ? `base de 4 sem: ${num(week.baseline_tss, 0)}` : "custo total da semana"}
              tone={week.ramp_is_safe === false ? "warning" : null}
              pill={
                week.tss_change_pct == null
                  ? null
                  : `${week.tss_change_pct > 0 ? "▲" : "▼"} ${num(Math.abs(week.tss_change_pct), 0)}% vs. anterior`
              }
              hint="Custo total da semana: duração × intensidade. Uma semana de volume moderado soma entre 250 e 450 TSS. Subir mais de 15% sobre a anterior é a faixa em que o risco de lesão cresce."
            />
            <StatCell
              label="TSS / hora"
              value={week.tss_per_hour ? num(week.tss_per_hour, 0) : "—"}
              accentToken="--ctl"
              sub="intensidade média"
              tone={intensityTone(week.tss_per_hour, 45, 55)}
              pill={intensityLabel(week.tss_per_hour)}
              hint="TSS ÷ horas pedaladas. Perto de 40 indica base/volume; acima de 55–60, bastante trabalho de limiar ou intervalos."
            />
            <StatCell
              label="NP mediana"
              value={week.np_median ? num(week.np_median, 0) : "—"}
              unit={week.np_median ? "W" : undefined}
              accentToken="--ctl"
              sub="treino típico da semana"
              hint="Potência normalizada: pesa mais os picos e variações que a média simples, refletindo o custo fisiológico real."
            />
            <StatCell
              label="IF mediano"
              value={week.if_median ? num(week.if_median, 2) : "—"}
              accentToken="--ctl"
              sub="NP ÷ FTP"
              tone={intensityTone(week.if_median, 0.75, 0.85)}
              pill={
                week.if_median == null
                  ? null
                  : week.if_median < 0.75
                    ? "base/recuperação"
                    : week.if_median < 0.85
                      ? "moderado/tempo"
                      : "intenso"
              }
              hint="Abaixo de 0,75 é base/recuperação; 0,75–0,85 moderado/tempo; acima de 0,85 bem intenso."
            />
            <StatCell
              label="Volume"
              value={duration(week.total_hours * 3600)}
              accentToken="--mod-outdoor"
              sub={[
                `${num(week.total_km, 0)} km`,
                `${num(week.total_elevation_m, 0)} m`,
                hoursGoal && `meta ${num(hoursGoal.target, 0)} h`,
              ]
                .filter(Boolean)
                .join(" · ")}
              {...weekGoalPill(week, hoursGoal, isCurrentWeek)}
              hint="Tempo em movimento, distância e elevação acumulados na semana, contra a meta semanal cadastrada no Panorama."
            />
            <StatCell
              label="Sessões"
              value={week.session_count}
              accentToken="--mod-outdoor"
              sub={`${week.rest_days} ${week.rest_days === 1 ? "dia" : "dias"} de descanso`}
              tone={week.rest_days === 0 && !isCurrentWeek ? "warning" : null}
              pill={week.rest_days === 0 && !isCurrentWeek ? "sem dia de descanso" : null}
              hint="Treinos registrados na semana, incluindo os que não são de bike."
            />

            <StatCell
              label="Sono médio"
              value={week.avg_sleep_hours ? formatSleep(week.avg_sleep_hours) : "—"}
              accentToken="--sleep"
              sub={avgSleepQuality ? `qualidade média ${num(avgSleepQuality, 0)}/100` : "média da semana"}
              tone={sleepTone(week.avg_sleep_hours)}
              pill={week.avg_sleep_hours ? sleepPill(week.avg_sleep_hours) : null}
              trend={series("sleep_hours")}
              trendToken="--sleep"
              hint="Média das noites da semana. Abaixo de 7h de forma sustentada costuma aparecer no HRV e no desempenho."
            />
            <StatCell
              label="HRV médio"
              value={week.avg_hrv_ms ? num(week.avg_hrv_ms, 0) : "—"}
              unit={week.avg_hrv_ms ? "ms" : undefined}
              accentToken="--hrv"
              sub={baseline.hrv ? `base de 45 dias: ${num(baseline.hrv, 0)} ms` : "média da semana"}
              {...vsBaseline(week.avg_hrv_ms, baseline.hrv, "hrv")}
              trend={series("hrv_rmssd_ms")}
              trendToken="--hrv"
              hint="Variabilidade cardíaca ao acordar. O valor absoluto varia entre pessoas — o que informa é a distância da própria base."
            />
            <StatCell
              label="FC rep. média"
              value={avgRestingHr ? num(avgRestingHr, 0) : "—"}
              unit={avgRestingHr ? "bpm" : undefined}
              accentToken="--atl"
              sub={baseline.rhr ? `base de 45 dias: ${num(baseline.rhr, 0)} bpm` : "45 dias"}
              {...vsBaseline(avgRestingHr, baseline.rhr, "rhr")}
              trend={series("resting_hr_bpm")}
              trendToken="--atl"
              hint="Média das manhãs da semana. Sobe com fadiga acumulada, calor, álcool ou infecção. Uma alta de 5+ bpm sobre a base merece atenção."
            />
            <StatCell
              label="Body battery"
              value={readiness?.body_battery ?? "—"}
              accentToken="--ctl"
              sub={`${momentLabel}, de 0 a 100`}
              tone={batteryTone(readiness?.body_battery)}
              pill={batteryPill(readiness?.body_battery)}
              trend={series("body_battery")}
              trendToken="--ctl"
              hint="Estimativa de energia disponível do Garmin, de 0 a 100, a partir de HRV, sono e estresse."
            />
            <StatCell
              label="Forma · TSB"
              value={today?.form?.tsb != null ? num(today.form.tsb, 0) : "—"}
              accentToken="--tsb-positive"
              sub={today?.form ? `CTL ${num(today.form.ctl, 0)} · ATL ${num(today.form.atl, 0)}` : "CTL − ATL"}
              tone={TONE_BY_TOKEN[form.token]}
              pill={form.label}
              trend={(today?.pmc || []).slice(-45).map((d) => d.tsb)}
              trendToken="--tsb-positive"
              hint="CTL − ATL. Bem negativo é fadiga acumulada (esperado em semana pesada); perto de zero ou positivo, corpo descansado."
            />
            <StatCell
              label="Prontidão"
              value={readiness?.score == null ? "—" : num(readiness.score, 0)}
              accentToken={tone.token || "--accent"}
              sub={isCurrentWeek ? "sono, HRV, bateria e TSB" : momentLabel}
              tone={TONE_BY_TOKEN[tone.token]}
              pill={tone.label}
              hint="Combina sono, HRV, body battery e TSB. Diferente do TSB, considera recuperação real, não só carga estimada."
            />
          </div>
        </section>

        {/* ── Timeline treino × saúde ──────────────────────────────────── */}
        <section className="section">
          <WeekGrid days={week.days} baseline={baseline} onSelectDay={setSelectedDay} />
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

        {/* ── Meses ────────────────────────────────────────────────────── */}
        <FitnessSection athleteWeightKg={athleteWeightKg} />
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
 * falta; semana fechada diz o percentual cumprido. O valor da meta vai na
 * linha de apoio do card: junto na etiqueta, o texto quebrava em duas linhas e
 * deixava a fileira inteira mais alta.
 */
function weekGoalPill(week, goal, inProgress) {
  if (!goal) return {}
  const done = week.total_hours
  const pct = (done / goal.target) * 100
  if (done >= goal.target) return { tone: "good", pill: "meta atingida" }
  if (inProgress) return { tone: null, pill: `faltam ${num(goal.target - done, 1)} h` }
  return { tone: pct >= 90 ? "warning" : "serious", pill: `${num(pct, 0)}% da meta` }
}

/** Tom das etiquetas a partir dos tokens de estado que o resto do app usa. */
const TONE_BY_TOKEN = {
  "--status-good": "good",
  "--status-warning": "warning",
  "--status-serious": "serious",
  "--status-critical": "critical",
}

/**
 * Intensidade não é bom nem ruim — é o que a semana pedia. O tom aqui só
 * separa as faixas: base sem cor, moderada em verde, intensa em âmbar.
 */
function intensityTone(value, low, high) {
  if (value == null) return null
  if (value < low) return null
  if (value < high) return "good"
  return "warning"
}

/** Médias de 45 dias de HRV e FC de repouso — a base pessoal do atleta. */
function healthBaseline(health) {
  const mean = (key) => {
    const values = (health || []).map((h) => h[key]).filter((v) => v != null)
    return values.length >= 7 ? values.reduce((a, b) => a + b, 0) / values.length : null
  }
  return { hrv: mean("hrv_rmssd_ms"), rhr: mean("resting_hr_bpm") }
}

/** Etiqueta de distância da base: HRV em %, FC de repouso em bpm. */
function vsBaseline(value, base, kind) {
  if (value == null || !base) return {}
  if (kind === "hrv") {
    const pct = (value / base - 1) * 100
    const tone = pct >= -5 ? "good" : pct >= -15 ? "warning" : "serious"
    return { tone, pill: `${pct >= 0 ? "+" : "−"}${num(Math.abs(pct), 0)}% vs. base` }
  }
  const delta = value - base
  const tone = delta <= 2 ? "good" : delta <= 4 ? "warning" : "serious"
  return { tone, pill: `${delta >= 0 ? "+" : "−"}${num(Math.abs(delta), 0)} bpm vs. base` }
}

function sleepTone(hours) {
  if (hours == null) return null
  return hours < 6 ? "serious" : hours < 7 ? "warning" : "good"
}

function sleepPill(hours) {
  return hours < 6 ? "sono curto" : hours < 7 ? "abaixo de 7h" : "7h ou mais"
}

function batteryTone(value) {
  if (value == null) return null
  return value >= 70 ? "good" : value >= 40 ? null : "warning"
}

function batteryPill(value) {
  if (value == null) return null
  return value >= 70 ? "carregado" : value >= 40 ? "moderado" : "baixo"
}

function formatSleep(hours) {
  const total = Math.round(hours * 60)
  return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`
}
