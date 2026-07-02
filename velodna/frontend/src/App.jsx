import { useEffect, useState } from "react"
import axios from "axios"
import ReadinessCard from "./components/ReadinessCard"
import PMCChart from "./components/PMCChart"
import PowerCurveChart from "./components/PowerCurveChart"
import RouteMap from "./components/RouteMap"
import ActivityList from "./components/ActivityList"
import ZoneChart from "./components/ZoneChart"
import HRVTrendCard from "./components/HRVTrendCard"
import CoachPanel from "./components/CoachPanel"

const TABS = ["Visão Geral", "Atividade", "Coach"]

export default function App() {
  const [tab, setTab] = useState("Visão Geral")
  const [selectedActivity, setSelectedActivity] = useState(null)
  const [waypoints, setWaypoints] = useState([])
  const [loadingStreams, setLoadingStreams] = useState(false)
  const [latestActivity, setLatestActivity] = useState(null)

  // Carrega atividade mais recente para o header
  useEffect(() => {
    axios.get("/api/activities/latest").then((r) => setLatestActivity(r.data)).catch(() => {})
  }, [])

  // Ao selecionar atividade, carrega streams GPS e vai para aba Atividade
  const handleSelectActivity = (activity) => {
    setSelectedActivity(activity)
    setWaypoints([])
    setTab("Atividade")
    setLoadingStreams(true)
    axios.get(`/api/activities/${activity.activity_id}/streams?every_n=6`)
      .then((r) => setWaypoints(r.data))
      .catch(() => setWaypoints([]))
      .finally(() => setLoadingStreams(false))
  }

  const actDate = selectedActivity
    ? new Date(selectedActivity.start_time).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" })
    : null

  return (
    <div style={styles.page}>
      {/* Header */}
      <header style={styles.header}>
        <h1 style={styles.logo}>🚴 VeloDNA</h1>
        <span style={styles.subtitle}>Performance Ciclística Local</span>
        {latestActivity && (
          <span style={styles.badge}>
            Última atividade: {new Date(latestActivity.start_time).toLocaleDateString("pt-BR")}
            &nbsp;·&nbsp;{(latestActivity.distance_m / 1000).toFixed(1)} km
            &nbsp;·&nbsp;{Math.round(latestActivity.duration_s / 60)} min
          </span>
        )}
      </header>

      {/* Tabs */}
      <nav style={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t}
            style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </nav>

      {/* Conteúdo principal */}
      <div style={styles.body}>

        {/* ── Visão Geral ── */}
        {tab === "Visão Geral" && (
          <div style={styles.grid}>
            <div style={styles.fullWidth}>
              <ReadinessCard />
            </div>
            <div style={styles.half}>
              <PMCChart />
            </div>
            <div style={styles.half}>
              <HRVTrendCard />
            </div>
            <div style={styles.half}>
              <PowerCurveChart />
            </div>
          </div>
        )}

        {/* ── Atividade ── */}
        {tab === "Atividade" && (
          <div style={styles.activityLayout}>
            {/* Sidebar — lista */}
            <div style={styles.sidebar}>
              <ActivityList
                selectedId={selectedActivity?.activity_id}
                onSelect={handleSelectActivity}
              />
            </div>

            {/* Área de detalhe */}
            <div style={styles.detail}>
              {!selectedActivity ? (
                <div style={styles.emptyDetail}>
                  <p style={styles.emptyText}>← Selecione uma atividade na lista</p>
                </div>
              ) : (
                <div style={styles.detailGrid}>
                  {/* Cabeçalho da atividade */}
                  <div style={{ ...styles.fullWidth, ...styles.actHeader }}>
                    <span style={styles.actTitle}>
                      🚴 {actDate}
                    </span>
                    <span style={styles.actStats}>
                      {selectedActivity.distance_m
                        ? `${(selectedActivity.distance_m / 1000).toFixed(1)} km`
                        : "—"}
                      {selectedActivity.duration_s
                        ? ` · ${Math.round(selectedActivity.duration_s / 60)} min`
                        : ""}
                      {selectedActivity.avg_power_w
                        ? ` · ${Math.round(selectedActivity.avg_power_w)} W médio`
                        : ""}
                      {selectedActivity.tss != null
                        ? ` · TSS ${Math.round(selectedActivity.tss)}`
                        : ""}
                    </span>
                  </div>

                  <div style={styles.fullWidth}>
                    <RouteMap
                      waypoints={loadingStreams ? [] : waypoints}
                      activityDate={actDate}
                    />
                  </div>

                  <div style={styles.half}>
                    <ZoneChart activityId={selectedActivity.activity_id} />
                  </div>

                  <div style={styles.half}>
                    <CoachPanel activityId={selectedActivity.activity_id} />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Coach ── */}
        {tab === "Coach" && (
          <div style={styles.grid}>
            <div style={styles.fullWidth}>
              <CoachPanel activityId={selectedActivity?.activity_id} />
            </div>
            <div style={styles.fullWidth}>
              <div style={styles.coachHint}>
                <p style={styles.hintText}>
                  💡 Para analisar uma atividade específica, selecione-a na aba <strong>Atividade</strong> e clique em "Analisar atividade".
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#0f172a",
    fontFamily: "'Inter', system-ui, sans-serif",
    color: "#f1f5f9",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    padding: "16px 32px",
    borderBottom: "1px solid #1e293b",
    flexWrap: "wrap",
  },
  logo: { margin: 0, fontSize: 20, fontWeight: 700, color: "#f1f5f9" },
  subtitle: { fontSize: 13, color: "#64748b" },
  badge: {
    marginLeft: "auto",
    fontSize: 12,
    color: "#94a3b8",
    background: "#1e293b",
    padding: "4px 12px",
    borderRadius: 20,
    border: "1px solid #334155",
  },
  tabs: {
    display: "flex",
    gap: 0,
    padding: "0 32px",
    borderBottom: "1px solid #1e293b",
    background: "#0f172a",
  },
  tab: {
    background: "none",
    border: "none",
    color: "#64748b",
    fontSize: 14,
    fontWeight: 500,
    padding: "12px 20px",
    cursor: "pointer",
    borderBottom: "2px solid transparent",
    transition: "color 0.15s, border-color 0.15s",
  },
  tabActive: {
    color: "#f1f5f9",
    borderBottom: "2px solid #3b82f6",
  },
  body: {
    padding: 24,
    maxWidth: 1400,
    margin: "0 auto",
  },
  // Visão Geral grid
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 20,
  },
  fullWidth: { gridColumn: "1 / -1" },
  half: { gridColumn: "span 1" },
  // Atividade layout
  activityLayout: {
    display: "grid",
    gridTemplateColumns: "280px 1fr",
    gap: 20,
    height: "calc(100vh - 140px)",
  },
  sidebar: {
    overflowY: "auto",
  },
  detail: {
    overflowY: "auto",
  },
  emptyDetail: {
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#1e293b",
    borderRadius: 12,
  },
  emptyText: {
    color: "#475569",
    fontSize: 15,
  },
  detailGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 16,
  },
  actHeader: {
    background: "#1e293b",
    borderRadius: 10,
    padding: "12px 16px",
    display: "flex",
    alignItems: "center",
    gap: 16,
    flexWrap: "wrap",
  },
  actTitle: {
    fontWeight: 600,
    fontSize: 15,
    color: "#f1f5f9",
  },
  actStats: {
    fontSize: 13,
    color: "#94a3b8",
  },
  coachHint: {
    background: "#1e293b",
    borderRadius: 10,
    padding: "14px 18px",
    border: "1px solid #334155",
  },
  hintText: {
    margin: 0,
    color: "#64748b",
    fontSize: 14,
  },
}
