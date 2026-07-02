import { useEffect, useState } from "react"
import axios from "axios"
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts"

const ZONE_COLORS = {
  Z1: "#64748b",
  Z2: "#3b82f6",
  Z3: "#22c55e",
  Z4: "#f59e0b",
  Z5: "#ef4444",
  Z6: "#a855f7",
}

const ZONE_LABELS = {
  Z1: "Z1 Recuperação",
  Z2: "Z2 Resistência",
  Z3: "Z3 Tempo",
  Z4: "Z4 Limiar",
  Z5: "Z5 VO2max",
  Z6: "Z6 Anaeróbio",
}

function formatTime(s) {
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}min`
  return `${Math.floor(m / 60)}h ${m % 60}min`
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, padding: "8px 12px" }}>
      <p style={{ margin: 0, color: "#f1f5f9", fontWeight: 600 }}>{ZONE_LABELS[d.zone] || d.zone}</p>
      <p style={{ margin: "4px 0 0", color: "#94a3b8", fontSize: 13 }}>{formatTime(d.seconds)} · {d.pct}%</p>
    </div>
  )
}

export default function ZoneChart({ activityId }) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!activityId) return
    setLoading(true)
    setError(null)
    axios.get(`/api/activities/${activityId}/zones`)
      .then((r) => {
        const rows = Object.entries(r.data).map(([zone, v]) => ({
          zone,
          seconds: v.seconds,
          pct: v.pct,
        }))
        setData(rows)
      })
      .catch(() => setError("Sem dados de potência para esta atividade"))
      .finally(() => setLoading(false))
  }, [activityId])

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>Zonas de Potência</h2>
      {!activityId ? (
        <p style={styles.muted}>Selecione uma atividade.</p>
      ) : loading ? (
        <p style={styles.muted}>Carregando...</p>
      ) : error ? (
        <p style={styles.muted}>{error}</p>
      ) : data.length === 0 ? (
        <p style={styles.muted}>Sem dados de potência.</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="zone" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis unit="%" tick={{ fill: "#94a3b8", fontSize: 11 }} domain={[0, 100]} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="pct" radius={[4, 4, 0, 0]}>
                {data.map((entry) => (
                  <Cell key={entry.zone} fill={ZONE_COLORS[entry.zone] || "#94a3b8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={styles.legend}>
            {data.map((d) => (
              <span key={d.zone} style={styles.legendItem}>
                <span style={{ ...styles.dot, background: ZONE_COLORS[d.zone] }} />
                {d.zone} · {d.pct}%
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

const styles = {
  card: {
    background: "#1e293b",
    borderRadius: 12,
    padding: 24,
    boxShadow: "0 2px 12px rgba(0,0,0,0.4)",
  },
  title: { margin: "0 0 16px", fontSize: 18, fontWeight: 600, color: "#f1f5f9" },
  muted: { color: "#94a3b8" },
  legend: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px 14px",
    marginTop: 12,
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    fontSize: 12,
    color: "#94a3b8",
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    display: "inline-block",
  },
}
