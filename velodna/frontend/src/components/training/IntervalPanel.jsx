/*
 * Estrutura do treino — os blocos de esforço que a média esconde.
 *
 * A leitura principal é a série ("4 × 8min @ 240 W"), que é como o ciclista
 * descreve o próprio treino. Os blocos individuais ficam abaixo, para quem
 * quer conferir se o quarto caiu em relação ao primeiro.
 */
import { useEffect, useState } from "react"

import ChartFrame from "../viz/ChartFrame"
import { api } from "../../lib/api"
import { duration, num, watts } from "../../lib/format"

export default function IntervalPanel({ activityId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activityId) return undefined
    let cancelled = false
    setLoading(true)

    api.training
      .intervals(activityId)
      .then((result) => !cancelled && setData(result))
      .catch(() => !cancelled && setData(null))
      .finally(() => !cancelled && setLoading(false))

    return () => {
      cancelled = true
    }
  }, [activityId])

  if (loading) return null
  if (!data) return null

  if (!data.interval_count) {
    return (
      <ChartFrame
        title="Estrutura do treino"
        subtitle={
          data.threshold_w
            ? `Nenhum bloco acima de ${num(data.threshold_w, 0)} W — pedal contínuo`
            : "Sem FTP de referência para esta data"
        }
      />
    )
  }

  // Séries de um bloco só não são estrutura: num pedal de montanha cada subida
  // vira seu próprio "grupo", e listar vinte deles como se fossem prescrição de
  // treino inventa uma intenção que não existiu. Quando nada se repete, só a
  // tabela de blocos é mostrada.
  const repeated = data.sets.filter((set) => set.count > 1)

  return (
    <ChartFrame
      title="Estrutura do treino"
      subtitle={
        repeated.length
          ? `${data.interval_count} blocos acima de ${num(data.threshold_w, 0)} W (FTP ${num(data.ftp_w_at_time, 0)} W)`
          : `${data.interval_count} esforços acima de ${num(data.threshold_w, 0)} W, sem repetição — provavelmente terreno, não treino estruturado`
      }
    >
      <div style={{ display: "grid", gap: "var(--space-3)" }}>
        {repeated.map((set, index) => (
          <div key={index} style={{ display: "grid", gap: "var(--space-1)" }}>
            <strong style={{ fontSize: "var(--fs-lead)" }}>{set.label}</strong>
            {set.avg_recovery_s && (
              <span className="muted" style={{ fontSize: "var(--fs-small)" }}>
                recuperação média de {duration(set.avg_recovery_s)}
              </span>
            )}
          </div>
        ))}

        <table className="tabular" style={{ width: "100%", fontSize: "var(--fs-small)" }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--text-muted)" }}>
              <th style={{ fontWeight: 500 }}>#</th>
              <th style={{ fontWeight: 500 }}>Início</th>
              <th style={{ fontWeight: 500 }}>Duração</th>
              <th style={{ fontWeight: 500, textAlign: "right" }}>Média</th>
              <th style={{ fontWeight: 500, textAlign: "right" }}>NP</th>
              <th style={{ fontWeight: 500, textAlign: "right" }}>IF</th>
              <th style={{ fontWeight: 500, textAlign: "right" }}>FC</th>
            </tr>
          </thead>
          <tbody>
            {data.intervals.map((interval, index) => (
              <tr key={interval.start_s} style={{ borderTop: "1px solid var(--border)" }}>
                <td>{index + 1}</td>
                <td>{duration(interval.start_s)}</td>
                <td>{duration(interval.duration_s)}</td>
                <td style={{ textAlign: "right" }}>{watts(interval.avg_power_w)}</td>
                <td style={{ textAlign: "right" }}>{watts(interval.normalized_power_w)}</td>
                <td style={{ textAlign: "right" }}>
                  {num(interval.intensity_factor, 2)}
                </td>
                <td style={{ textAlign: "right" }}>
                  {interval.avg_hr_bpm ? `${num(interval.avg_hr_bpm)} bpm` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartFrame>
  )
}
