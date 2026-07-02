import { useEffect, useState } from "react"
import axios from "axios"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts"

export default function PMCChart() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get("/api/pmc")
      .then((r) => setData(r.data))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>Performance Management Chart</h2>
      {loading ? (
        <p style={styles.muted}>Carregando...</p>
      ) : data.length === 0 ? (
        <p style={styles.muted}>Nenhum dado de carga de treino registrado.</p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
              labelStyle={{ color: "#f1f5f9" }}
            />
            <Legend wrapperStyle={{ color: "#94a3b8" }} />
            <Line type="monotone" dataKey="ctl" stroke="#3b82f6" dot={false} name="CTL (fitness)" strokeWidth={2} />
            <Line type="monotone" dataKey="atl" stroke="#ef4444" dot={false} name="ATL (fadiga)" strokeWidth={2} />
            <Line type="monotone" dataKey="tsb" stroke="#22c55e" dot={false} name="TSB (forma)" strokeWidth={2} />
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
