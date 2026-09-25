/*
 * Perfil de capacidade — forças e limitadores por duração.
 *
 * A curva de potência diz quanto o atleta produz; não diz onde ele está pior em
 * relação a si mesmo. Um número de 5 minutos alto não significa nada se o de 20
 * estiver ainda mais alto — o limitador é relativo.
 *
 * A referência é o próprio atleta, não tabela populacional: percentis dependem
 * de peso, idade e categoria, e erram feio no indivíduo. A evolução contra o
 * próprio recorde não erra.
 */
import { useEffect, useState } from "react"

import ChartFrame from "../viz/ChartFrame"
import { api } from "../../lib/api"
import { num, shortDuration, watts } from "../../lib/format"

const WINDOWS = [
  { label: "90d", days: 90 },
  { label: "180d", days: 180 },
  { label: "1a", days: 365 },
]

const CLASSIFICATION_TOKEN = {
  força: "--status-good",
  limitador: "--status-warning",
  normal: null,
  "sem dados": null,
}

export default function CapacityProfile() {
  const [window, setWindow] = useState(WINDOWS[0])
  const [data, setData] = useState(null)

  useEffect(() => {
    let cancelled = false
    setData(null)

    api.analysis
      .capacityProfile({ days: window.days, sport: "cycling" })
      .then((r) => !cancelled && setData(r))
      .catch(() => !cancelled && setData(null))

    return () => {
      cancelled = true
    }
  }, [window])

  if (!data?.points?.length) return null

  const scored = data.points.filter((p) => p.pct_of_best !== null)
  if (!scored.length) {
    return (
      <ChartFrame title="Perfil de capacidade">
        <p className="muted">Histórico insuficiente para traçar o perfil.</p>
      </ChartFrame>
    )
  }

  return (
    <ChartFrame
      title="Perfil de capacidade"
      subtitle={data.summary}
      action={
        <nav className="segmented" role="group" aria-label="Janela">
          {WINDOWS.map((w) => (
            <button
              key={w.label}
              aria-pressed={window.label === w.label}
              onClick={() => setWindow(w)}
            >
              {w.label}
            </button>
          ))}
        </nav>
      }
    >
      <div style={{ display: "grid", gap: "var(--space-4)" }}>
        {data.points.map((point) => (
          <div
            key={point.duration_s}
            style={{
              display: "grid",
              gridTemplateColumns: "140px 1fr 140px",
              alignItems: "center",
              gap: "var(--space-4)",
              fontSize: "var(--fs-small)",
            }}
          >
            <span style={{ color: "var(--text-secondary)" }}>
              <strong style={{ color: "var(--text-primary)" }}>
                {shortDuration(point.duration_s)}
              </strong>{" "}
              {point.label}
            </span>

            <div
              style={{
                position: "relative",
                height: 10,
                background: "var(--surface-sunken)",
                borderRadius: "var(--radius-sm)",
              }}
            >
              {point.pct_of_best !== null && (
                <div
                  style={{
                    width: `${Math.min(point.pct_of_best, 100)}%`,
                    height: "100%",
                    background: "var(--ctl)",
                    borderRadius: "var(--radius-sm)",
                  }}
                />
              )}
              {/* Marca dos 90%: abaixo dela a duração entra como limitador,
                  e é mais fácil ver a linha que comparar números. */}
              <span
                style={{
                  position: "absolute",
                  left: "90%",
                  top: -3,
                  width: 1,
                  height: 16,
                  background: "var(--border-strong)",
                }}
              />
            </div>

            <span
              className="tabular"
              style={{
                textAlign: "right",
                color: CLASSIFICATION_TOKEN[point.classification]
                  ? `var(${CLASSIFICATION_TOKEN[point.classification]})`
                  : "var(--text-secondary)",
              }}
            >
              {point.pct_of_best === null
                ? "—"
                : `${num(point.pct_of_best, 0)}% · ${watts(point.current_w)}`}
            </span>
          </div>
        ))}

        <p className="card-subtitle" style={{ margin: 0 }}>
          Percentual do melhor histórico do atleta em cada duração. A marca é
          90%: abaixo dela, a duração conta como limitador.
          {data.limiters.length > 0 && (
            <>
              {" "}Limitadores agora:{" "}
              <strong style={{ color: "var(--text-primary)" }}>
                {data.limiters.join(", ")}
              </strong>
              .
            </>
          )}
        </p>
      </div>
    </ChartFrame>
  )
}
