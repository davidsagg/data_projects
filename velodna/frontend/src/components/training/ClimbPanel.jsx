/*
 * Subidas da atividade.
 *
 * Num pedal de montanha a média da atividade não descreve nada: 129 W num dia
 * de 1.570 m mistura meia hora a 210 W subindo com meia hora a zero descendo.
 * O que descreve o esforço é cada subida.
 *
 * A coluna que carrega a leitura é o **VAM** — metros verticais por hora. É o
 * que permite comparar subidas de inclinações diferentes e o que mostra
 * progressão melhor que a potência bruta, porque já embute o peso. Quatro
 * subidas com VAM parecido significam ritmo constante; uma queda progressiva
 * mostra onde o atleta começou a pagar.
 */
import { useEffect, useState } from "react"

import ChartFrame from "../viz/ChartFrame"
import { api } from "../../lib/api"
import { duration, num } from "../../lib/format"

export default function ClimbPanel({ activityId }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!activityId) return undefined
    let cancelled = false
    setData(null)

    api.analysis
      .climbs(activityId)
      .then((r) => !cancelled && setData(r))
      .catch(() => !cancelled && setData(null))

    return () => {
      cancelled = true
    }
  }, [activityId])

  if (!data?.summary?.count) return null

  const { summary, climbs } = data
  const maxVam = Math.max(...climbs.map((c) => c.vam_mh), 1)

  return (
    <ChartFrame
      title="Subidas"
      subtitle={
        `${summary.count} ${summary.count === 1 ? "subida" : "subidas"} · ` +
        `${num(summary.total_gain_m, 0)} m acumulados · ` +
        `VAM médio ${num(summary.avg_vam_mh, 0)} m/h`
      }
    >
      <div className="scroll-x">
        <table
          className="tabular"
          style={{ width: "100%", minWidth: 620, fontSize: "var(--fs-small)" }}
        >
          <thead>
            <tr style={{ textAlign: "left", color: "var(--text-tertiary)" }}>
              <Th>Início</Th>
              <Th>Duração</Th>
              <Th align="right">Ganho</Th>
              <Th align="right">Inclinação</Th>
              <Th align="right">VAM</Th>
              <Th align="right">Potência</Th>
              <Th align="right">FC</Th>
              <Th>Cat.</Th>
            </tr>
          </thead>
          <tbody>
            {climbs.map((climb) => (
              <tr
                key={climb.start_s}
                style={{ borderTop: "1px solid var(--border-subtle)" }}
              >
                <td>{duration(climb.start_s)}</td>
                <td>{duration(climb.duration_s)}</td>
                <td style={{ textAlign: "right" }}>
                  +{num(climb.elevation_gain_m, 0)} m
                </td>
                <td style={{ textAlign: "right" }}>
                  {num(climb.avg_gradient_pct, 1)}%
                </td>
                <td style={{ textAlign: "right" }}>
                  {/* Barra embutida na célula: compara as subidas entre si sem
                      gastar um gráfico inteiro para seis linhas. */}
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      justifyContent: "flex-end",
                      width: "100%",
                    }}
                  >
                    <span
                      style={{
                        width: `${(climb.vam_mh / maxVam) * 44}px`,
                        height: 8,
                        background: "var(--ctl)",
                        borderRadius: 2,
                      }}
                    />
                    {num(climb.vam_mh, 0)}
                  </span>
                </td>
                <td style={{ textAlign: "right" }}>
                  {climb.avg_power_w ? `${num(climb.avg_power_w, 0)} W` : "—"}
                  {climb.watts_per_kg && (
                    <span className="muted"> · {num(climb.watts_per_kg, 2)} W/kg</span>
                  )}
                </td>
                <td style={{ textAlign: "right" }}>
                  {climb.avg_hr_bpm ? `${num(climb.avg_hr_bpm, 0)}` : "—"}
                </td>
                <td>{climb.category}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartFrame>
  )
}

function Th({ children, align = "left" }) {
  return <th style={{ fontWeight: 500, textAlign: align }}>{children}</th>
}
