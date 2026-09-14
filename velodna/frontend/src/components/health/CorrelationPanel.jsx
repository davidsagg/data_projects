/*
 * Correlação entre recuperação e performance (US-12).
 *
 * A tabela vem antes do gráfico de propósito: o que decide se um achado vale
 * algo é o trio r, n e p — não a aparência da nuvem de pontos. O gráfico só
 * aparece para o par selecionado, e serve para ver se a relação é linear ou se
 * um punhado de pontos extremos está carregando o coeficiente.
 *
 * Achados não significativos não são escondidos: saber que não há relação
 * detectável entre sono e potência é informação, não ausência dela.
 */
import { useEffect, useState } from "react"
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { api } from "../../lib/api"
import { useCssVars } from "../../lib/useCssVar"
import { fullDate, num } from "../../lib/format"

const TOKENS = ["--series-1", "--gridline", "--axis", "--text-muted"]

export default function CorrelationPanel() {
  const [data, setData] = useState(null)
  const [selected, setSelected] = useState(0)
  const colors = useCssVars(TOKENS)

  useEffect(() => {
    api.health.sleepCorrelation().then(setData).catch(() => setData(null))
  }, [])

  if (!data) return null
  const { correlations } = data
  if (!correlations?.length) {
    return (
      <section className="card">
        <h2 className="card-title">Recuperação e performance</h2>
        <p className="muted">
          Dados insuficientes — são necessários pelo menos 7 dias com sono e
          treino no mesmo dia.
        </p>
      </section>
    )
  }

  const current = correlations[selected] || correlations[0]

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      <section className="card">
        <h2 className="card-title">Recuperação e performance</h2>
        <p className="card-subtitle">
          Janela de {data.window_days} dias · clique numa linha para ver a
          dispersão
        </p>

        <div className="scroll-x">
          <table className="data">
            <thead>
              <tr>
                <th>Recuperação</th>
                <th>Performance</th>
                <th>r</th>
                <th>n</th>
                <th>p</th>
                <th>Leitura</th>
              </tr>
            </thead>
            <tbody>
              {correlations.map((c, index) => (
                <tr
                  key={`${c.x_key}-${c.y_key}`}
                  onClick={() => setSelected(index)}
                  style={{
                    cursor: "pointer",
                    background:
                      index === selected ? "var(--surface-sunken)" : undefined,
                  }}
                >
                  <td>{c.x_label}</td>
                  <td>{c.y_label}</td>
                  <td style={{ fontWeight: 600 }}>{num(c.r, 3)}</td>
                  <td>{c.n}</td>
                  <td>{c.p_value < 0.001 ? "<0,001" : num(c.p_value, 3)}</td>
                  <td style={{ textAlign: "left" }}>
                    {/* Significância marcada por texto, não por cor. */}
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: "var(--fs-micro)",
                        color: c.significant
                          ? "var(--status-good)"
                          : "var(--text-muted)",
                        marginRight: 6,
                      }}
                    >
                      {c.significant ? "SIGNIFICATIVO" : "não significativo"}
                    </span>
                    {c.significant && `${c.strength} · ${c.direction}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p
          className="card-subtitle"
          style={{ marginTop: "var(--space-3)", marginBottom: 0 }}
        >
          Correlação não é causa. Dormir bem e render bem compartilham causas
          comuns — descanso, ausência de estresse, ausência de doença.
        </p>
      </section>

      <ChartFrame
        title={`${current.x_label} × ${current.y_label}`}
        subtitle={current.interpretation}
      >
        <ResponsiveContainer width="100%" height={280}>
          <ScatterChart
            data={current.points}
            margin={{ top: 8, right: 12, bottom: 12, left: -6 }}
          >
            <CartesianGrid stroke={colors["--gridline"]} />
            <XAxis
              type="number"
              dataKey="x"
              name={current.x_label}
              tick={{ fill: colors["--text-muted"], fontSize: 11 }}
              stroke={colors["--axis"]}
              domain={[
                (min) => Math.floor(min - Math.abs(min) * 0.05 - 0.5),
                (max) => Math.ceil(max + Math.abs(max) * 0.05 + 0.5),
              ]}
              label={{
                value: current.x_label,
                position: "insideBottom",
                offset: -6,
                fill: colors["--text-muted"],
                fontSize: 11,
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name={current.y_label}
              tick={{ fill: colors["--text-muted"], fontSize: 11 }}
              stroke={colors["--axis"]}
              width={54}
              domain={[
                (min) => Math.floor(min - Math.abs(min) * 0.05 - 0.5),
                (max) => Math.ceil(max + Math.abs(max) * 0.05 + 0.5),
              ]}
            />
            <ZAxis range={[42, 42]} />
            <Tooltip
              content={
                <VizTooltip
                  formatValue={(v, key, row) =>
                    key === "x"
                      ? num(v, 1)
                      : `${num(v, 1)}${row?.date ? ` · ${fullDate(row.date)}` : ""}`
                  }
                />
              }
              cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
            />
            <Scatter
              name={current.y_label}
              fill={colors["--series-1"]}
              fillOpacity={0.55}
              shape="circle"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </ChartFrame>
    </div>
  )
}
