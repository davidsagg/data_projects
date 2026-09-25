/*
 * Casca da aplicação — cabeçalho, navegação e alternância de tema.
 *
 * A navegação é um funil de zoom, não uma lista plana. Antes havia sete abas em
 * que "Hoje", "Semana" e "Fitness" respondiam à mesma pergunta em horizontes
 * diferentes, sem que a ordem dissesse isso — o usuário tinha de resolver a
 * hierarquia na cabeça. Agora são dois grupos:
 *
 *   estado    Hoje → Semana → Fitness      (agora, sete dias, meses)
 *   detalhe   Atividade · Segmentos · Plano · Coach
 *
 * A Semana é a tela de entrada: é onde mora a pergunta central do produto.
 */
import { useEffect, useState } from "react"

import TodayView from "./views/TodayView"
import WeekView from "./views/WeekView"
import FitnessView from "./views/FitnessView"
import ActivityView from "./views/ActivityView"
import PlanningView from "./views/PlanningView"
import SegmentsView from "./views/SegmentsView"
import CoachView from "./views/CoachView"
import { api } from "./lib/api"
import "./styles/tokens.css"

const STATE_VIEWS = [
  { id: "today", label: "Hoje" },
  { id: "week", label: "Semana" },
  { id: "fitness", label: "Fitness" },
]

const DETAIL_VIEWS = [
  { id: "activity", label: "Atividade" },
  { id: "segments", label: "Segmentos" },
  { id: "planning", label: "Plano" },
  { id: "coach", label: "Coach" },
]

/** Tema inicial: o que o usuário escolheu antes, senão a preferência do sistema. */
function initialTheme() {
  const stored = localStorage.getItem("velodna-theme")
  if (stored) return stored
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export default function App() {
  const [view, setView] = useState("week")
  const [theme, setTheme] = useState(initialTheme)
  const [zones, setZones] = useState(null)
  const [focusedActivity, setFocusedActivity] = useState(null)

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
    localStorage.setItem("velodna-theme", theme)
  }, [theme])

  useEffect(() => {
    api.fitness.zones().then(setZones).catch(() => {})
  }, [])

  /** Abre uma atividade vinda do drawer da semana, mudando de visão junto. */
  const openActivity = (activity) => {
    setFocusedActivity(activity)
    setView("activity")
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--surface-page)" }}>
      <header
        style={{
          borderBottom: "1px solid var(--border-subtle)",
          background: "var(--surface-1)",
          position: "sticky",
          top: 0,
          zIndex: 20,
        }}
      >
        <div
          style={{
            maxWidth: "var(--page-max)",
            margin: "0 auto",
            padding: "var(--space-4) var(--page-margin)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-8)",
            flexWrap: "wrap",
          }}
        >
          <strong
            style={{
              fontSize: "var(--fs-lead)",
              letterSpacing: "-0.01em",
              cursor: "pointer",
            }}
            onClick={() => setView("week")}
          >
            VeloDNA
          </strong>

          <nav className="segmented" role="group" aria-label="Estado">
            {STATE_VIEWS.map((v) => (
              <button key={v.id} aria-pressed={view === v.id} onClick={() => setView(v.id)}>
                {v.label}
              </button>
            ))}
          </nav>

          <nav
            role="group"
            aria-label="Detalhe"
            style={{ display: "flex", gap: "var(--space-5)" }}
          >
            {DETAIL_VIEWS.map((v) => (
              <button
                key={v.id}
                aria-pressed={view === v.id}
                onClick={() => setView(v.id)}
                style={{
                  appearance: "none",
                  border: 0,
                  background: "transparent",
                  font: "inherit",
                  fontSize: "var(--fs-small)",
                  cursor: "pointer",
                  padding: 0,
                  color:
                    view === v.id ? "var(--text-primary)" : "var(--text-tertiary)",
                  borderBottom:
                    view === v.id
                      ? "1px solid var(--text-primary)"
                      : "1px solid transparent",
                  paddingBottom: 2,
                }}
              >
                {v.label}
              </button>
            ))}
          </nav>

          <button
            className="segmented"
            style={{
              marginLeft: "auto",
              padding: "var(--space-2) var(--space-3)",
              cursor: "pointer",
            }}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema escuro"}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </header>

      <main>
        {view === "today" && <TodayView onGoToWeek={() => setView("week")} />}
        {view === "week" && <WeekView onOpenActivity={openActivity} />}
        {view === "fitness" && <FitnessView athleteWeightKg={zones?.weight_kg} />}
        {view === "activity" && <ActivityView initialActivity={focusedActivity} />}
        {view === "planning" && <PlanningView />}
        {view === "segments" && <SegmentsView />}
        {view === "coach" && <CoachView />}
      </main>
    </div>
  )
}
