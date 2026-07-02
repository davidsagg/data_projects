import { useEffect, useState } from "react"
import axios from "axios"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts"

const DURATIONS = [5, 10, 30, 60, 300, 1200, 3600]

function formatDuration(s) {
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.round(s / 60)}min`
  return `${Math.round(s / 3600)}h`
}

export default function PowerCurveChart() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get("/api/power-curve")
      .then((r) => {
        const filtered = r.data.filter((d) => DURATIONS.includes(d.duration_s))
        setData(filtered.map((d) => ({ ...d, label: formatDuration(d.duration_s) })))
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>Curva de Potência (MMP)</h2>
      {loading ? (
        <p style={styles.muted}>Carregando...</p>
      ) : data.length === 0 ? (
        <p style={styles.muted}>Nenhum dado de potência registrado.</p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              unit=" W"
            />
            <Tooltip
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
              labelStyle={{ color: "#f1f5f9" }}
              formatter={(v) => [`${v} W`, "Melhor Potência"]}
            />
            <Legend wrapperStyle={{ color: "#94a3b8" }} />
            <Line
              type="monotone"
              dataKey="best_power_w"
              stroke="#f59e0b"
              dot={{ r: 4, fill: "#f59e0b" }}
              name="Melhor Potência (W)"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
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
}
