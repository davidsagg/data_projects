/*
 * Casca da aplicação — cabeçalho, navegação e alternância de tema.
 *
 * Três abas, cada uma com uma pergunta:
 *
 *   Resumo     como estou? — hoje, a semana e, mais abaixo, os meses
 *   Panorama   como estou indo em relação ao que quero? — o ciclo e as metas
 *   Atividade  o que aconteceu neste treino?
 *
 * Coach, Plano e Segmentos saíram da interface para focar no que é usado; os
 * endpoints seguem na API (e no MCP, no caso dos segmentos).
 */
import { useEffect, useState } from "react"

import SummaryView from "./views/SummaryView"
import PanoramaView from "./views/PanoramaView"
import ActivityView from "./views/ActivityView"
import { api } from "./lib/api"
import "./styles/tokens.css"

const VIEWS = [
  { id: "summary", label: "Resumo" },
  { id: "panorama", label: "Panorama" },
  { id: "activity", label: "Atividade" },
]

/** Tema inicial: o que o usuário escolheu antes, senão a preferência do sistema. */
function initialTheme() {
  const stored = localStorage.getItem("velodna-theme")
  if (stored) return stored
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export default function App() {
  const [view, setView] = useState("summary")
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
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: "var(--fs-lead)",
              letterSpacing: "-0.01em",
              cursor: "pointer",
            }}
            onClick={() => setView("summary")}
          >
            VeloDNA
          </strong>

          <nav className="segmented" role="group" aria-label="Seções">
            {VIEWS.map((v) => (
              <button key={v.id} aria-pressed={view === v.id} onClick={() => setView(v.id)}>
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
        {view === "summary" && (
          <SummaryView onOpenActivity={openActivity} athleteWeightKg={zones?.weight_kg} />
        )}
        {view === "panorama" && <PanoramaView onOpenActivity={openActivity} />}
        {view === "activity" && <ActivityView initialActivity={focusedActivity} />}
      </main>
    </div>
  )
}
