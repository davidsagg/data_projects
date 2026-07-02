import { useEffect, useState } from "react"
import axios from "axios"

export default function ReadinessCard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get("/api/readiness/today")
      .then((r) => setData(r.data))
      .catch(() => setError("Sem dados de recuperação para hoje"))
  }, [])

  const color = (score) => {
    if (score > 75) return "#22c55e"  // verde
    if (score >= 50) return "#eab308" // amarelo
    return "#ef4444"                  // vermelho
  }

  if (error) return (
    <div style={styles.card}>
      <h2 style={styles.title}>Recuperação de Hoje</h2>
      <p style={{ color: "#94a3b8" }}>{error}</p>
    </div>
  )

  if (!data) return (
    <div style={styles.card}>
      <h2 style={styles.title}>Recuperação de Hoje</h2>
      <p style={{ color: "#94a3b8" }}>Carregando...</p>
    </div>
  )

  const c = color(data.score)

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>Recuperação de Hoje</h2>

      <div style={{ textAlign: "center", margin: "16px 0" }}>
        <span style={{ fontSize: 64, fontWeight: 800, color: c }}>
          {data.score}
        </span>
        <span style={{ fontSize: 24, color: "#94a3b8" }}>/100</span>
      </div>

      <div style={styles.barBg}>
        <div style={{ ...styles.barFill, width: `${data.score}%`, background: c }} />
      </div>

      <p style={{ marginTop: 16, color: "#cbd5e1", textAlign: "center" }}>
        {data.recommendation}
      </p>
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
  title: {
    margin: 0,
    fontSize: 18,
    fontWeight: 600,
    color: "#f1f5f9",
  },
  barBg: {
    height: 12,
    background: "#334155",
    borderRadius: 6,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 6,
    transition: "width 0.6s ease",
  },
}
