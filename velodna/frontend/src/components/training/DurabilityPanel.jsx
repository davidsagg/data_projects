/*
 * Durabilidade — o que sobra da potência depois do trabalho acumulado.
 *
 * Quando a atividade não é longa o bastante, o painel diz isso em vez de
 * mostrar um número. Um veredito "excelente" calculado sobre 20 minutos de
 * pedal seria pior que veredito nenhum: parece informação e não é.
 */
import { useEffect, useState } from "react"

import ChartFrame from "../viz/ChartFrame"
import { api } from "../../lib/api"
import { num, shortDuration, watts } from "../../lib/format"

const VERDICT_TOKEN = {
  excelente: "--status-good",
  boa: "--status-good",
  moderada: "--status-warning",
  baixa: "--status-critical",
}

export default function DurabilityPanel({ activityId }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!activityId) return undefined
    let cancelled = false

    api.training
      .durability(activityId)
      .then((result) => !cancelled && setData(result))
      .catch(() => !cancelled && setData(null))

    return () => {
      cancelled = true
    }
  }, [activityId])

  if (!data) return null

  if (!data.is_conclusive) {
    return (
      <ChartFrame
        title="Durabilidade"
        subtitle={
          `${num(data.total_kj, 0)} kJ de trabalho — insuficiente para comparar ` +
          `os dois lados do corte de ${num(data.kj_threshold, 0)} kJ`
        }
      />
    )
  }

  return (
    <ChartFrame
      title="Durabilidade"
      subtitle={
        `${num(data.total_kj, 0)} kJ no total · corte aos ` +
        `${num(data.kj_threshold, 0)} kJ (${shortDuration(data.split_time_s)})`
      }
      action={
        <span
          style={{
            fontSize: "var(--fs-small)",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            color: "var(--text-secondary)",
          }}
        >
          <span
            className="viz-swatch"
            style={{
              background: `var(${VERDICT_TOKEN[data.verdict] || "--text-muted"})`,
              borderRadius: "50%",
            }}
          />
          {data.verdict}
        </span>
      }
    >
      <div style={{ display: "grid", gap: "var(--space-3)" }}>
        {data.ef_change_pct !== null && (
          <p style={{ margin: 0, fontSize: "var(--fs-small)" }}>
            Efficiency Factor caiu{" "}
            <strong>{num(Math.abs(data.ef_change_pct), 1)}%</strong> depois do corte
            <span className="muted">
              {" "}
              ({num(data.ef_before, 3)} → {num(data.ef_after, 3)})
            </span>
          </p>
        )}

        {data.points.length > 0 && (
          <table className="tabular" style={{ width: "100%", fontSize: "var(--fs-small)" }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--text-muted)" }}>
                <th style={{ fontWeight: 500 }}>Duração</th>
                <th style={{ fontWeight: 500, textAlign: "right" }}>Antes</th>
                <th style={{ fontWeight: 500, textAlign: "right" }}>Depois</th>
                <th style={{ fontWeight: 500, textAlign: "right" }}>Variação</th>
              </tr>
            </thead>
            <tbody>
              {data.points.map((point) => (
                <tr key={point.duration_s} style={{ borderTop: "1px solid var(--border)" }}>
                  <td>{shortDuration(point.duration_s)}</td>
                  <td style={{ textAlign: "right" }}>{watts(point.before_w)}</td>
                  <td style={{ textAlign: "right" }}>{watts(point.after_w)}</td>
                  <td
                    style={{
                      textAlign: "right",
                      color:
                        point.change_pct < -8
                          ? "var(--status-critical)"
                          : "var(--text-secondary)",
                    }}
                  >
                    {point.change_pct > 0 ? "+" : ""}
                    {num(point.change_pct, 1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </ChartFrame>
  )
}
