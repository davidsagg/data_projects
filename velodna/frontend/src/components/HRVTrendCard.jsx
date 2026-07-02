import { useEffect, useState } from "react"
import axios from "axios"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts"

function formatDate(d) {
  if (!d) return ""
  return new Date(d).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })
}

export default function HRVTrendCard() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [trend, setTrend] = useState(null)

  useEffect(() => {
    axios.get("/api/health-daily?days=30")
      .then((r) => {
        const rows = r.data
          .filter((d) => d.hrv_rmssd_ms != null)
          .map((d) => ({
            date: formatDate(d.date),
            hrv: Math.round(d.hrv_rmssd_ms),
            sleep: d.sleep_score,
          }))
          .reverse()

        setData(rows)

        if (rows.length >= 7) {
          const recent = rows.slice(-3).reduce((s, r) => s + r.hrv, 0) / 3
          const baseline = rows.slice(0, 7).reduce((s, r) => s + r.hrv, 0) / 7
          if (recent < baseline * 0.85) setTrend("declining")
          else if (recent > baseline * 1.05) setTrend("improving")
          else setTrend("stable")
        }
      })
      .finally(() => setLoading(false))
  }, [])

  const avg = data.length ? Math.round(data.reduce((s, d) => s + d.hrv, 0) / data.length) : null

  const trendColor = trend === "declining" ? "#ef4444" : trend === "improving" ? "#22c55e" : "#f59e0b"
  const trendLabel = trend === "declining" ? "↘ Em queda" : trend === "improving" ? "↗ Em alta" : "→ Estável"

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <h2 style={styles.title}>Tendência HRV (30 dias)</h2>
        {trend && (
          <span style={{ ...styles.badge, color: trendColor, borderColor: trendColor }}>
            {trendLabel}
          </span>
        )}
      </div>

      {loading ? (
        <p style={styles.muted}>Carregando...</p>
      ) : data.length === 0 ? (
        <p style={styles.muted}>Sem dados de HRV. Sincronize o Garmin para ver a tendência.</p>
      ) : (
        <>
          <div style={styles.statsRow}>
            <div style={styles.stat}>
              <span style={styles.statVal}>{avg}</span>
              <span style={styles.statLabel}>ms médio</span>
            </div>
            <div style={styles.stat}>
              <span style={styles.statVal}>{Math.max(...data.map((d) => d.hrv))}</span>
              <span style={styles.statLabel}>ms máximo</span>
            </div>
            <div style={styles.stat}>
              <span style={styles.statVal}>{Math.min(...data.map((d) => d.hrv))}</span>
              <span style={styles.statLabel}>ms mínimo</span>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#64748b", fontSize: 10 }}
                interval={Math.floor(data.length / 5)}
              />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} unit=" ms" />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                labelStyle={{ color: "#f1f5f9" }}
                formatter={(v) => [`${v} ms`, "HRV rMSSD"]}
              />
              {avg && (
                <ReferenceLine
                  y={avg}
                  stroke="#f59e0b"
                  strokeDasharray="4 4"
                  label={{ value: "média", fill: "#f59e0b", fontSize: 10 }}
                />
              )}
              <Line
                type="monotone"
                dataKey="hrv"
                stroke="#22c55e"
                dot={false}
                strokeWidth={2}
                name="HRV rMSSD"
              />
            </LineChart>
          </ResponsiveContainer>
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
  header: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 16,
  },
  title: { margin: 0, fontSize: 18, fontWeight: 600, color: "#f1f5f9", flex: 1 },
  badge: {
    fontSize: 12,
    fontWeight: 600,
    border: "1px solid",
    borderRadius: 12,
    padding: "2px 10px",
  },
  muted: { color: "#94a3b8" },
  statsRow: {
    display: "flex",
    gap: 24,
    marginBottom: 16,
  },
  stat: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  statVal: {
    fontSize: 24,
    fontWeight: 700,
    color: "#22c55e",
  },
  statLabel: {
    fontSize: 11,
    color: "#64748b",
  },
}
