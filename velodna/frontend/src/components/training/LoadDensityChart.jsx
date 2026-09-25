/*
 * Densidade de carga interna × externa.
 *
 * Cada célula é uma faixa de potência cruzada com uma faixa de FC, e o tom diz
 * quanto tempo o atleta passou ali. A leitura é a relação entre o que ele
 * produziu e o que aquilo custou — e é a nuvem inteira que importa, não pontos
 * isolados: com ganho de base ela se desloca para a direita e para baixo, a
 * mesma potência passando a custar menos batimentos.
 *
 * Rampa sequencial de um hue porque a grandeza é magnitude contínua (tempo),
 * não categoria.
 */
import { useEffect, useMemo, useState } from "react"

import ChartFrame from "../viz/ChartFrame"
import { api } from "../../lib/api"
import { num } from "../../lib/format"

const STEPS = ["--seq-100", "--seq-250", "--seq-400", "--seq-550", "--seq-700"]

export default function LoadDensityChart({ activityId }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!activityId) return undefined
    let cancelled = false
    setData(null)

    api.analysis
      .loadDensity(activityId)
      .then((r) => !cancelled && setData(r))
      .catch(() => !cancelled && setData(null))

    return () => {
      cancelled = true
    }
  }, [activityId])

  const grid = useMemo(() => buildGrid(data), [data])

  if (!grid) return null

  return (
    <ChartFrame
      title="Carga interna × externa"
      subtitle={
        `Tempo em cada combinação de potência e frequência cardíaca · ` +
        `faixas de ${data.power_bin_w} W e ${data.hr_bin_bpm} bpm`
      }
    >
      <div className="scroll-x">
        <div style={{ display: "grid", gap: "var(--space-2)", minWidth: 520 }}>
          {grid.rows.map((row) => (
            <div
              key={row.hr}
              style={{
                display: "grid",
                gridTemplateColumns: `52px repeat(${grid.powers.length}, 1fr)`,
                gap: 2,
                alignItems: "center",
              }}
            >
              <span
                className="tabular"
                style={{ fontSize: "var(--fs-micro)", color: "var(--text-tertiary)" }}
              >
                {row.hr} bpm
              </span>
              {grid.powers.map((power) => {
                const seconds = row.cells[power] || 0
                return (
                  <div
                    key={power}
                    title={
                      seconds
                        ? `${power}–${power + data.power_bin_w} W a ${row.hr} bpm: ${Math.round(seconds / 60)} min`
                        : undefined
                    }
                    style={{
                      height: 18,
                      borderRadius: 2,
                      background: seconds
                        ? `var(${STEPS[bucket(seconds, grid.max)]})`
                        : "var(--surface-sunken)",
                    }}
                  />
                )
              })}
            </div>
          ))}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: `52px repeat(${grid.powers.length}, 1fr)`,
              gap: 2,
            }}
          >
            <span />
            {grid.powers.map((power, i) => (
              <span
                key={power}
                className="tabular"
                style={{
                  fontSize: "var(--fs-micro)",
                  color: "var(--text-tertiary)",
                  textAlign: "center",
                }}
              >
                {/* Um rótulo a cada duas colunas: todos colidiriam. */}
                {i % 2 === 0 ? power : ""}
              </span>
            ))}
          </div>
          <span
            className="label"
            style={{ textAlign: "center", marginTop: "var(--space-2)" }}
          >
            Potência (W)
          </span>
        </div>
      </div>
    </ChartFrame>
  )
}

/** Organiza as células em linhas de FC decrescente e colunas de potência. */
function buildGrid(data) {
  if (!data?.cells?.length) return null

  const powers = [...new Set(data.cells.map((c) => c.power_w))].sort((a, b) => a - b)
  const hrs = [...new Set(data.cells.map((c) => c.hr_bpm))].sort((a, b) => b - a)
  const max = Math.max(...data.cells.map((c) => c.seconds))

  const rows = hrs.map((hr) => ({
    hr,
    cells: Object.fromEntries(
      data.cells.filter((c) => c.hr_bpm === hr).map((c) => [c.power_w, c.seconds]),
    ),
  }))

  return { powers, rows, max }
}

/**
 * Escolhe o passo da rampa.
 *
 * A escala é de raiz quadrada, não linear: a distribuição de tempo é muito
 * assimétrica — o atleta passa a maior parte do pedal em poucas células — e na
 * escala linear todo o resto colapsaria no tom mais claro.
 */
function bucket(seconds, max) {
  const ratio = Math.sqrt(seconds / max)
  return Math.min(STEPS.length - 1, Math.floor(ratio * STEPS.length))
}
