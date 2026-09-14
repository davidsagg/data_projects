/*
 * Visão Coach — conversa livre com o estado do atleta como contexto (US-14).
 *
 * O contexto é montado no backend a cada turno, então a conversa já conhece
 * carga, forma, FTP, saúde e últimos treinos sem que o atleta precise repetir
 * nada. As sugestões iniciais existem porque uma caixa de texto vazia não
 * comunica o que a ferramenta sabe responder.
 */
import { useEffect, useRef, useState } from "react"

import { api } from "../lib/api"
import { fullDate } from "../lib/format"

const SUGGESTIONS = [
  "Como está minha forma para uma prova em 4 semanas?",
  "Meu HRV caiu. Devo treinar amanhã?",
  "Onde estão meus pontos fracos na curva de potência?",
  "Como distribuir 8 horas de treino nesta semana?",
]

export default function CoachView() {
  const [sessionId, setSessionId] = useState(null)
  const [turns, setTurns] = useState([])
  const [question, setQuestion] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [sessions, setSessions] = useState([])
  const endRef = useRef(null)

  useEffect(() => {
    api.coach.sessions().then(setSessions).catch(() => {})
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [turns, busy])

  const send = (text) => {
    const asked = (text ?? question).trim()
    if (!asked || busy) return

    setTurns((current) => [...current, { role: "user", content: asked }])
    setQuestion("")
    setBusy(true)
    setError(null)

    api.coach
      .chat({ question: asked, session_id: sessionId })
      .then((response) => {
        setSessionId(response.session_id)
        setTurns((current) => [
          ...current,
          { role: "assistant", content: response.answer },
        ])
        api.coach.sessions().then(setSessions).catch(() => {})
      })
      .catch((e) =>
        setError(
          e.response?.status === 503
            ? "O Ollama não está acessível. Suba o serviço para conversar."
            : "Não foi possível obter resposta.",
        ),
      )
      .finally(() => setBusy(false))
  }

  const openSession = (id) => {
    api.coach.history(id).then((history) => {
      setSessionId(id)
      setTurns(history.map((h) => ({ role: h.role, content: h.content })))
    })
  }

  const startNew = () => {
    setSessionId(null)
    setTurns([])
    setError(null)
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) minmax(200px, 260px)",
        gap: "var(--space-4)",
        alignItems: "start",
      }}
    >
      <section className="card" style={{ display: "grid", gap: "var(--space-3)" }}>
        <div>
          <h2 className="card-title">Conversa com o treinador</h2>
          <p className="card-subtitle">
            As respostas usam seus dados reais de carga, forma e saúde
          </p>
        </div>

        <div
          style={{
            minHeight: 300,
            maxHeight: 460,
            overflowY: "auto",
            display: "grid",
            gap: "var(--space-3)",
            alignContent: "start",
          }}
        >
          {!turns.length && (
            <div style={{ display: "grid", gap: "var(--space-2)" }}>
              <span className="muted" style={{ fontSize: "var(--fs-small)" }}>
                Comece por uma destas perguntas:
              </span>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  style={{
                    ...bubbleStyle,
                    textAlign: "left",
                    cursor: "pointer",
                    border: "1px dashed var(--border)",
                    background: "transparent",
                    color: "var(--text-secondary)",
                    font: "inherit",
                    fontSize: "var(--fs-small)",
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {turns.map((turn, index) => (
            <div
              key={index}
              style={{
                ...bubbleStyle,
                justifySelf: turn.role === "user" ? "end" : "start",
                maxWidth: "82%",
                background:
                  turn.role === "user"
                    ? "var(--surface-sunken)"
                    : "transparent",
                border:
                  turn.role === "user" ? "none" : "1px solid var(--border)",
                whiteSpace: "pre-wrap",
              }}
            >
              <div
                style={{
                  fontSize: "var(--fs-micro)",
                  color: "var(--text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                  marginBottom: 4,
                }}
              >
                {turn.role === "user" ? "Você" : "Treinador"}
              </div>
              {turn.content}
            </div>
          ))}

          {busy && (
            <div style={{ ...bubbleStyle, color: "var(--text-muted)" }}>
              Pensando…
            </div>
          )}
          <div ref={endRef} />
        </div>

        {error && (
          <p style={{ color: "var(--status-critical)", fontSize: "var(--fs-small)" }}>
            {error}
          </p>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            send()
          }}
          style={{ display: "flex", gap: "var(--space-2)" }}
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Pergunte sobre seu treino…"
            aria-label="Pergunta"
            style={{
              flex: 1,
              minWidth: 0,
              font: "inherit",
              fontSize: "var(--fs-body)",
              padding: "8px 10px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
              background: "var(--surface-1)",
              color: "var(--text-primary)",
            }}
          />
          <button type="submit" disabled={busy || !question.trim()} style={buttonStyle}>
            Enviar
          </button>
        </form>
      </section>

      <section
        className="card"
        style={{ display: "grid", gap: "var(--space-2)", minWidth: 0 }}
      >
        <h2 className="card-title">Conversas</h2>
        <button onClick={startNew} style={buttonStyle}>
          Nova conversa
        </button>
        {sessions.length === 0 && <p className="muted">Nenhuma ainda.</p>}
        {sessions.map((s) => (
          <button
            key={s.session_id}
            onClick={() => openSession(s.session_id)}
            style={{
              textAlign: "left",
              font: "inherit",
              fontSize: "var(--fs-small)",
              padding: "var(--space-2)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
              background:
                s.session_id === sessionId
                  ? "var(--surface-sunken)"
                  : "transparent",
              color: "var(--text-primary)",
              cursor: "pointer",
              minWidth: 0,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {s.first_question || "Conversa"}
            </div>
            <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>
              {fullDate(s.last_message_at)} · {s.turns} mensagens
            </div>
          </button>
        ))}
      </section>
    </div>
  )
}

const bubbleStyle = {
  padding: "var(--space-3)",
  borderRadius: "var(--radius)",
  fontSize: "var(--fs-body)",
  lineHeight: 1.5,
}

const buttonStyle = {
  font: "inherit",
  fontSize: "var(--fs-small)",
  fontWeight: 600,
  padding: "8px 14px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "var(--surface-sunken)",
  color: "var(--text-primary)",
  cursor: "pointer",
}
