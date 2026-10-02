/*
 * Panorama — o ciclo de 13 semanas lido contra as metas.
 *
 * Inspirado no `health_tracker.html` (docs/design-refs). O Resumo responde
 * "como foi esta semana?"; o Panorama responde "como estou indo em relação ao
 * que quero?". Ordem de leitura:
 *
 *   números do ciclo  → peso, FTP e W/kg, volume, maior esforço — cada um com
 *                       a meta ao lado e uma etiqueta dizendo quanto falta
 *   carga             → volume por modalidade contra a meta; CTL com os marcos
 *   zonas             → onde caiu o tempo do ciclo
 *   atividades        → as sessões recentes, com nome
 *   notas             → exames, planos, provas, testes de CP
 *   metas e marcos    → o cadastro, no fim, porque é consulta rara
 */
import { useEffect, useState } from "react"

import CtlChart from "../components/panorama/CtlChart"
import CycleSettings from "../components/panorama/CycleSettings"
import MilestoneCards from "../components/panorama/MilestoneCards"
import VolumeChart from "../components/panorama/VolumeChart"
import ZoneBar from "../components/week/ZoneBar"
import ChartFrame, { DataTable } from "../components/viz/ChartFrame"
import ErrorState from "../components/viz/ErrorState"
import GoalPill, { Pill } from "../components/viz/GoalPill"
import { api } from "../lib/api"
import { MODALITY_TOKENS } from "../lib/goals"
import { duration, fullDate, km, num, shortDate } from "../lib/format"

const WINDOWS = [
  { weeks: 13, label: "13 sem" },
  { weeks: 26, label: "26 sem" },
  { weeks: 52, label: "1 ano" },
]

/** Variação de FTP no ciclo, em etiqueta: estável, subindo ou caindo. */
function ftpTrend(now, start) {
  if (!now || !start) return null
  const change = ((now - start) / start) * 100
  if (Math.abs(change) < 2) return { tone: "good", text: "FTP estável no ciclo" }
  if (change > 0) return { tone: "good", text: `FTP +${num(now - start)} W no ciclo` }
  return { tone: "warning", text: `FTP ${num(now - start)} W no ciclo` }
}

function Tile({ label, value, unit, sub, children }) {
  return (
    <div className="card card--static" style={{ display: "grid", gap: 6, alignContent: "start" }}>
      <span className="label">{label}</span>
      <span className="figure">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </span>
      {sub && (
        <span style={{ fontSize: "var(--fs-small)", color: "var(--text-secondary)" }}>{sub}</span>
      )}
      {children}
    </div>
  )
}

function ModalityBadge({ modality, label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
      <span
        className="viz-swatch"
        style={{ background: `var(${MODALITY_TOKENS[modality]})`, borderRadius: "50%" }}
      />
      {label}
    </span>
  )
}

