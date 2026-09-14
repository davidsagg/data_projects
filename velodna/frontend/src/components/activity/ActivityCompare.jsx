/*
 * Comparação entre atividades (US-04).
 *
 * Três leituras que respondem perguntas diferentes:
 *
 *  - **Tabela de métricas**: números lado a lado, com a diferença explícita.
 *    Comparar mentalmente duas colunas é trabalho que o software deve fazer.
 *  - **Curvas de potência sobrepostas**: onde um treino foi mais forte que o
 *    outro, duração a duração.
 *  - **Distribuição em zonas**: barras agrupadas por zona, não empilhadas —
 *    empilhar somaria treinos diferentes, que não formam um todo.
 */
import { useMemo } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { useCssVars } from "../../lib/useCssVar"
import { duration, fullDate, km, num, shortDuration } from "../../lib/format"

const SERIES_TOKENS = ["--series-1", "--series-2", "--series-3"]
const TOKENS = [...SERIES_TOKENS, "--gridline", "--axis", "--text-muted"]
const TICKS = [1, 5, 15, 60, 300, 720, 1200, 3600, 7200]

const METRICS = [
  { key: "distance_m", label: "Distância", format: (v) => km(v) },
  { key: "elapsed_time_s", label: "Duração", format: duration },
  { key: "moving_time_s", label: "Em movimento", format: duration },
  { key: "elevation_gain_m", label: "Elevação", format: (v) => `${num(v)} m` },
  { key: "avg_power_w", label: "Potência média", format: (v) => `${num(v)} W` },
  { key: "normalized_power_w", label: "NP", format: (v) => `${num(v)} W` },
  { key: "intensity_factor", label: "IF", format: (v) => num(v, 2) },
  { key: "variability_index", label: "VI", format: (v) => num(v, 2) },
  { key: "tss", label: "TSS", format: (v) => num(v, 0) },
  { key: "avg_hr_bpm", label: "FC média", format: (v) => `${num(v)} bpm` },
  { key: "efficiency_factor", label: "Efficiency Factor", format: (v) => num(v, 3) },
  { key: "decoupling_pct", label: "Decoupling", format: (v) => `${num(v, 1)}%` },
]

export default function ActivityCompare({ activities, curves, zones }) {
  const colors = useCssVars(TOKENS)

  const series = activities.map((a, i) => ({
    label: fullDate(a.started_at),
    color: colors[SERIES_TOKENS[i]],
  }))

  const curveRows = useMemo(() => {
    const byDuration = new Map()
    activities.forEach((activity, index) => {
      ;(curves[activity.id] || []).forEach((point) => {
        const row = byDuration.get(point.duration_s) || {
          duration_s: point.duration_s,
        }
        row[`a${index}`] = point.power_w
        byDuration.set(point.duration_s, row)
      })
    })
    return [...byDuration.values()].sort((a, b) => a.duration_s - b.duration_s)
  }, [activities, curves])

  const zoneRows = useMemo(() => {
    const byZone = new Map()
    activities.forEach((activity, index) => {
      const distribution = zones[activity.id]?.power || []
      distribution.forEach((z) => {
        const row = byZone.get(z.zone) || { zone: z.zone, label: z.label }
        row[`a${index}`] = z.pct
        byZone.set(z.zone, row)
      })
    })
    return [...byZone.values()]
  }, [activities, zones])

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      <section className="card">
        <h2 className="card-title">Comparação</h2>
        <p className="card-subtitle">
          {activities.length === 2
            ? "Diferença calculada da segunda para a primeira atividade"
            : `${activities.length} atividades selecionadas`}
        </p>
        <div className="scroll-x">
          <table className="data">
            <thead>
              <tr>
                <th>Métrica</th>
                {activities.map((a, i) => (
                  <th key={a.id}>
                    <span
                      className="viz-swatch"
                      style={{
                        background: colors[SERIES_TOKENS[i]],
                        display: "inline-block",
                        marginRight: 6,
                      }}
                    />
                    {fullDate(a.started_at)}
                  </th>
                ))}
                {activities.length === 2 && <th>Δ</th>}
              </tr>
            </thead>
            <tbody>
              {METRICS.map((metric) => {
                const values = activities.map((a) => a[metric.key])
                const hasAny = values.some((v) => v !== null && v !== undefined)
                if (!hasAny) return null

                const delta =
                  activities.length === 2 &&
                  values[0] !== null &&
                  values[1] !== null &&
                  values[0] !== undefined &&
                  values[1] !== undefined
                    ? values[1] - values[0]
                    : null

                return (
                  <tr key={metric.key}>
                    <td>{metric.label}</td>
                    {values.map((v, i) => (
                      <td key={i}>
                        {v === null || v === undefined ? "—" : metric.format(v)}
                      </td>
                    ))}
                    {activities.length === 2 && (
                      <td
                        style={{
                          color:
                            delta === null
                              ? "var(--text-muted)"
                              : "var(--text-primary)",
                          fontWeight: 600,
                        }}
                      >
                        {delta === null
                          ? "—"
                          : `${delta >= 0 ? "+" : ""}${metric.format(delta)}`}
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {curveRows.length > 0 && (
        <ChartFrame
          title="Curvas de potência sobrepostas"
          subtitle="Melhor esforço por duração em cada atividade"
          series={series}
        >
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={curveRows} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
              <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
              <XAxis
                dataKey="duration_s"
                scale="log"
                domain={["dataMin", "dataMax"]}
                type="number"
                ticks={TICKS}
                tickFormatter={shortDuration}
                tick={{ fill: colors["--text-muted"], fontSize: 11 }}
                stroke={colors["--axis"]}
              />
              <YAxis
                tick={{ fill: colors["--text-muted"], fontSize: 11 }}
                stroke={colors["--axis"]}
                width={54}
              />
              <Tooltip
                content={<VizTooltip formatValue={(v) => `${num(v)} W`} />}
                labelFormatter={(v) => `Esforço de ${shortDuration(v)}`}
                cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
              />
              {activities.map((a, i) => (
                <Line
                  key={a.id}
                  type="monotone"
                  dataKey={`a${i}`}
                  name={fullDate(a.started_at)}
                  stroke={colors[SERIES_TOKENS[i]]}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartFrame>
      )}

      {zoneRows.length > 0 && (
        <ChartFrame
          title="Tempo em zona de potência"
          subtitle="Percentual do treino em cada zona"
          series={series}
        >
          <ResponsiveContainer width="100%" height={220}>
            {/* Barras agrupadas, não empilhadas: são treinos distintos e a
                soma entre eles não significa nada. */}
            <BarChart data={zoneRows} margin={{ top: 4, right: 8, bottom: 0, left: -6 }} barGap={2}>
              <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
              <XAxis
                dataKey="zone"
                tick={{ fill: colors["--text-muted"], fontSize: 11 }}
                stroke={colors["--axis"]}
              />
              <YAxis
                tick={{ fill: colors["--text-muted"], fontSize: 11 }}
                stroke={colors["--axis"]}
                width={44}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                content={<VizTooltip formatValue={(v) => `${num(v, 1)}%`} />}
                labelFormatter={(zone) =>
                  zoneRows.find((r) => r.zone === zone)?.label || zone
                }
                cursor={{ fill: colors["--gridline"] }}
              />
              {activities.map((a, i) => (
                <Bar
                  key={a.id}
                  dataKey={`a${i}`}
                  name={fullDate(a.started_at)}
                  fill={colors[SERIES_TOKENS[i]]}
                  radius={[2, 2, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>
      )}
    </div>
  )
}
