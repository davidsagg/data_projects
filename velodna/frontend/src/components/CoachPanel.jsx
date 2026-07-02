import { useState } from "react"
import axios from "axios"

export default function CoachPanel({ activityId }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const analyze = () => {
    if (!activityId) return
    setLoading(true)
    setError(null)
    setResult(null)
    axios.post("/api/coach/analyze-activity", { activity_id: activityId })
      .then((r) => setResult(r.data))
      .catch((e) => {
        const msg = e.response?.data?.detail || "Erro ao conectar com o Coach. Verifique se o Ollama está rodando."
        setError(msg)
      })
      .finally(() => setLoading(false))
  }

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <h2 style={styles.title}>🤖 AI Coach</h2>
        <button
          style={{
            ...styles.btn,
            ...(loading || !activityId ? styles.btnDisabled : {}),
          }}
          onClick={analyze}
          disabled={loading || !activityId}
        >
          {loading ? "Analisando..." : "Analisar atividade"}
        </button>
      </div>

      {!activityId && (
        <p style={styles.muted}>Selecione uma atividade para análise do coach.</p>
      )}

      {error && (
        <div style={styles.errorBox}>
          <span style={styles.errorIcon}>⚠️</span> {error}
        </div>
      )}

      {result && (
        <div style={styles.result}>
          {result.summary && (
            <div style={styles.section}>
              <p style={styles.sectionLabel}>Resumo</p>
              <p style={styles.sectionText}>{result.summary}</p>
            </div>
          )}

          {result.highlights?.length > 0 && (
            <div style={styles.section}>
              <p style={styles.sectionLabel}>✅ Destaques</p>
              <ul style={styles.list}>
                {result.highlights.map((h, i) => (
                  <li key={i} style={styles.listItem}>{h}</li>
                ))}
              </ul>
            </div>
          )}

          {result.alerts?.length > 0 && (
            <div style={styles.section}>
              <p style={styles.sectionLabel}>⚠️ Alertas</p>
              <ul style={styles.list}>
                {result.alerts.map((a, i) => (
                  <li key={i} style={{ ...styles.listItem, color: "#fbbf24" }}>{a}</li>
                ))}
              </ul>
            </div>
          )}

          {result.recommendations?.length > 0 && (
            <div style={styles.section}>
              <p style={styles.sectionLabel}>💡 Recomendações</p>
              <ul style={styles.list}>
                {result.recommendations.map((r, i) => (
                  <li key={i} style={styles.listItem}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
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
    justifyContent: "space-between",
    marginBottom: 16,
  },
  title: { margin: 0, fontSize: 18, fontWeight: 600, color: "#f1f5f9" },
  btn: {
    background: "#3b82f6",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    padding: "8px 16px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnDisabled: {
    background: "#334155",
    color: "#64748b",
    cursor: "not-allowed",
  },
  muted: { color: "#64748b", fontSize: 13 },
  errorBox: {
    background: "#450a0a",
    border: "1px solid #7f1d1d",
    borderRadius: 8,
    padding: "10px 14px",
    color: "#fca5a5",
    fontSize: 13,
    display: "flex",
    gap: 8,
    alignItems: "flex-start",
  },
  errorIcon: { flexShrink: 0 },
  result: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  section: {},
  sectionLabel: {
    margin: "0 0 6px",
    fontSize: 12,
    fontWeight: 700,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  sectionText: {
    margin: 0,
    color: "#cbd5e1",
    fontSize: 14,
    lineHeight: 1.6,
  },
  list: {
    margin: 0,
    paddingLeft: 18,
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  listItem: {
    color: "#cbd5e1",
    fontSize: 14,
    lineHeight: 1.5,
  },
}
