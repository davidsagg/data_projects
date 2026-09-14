/*
 * Casca da aplicação — cabeçalho, navegação e alternância de tema.
 *
 * As demais visões (Hoje, Atividade, Planejamento) entram aqui conforme forem
 * construídas; a visão Fitness já usa o sistema de design completo.
 */
import { useEffect, useState } from "react"

import FitnessView from "./views/FitnessView"
import TodayView from "./views/TodayView"
import WeekView from "./views/WeekView"
import ActivityView from "./views/ActivityView"
import PlanningView from "./views/PlanningView"
import SegmentsView from "./views/SegmentsView"
import CoachView from "./views/CoachView"
import { api } from "./lib/api"
import { fullDate, km, duration } from "./lib/format"
import "./styles/tokens.css"

const VIEWS = [
  { id: "today", label: "Hoje" },
  { id: "week", label: "Semana" },
  { id: "fitness", label: "Fitness" },
  { id: "activity", label: "Atividade" },
  { id: "planning", label: "Planejamento" },
  { id: "segments", label: "Segmentos" },
  { id: "coach", label: "Coach" },
]

/** Tema inicial: o que o usuário escolheu antes, senão a preferência do sistema. */
function initialTheme() {
  const stored = localStorage.getItem("velodna-theme")
  if (stored) return stored
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light"
}

export default function App() {
  const [view, setView] = useState("today")
  const [theme, setTheme] = useState(initialTheme)
  const [latest, setLatest] = useState(null)
  const [zones, setZones] = useState(null)

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
    localStorage.setItem("velodna-theme", theme)
  }, [theme])

  useEffect(() => {
    api.activities.latest().then(setLatest).catch(() => {})
    api.fitness.zones().then(setZones).catch(() => {})
  }, [])

  return (
    <div style={{ minHeight: "100vh", background: "var(--surface-page)" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-4)",
          padding: "var(--space-3) var(--space-5)",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface-1)",
          flexWrap: "wrap",
        }}
      >
        <strong style={{ fontSize: "var(--fs-lead)", letterSpacing: "-0.01em" }}>
          VeloDNA
        </strong>

        <nav className="segmented" role="group" aria-label="Seções">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              aria-pressed={view === v.id}
              onClick={() => setView(v.id)}
            >
              {v.label}
            </button>
          ))}
        </nav>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          {latest && (
            <span
              className="muted"
              style={{ fontSize: "var(--fs-micro)" }}
            >
              Última atividade: {fullDate(latest.started_at)} ·{" "}
              {km(latest.distance_m)} · {duration(latest.elapsed_time_s)}
            </span>
          )}
          <button
            className="segmented"
            style={{ padding: "5px 10px", cursor: "pointer" }}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema escuro"}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </header>

      <main style={{ padding: "var(--space-5)", maxWidth: 1440, margin: "0 auto" }}>
        {view === "today" && <TodayView />}
        {view === "week" && <WeekView />}
        {view === "fitness" && <FitnessView athleteWeightKg={zones?.weight_kg} />}
        {view === "activity" && <ActivityView />}
        {view === "planning" && <PlanningView />}
        {view === "segments" && <SegmentsView />}
        {view === "coach" && <CoachView />}
      </main>
    </div>
  )
}
