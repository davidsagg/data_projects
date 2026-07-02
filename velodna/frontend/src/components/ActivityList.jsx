import { useEffect, useState } from "react"
import axios from "axios"

function formatDuration(s) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}min` : `${m}min`
}

function formatDate(dt) {
  if (!dt) return "—"
  return new Date(dt).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" })
}

function sportIcon(sport) {
  if (!sport) return "🚴"
  const s = sport.toLowerCase()
  if (s.includes("run")) return "🏃"
  if (s.includes("swim")) return "🏊"
  if (s.includes("walk")) return "🚶"
  return "🚴"
}

export default function ActivityList({ selectedId, onSelect }) {
  const [activities, setActivities] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")

  useEffect(() => {
    axios.get("/api/activities")
      .then((r) => setActivities(r.data))
      .finally(() => setLoading(false))
  }, [])

  const filtered = activities.filter((a) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (a.sport_type || "").toLowerCase().includes(q) ||
      formatDate(a.start_time).toLowerCase().includes(q)
    )
  })

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <span style={styles.title}>Atividades</span>
        <span style={styles.count}>{activities.length}</span>
      </div>

      <input
        style={styles.search}
        placeholder="Buscar..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {loading ? (
        <p style={styles.muted}>Carregando...</p>
      ) : filtered.length === 0 ? (
        <p style={styles.muted}>Nenhuma atividade.</p>
      ) : (
        <div style={styles.list}>
          {filtered.map((a) => (
            <div
              key={a.activity_id}
              style={{
                ...styles.item,
                ...(a.activity_id === selectedId ? styles.itemActive : {}),
              }}
              onClick={() => onSelect(a)}
            >
              <div style={styles.itemTop}>
                <span style={styles.icon}>{sportIcon(a.sport_type)}</span>
                <span style={styles.date}>{formatDate(a.start_time)}</span>
              </div>
              <div style={styles.itemStats}>
                <span>{a.distance_m ? `${(a.distance_m / 1000).toFixed(1)} km` : "—"}</span>
                <span>{a.duration_s ? formatDuration(a.duration_s) : "—"}</span>
                {a.tss != null && <span style={styles.tss}>TSS {Math.round(a.tss)}</span>}
              </div>
              {a.avg_power_w && (
                <div style={styles.power}>{Math.round(a.avg_power_w)} W médio</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const styles = {
  wrap: {
    background: "#1e293b",
    borderRadius: 12,
    padding: "16px 12px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    height: "100%",
    overflowY: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  title: { fontSize: 16, fontWeight: 600, color: "#f1f5f9" },
  count: {
    background: "#334155",
    color: "#94a3b8",
    fontSize: 12,
    borderRadius: 20,
    padding: "2px 8px",
  },
  search: {
    background: "#0f172a",
    border: "1px solid #334155",
    borderRadius: 6,
    color: "#f1f5f9",
    padding: "6px 10px",
    fontSize: 13,
    outline: "none",
  },
  list: {
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    flex: 1,
  },
  item: {
    background: "#0f172a",
    borderRadius: 8,
    padding: "10px 12px",
    cursor: "pointer",
    border: "1px solid transparent",
    transition: "border-color 0.15s",
  },
  itemActive: {
    border: "1px solid #3b82f6",
    background: "#172033",
  },
  itemTop: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    marginBottom: 4,
  },
  icon: { fontSize: 14 },
  date: { fontSize: 13, color: "#94a3b8" },
  itemStats: {
    display: "flex",
    gap: 12,
    fontSize: 13,
    color: "#cbd5e1",
    fontWeight: 500,
  },
  tss: {
    color: "#f59e0b",
    marginLeft: "auto",
  },
  power: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 2,
  },
  muted: { color: "#64748b", fontSize: 13 },
}