export default function PanoramaView({ onOpenActivity }) {
  const [weeks, setWeeks] = useState(13)
  const [attempt, setAttempt] = useState(0)
  // O resultado guarda a chave do pedido que o produziu: enquanto a chave atual
  // não chegou, a tela mostra o panorama anterior esmaecido em vez de piscar.
  const key = `${weeks}:${attempt}`
  const [result, setResult] = useState({})

  useEffect(() => {
    let cancelled = false
    api
      .panorama({ weeks: Number(key.split(":")[0]) })
      .then((data) => !cancelled && setResult({ key, data }))
      .catch((error) => !cancelled && setResult((prev) => ({ ...prev, key, error })))
    return () => {
      cancelled = true
    }
  }, [key])

  const loading = result.key !== key
  const state = { loading, data: result.data, error: loading ? null : result.error }

  if (state.error)
    return <ErrorState error={state.error} onRetry={() => setAttempt((n) => n + 1)} />
  if (!state.data) return <PanoramaSkeleton />

  const { window: cycle, athlete, goals, volume, biggest_effort: effort, zones } = state.data
  const goal = (metric) => goals.find((g) => g.metric === metric)
  const weightGoal = goal("weight_kg")
  const hoursGoal = goal("weekly_hours")
  const wkgGoal = goal("w_per_kg")
  const trend = ftpTrend(athlete.ftp_w, athlete.ftp_w_at_start)
  const labels = Object.fromEntries(volume.modalities.map((m) => [m.key, m.label]))

  const windowStart = cycle.start
  const inWindow = state.data.milestones.filter((m) => m.date >= windowStart)

  return (
    <div className="page" style={{ opacity: state.loading ? 0.6 : 1 }}>
      {/* ── Cabeçalho ──────────────────────────────────────────────────── */}
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: "var(--space-3)",
        }}
      >
        <div>
          <p className="label" style={{ margin: "0 0 4px", color: "var(--accent)" }}>
            Panorama do ciclo
          </p>
          <h1 style={{ margin: 0, fontSize: "clamp(1.375rem, 3vw, 1.875rem)", fontWeight: 800 }}>
            Desempenho e metas
          </h1>
          <p className="section-lede">
            {fullDate(cycle.start)} – {fullDate(cycle.end)} · {cycle.complete_weeks}{" "}
            {cycle.complete_weeks === 1 ? "semana completa" : "semanas completas"} · Strava,
            Garmin e arquivos .fit
          </p>
        </div>
        <nav className="segmented" role="group" aria-label="Janela do panorama">
          {WINDOWS.map((w) => (
            <button key={w.weeks} aria-pressed={weeks === w.weeks} onClick={() => setWeeks(w.weeks)}>
              {w.label}
            </button>
          ))}
        </nav>
      </header>

      {/* ── Números do ciclo ───────────────────────────────────────────── */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
          gap: "var(--card-gap)",
        }}
      >
        <Tile
          label="Peso atual"
          value={athlete.weight_kg ? num(athlete.weight_kg, 1) : "—"}
          unit={athlete.weight_kg ? "kg" : undefined}
          sub={weightGoal ? `Meta: ${num(weightGoal.target, 1)} kg` : "Sem meta de peso"}
        >
          <GoalPill goal={weightGoal} />
        </Tile>

        <Tile
          label="FTP · W/kg"
          value={
            <>
              {num(athlete.ftp_w)}
              <span className="unit">W</span> · {num(athlete.w_per_kg, 2)}
            </>
          }
          unit="W/kg"
          sub={
            athlete.w_per_kg_at_goal
              ? `No peso alvo, mesmo FTP: ${num(athlete.w_per_kg_at_goal, 2)} W/kg (+${num(athlete.w_per_kg_at_goal - athlete.w_per_kg, 2)})`
              : "Cadastre a meta de peso para ver o W/kg projetado"
          }
        >
          {wkgGoal ? <GoalPill goal={wkgGoal} /> : trend && <Pill tone={trend.tone}>{trend.text}</Pill>}
        </Tile>

        <Tile
          label="Volume semanal médio"
          value={num(volume.avg_weekly_hours, 1)}
          unit="h / sem"
          sub={
            hoursGoal
              ? `Meta: ${num(hoursGoal.target, 0)} h/semana · ${cycle.complete_weeks} sem completas`
              : `${cycle.complete_weeks} semanas completas`
          }
        >
          <GoalPill goal={hoursGoal} />
        </Tile>

        <Tile
          label="Maior esforço no ciclo"
          value={effort ? num(effort.tss, 0) : "—"}
          unit={effort ? "TSS" : undefined}
          sub={
            effort &&
            `${effort.name || "Atividade"} · ${shortDate(effort.date)} · ${duration(effort.duration_s)}${
              effort.elevation_gain_m ? ` · ${num(effort.elevation_gain_m)} m` : ""
            }`
          }
        >
          {effort?.ratio_to_median && (
            <Pill tone={effort.ratio_to_median >= 3 ? "warning" : null}>
              {num(effort.ratio_to_median, 1)}× o treino típico ({num(effort.median_session_tss, 0)} TSS)
            </Pill>
          )}
        </Tile>
      </section>

      {/* ── Carga do ciclo ─────────────────────────────────────────────── */}
      <section className="section">
        <div>
          <h2 className="section-title">Carga de treino — últimas {cycle.weeks} semanas</h2>
          <p className="section-lede">
            Volume por modalidade contra a meta, e o condicionamento com os marcos do ciclo.
          </p>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
            gap: "var(--card-gap)",
          }}
        >
          <VolumeChart volume={volume} goalHours={hoursGoal?.target} />
          <CtlChart
            series={state.data.ctl_series}
            milestones={inWindow}
            goalCtl={goal("ctl")?.target}
          />
        </div>
      </section>

      {/* ── Zonas ──────────────────────────────────────────────────────── */}
      <section className="section">
        <ChartFrame
          title="Zonas de potência no ciclo"
          subtitle={`Tempo pedalado em cada zona, contra o FTP vigente em cada data · FTP atual ${num(zones.ftp_w)} W`}
        >
          <ZoneBar
            zoneSeconds={zones.seconds}
            intensity={zones.intensity}
            distribution={zones.distribution}
            definitions={zones.definitions}
            emptyText="Sem dados de potência no ciclo."
          />
        </ChartFrame>
      </section>

      {/* ── Atividades recentes ────────────────────────────────────────── */}
      <section className="section">
        <div>
          <h2 className="section-title">Atividades recentes</h2>
          <p className="section-lede">
            Últimas {state.data.recent_activities.length} sessões do ciclo. Clique no nome para abrir a análise.
          </p>
        </div>
        <div className="card card--static" style={{ padding: "var(--space-2) var(--space-3)" }}>
          <DataTable
            columns={[
              {
                key: "name",
                label: "Atividade",
                format: (v, r) => (
                  <button
                    type="button"
                    onClick={() => onOpenActivity?.(r)}
                    style={{
                      appearance: "none",
                      border: 0,
                      padding: 0,
                      background: "none",
                      font: "inherit",
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    {v || "Sem nome"}
                  </button>
                ),
              },
              {
                key: "modality",
                label: "Tipo",
                format: (v) => <ModalityBadge modality={v} label={labels[v]} />,
              },
              { key: "date", label: "Data", num: true, format: (v) => <span className="tabular">{shortDate(v)}</span> },
              { key: "duration_s", label: "Duração", num: true, format: (v) => <span className="tabular">{duration(v)}</span> },
              {
                key: "distance_m",
                label: "Dist.",
                num: true,
                format: (v) => <span className="tabular">{v ? km(v) : "—"}</span>,
              },
              {
                key: "elevation_gain_m",
                label: "Elev.",
                num: true,
                format: (v) => <span className="tabular">{v ? `${num(v)} m` : "—"}</span>,
              },
              { key: "tss", label: "TSS", num: true, format: (v) => <span className="tabular">{num(v, 0)}</span> },
              {
                key: "intensity_factor",
                label: "IF",
                num: true,
                format: (v) => <span className="tabular">{v ? num(v, 2) : "—"}</span>,
              },
            ]}
            rows={state.data.recent_activities}
          />
        </div>
      </section>

      {/* ── Notas ──────────────────────────────────────────────────────── */}
      <section className="section">
        <div>
          <h2 className="section-title">Notas do ciclo</h2>
          <p className="section-lede">
            Exames, planos, provas e testes de potência crítica — o contexto que não vem de sensor.
          </p>
        </div>
        <MilestoneCards
          milestones={state.data.milestones}
          onDelete={(m) => api.milestones.remove(m.id).then(() => setAttempt((n) => n + 1))}
        />
      </section>

      {/* ── Cadastro ───────────────────────────────────────────────────── */}
      <section className="section">
        <div>
          <h2 className="section-title">Metas e marcos</h2>
          <p className="section-lede">
            Também pelo terminal: <code>set_athlete_profile.py --goal</code> e{" "}
            <code>add_milestone.py</code>.
          </p>
        </div>
        <CycleSettings goals={goals} onChanged={() => setAttempt((n) => n + 1)} />
      </section>
    </div>
  )
}

function PanoramaSkeleton() {
  return (
    <div className="page" aria-busy="true">
      <div className="skeleton" style={{ height: 60 }} />
      <div className="section" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton" style={{ height: 130, borderRadius: "var(--radius)" }} />
        ))}
      </div>
      <div className="skeleton" style={{ height: 320, borderRadius: "var(--radius)" }} />
      <div className="skeleton" style={{ height: 200, borderRadius: "var(--radius)" }} />
    </div>
  )
}
