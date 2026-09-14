/*
 * Eficiência aeróbica ao longo do tempo.
 *
 * EF (potência normalizada por batimento) sobe quando a base aeróbica melhora,
 * mesmo que o FTP não mude. Decoupling mede a deriva cardíaca dentro do treino:
 * acima de ~5% a resistência não sustenta a duração do esforço.
 *
 * Cada ponto é um treino, então a média móvel existe para dar a tendência — a
 * dispersão entre sessões é grande demais para se ler ponto a ponto.
 */
import { useMemo, useState } from "react"
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { useCssVars } from "../../lib/useCssVar"
import { fullDate, monthYear, num } from "../../lib/format"

const METRICS = {
  efficiency_factor: {
    label: "Efficiency Factor",
    subtitle: "Potência normalizada por batimento — mais alto é melhor",
    digits: 3,
    reference: null,
  },
  decoupling_pct: {
    label: "Decoupling",
    subtitle: "Deriva cardíaca entre as metades do treino — abaixo de 5% é bom",
    digits: 1,
    reference: 5,
  },
}

const TOKENS = [
  "--series-1",
  "--series-2",
  "--status-warning",
  "--gridline",
  "--axis",
  "--text-muted",
]

/** Média móvel simples, para dar tendência a uma nuvem dispersa. */
function rollingMean(rows, key, window = 10) {
  return rows.map((row, index) => {
    const slice = rows
      .slice(Math.max(0, index - window + 1), index + 1)
      .map((r) => r[key])
      .filter((v) => v !== null && v !== undefined)
    return {
      ...row,
      trend: slice.length
        ? slice.reduce((a, b) => a + b, 0) / slice.length
        : null,
    }
  })
}

export default function EfficiencyChart({ activities }) {
  const [metric, setMetric] = useState("efficiency_factor")
  const colors = useCssVars(TOKENS)
  const config = METRICS[metric]

  const rows = useMemo(() => {
    if (!activities?.length) return []
    const filtered = activities
      .filter((a) => a[metric] !== null && a[metric] !== undefined)
      .map((a) => ({
        date: a.date,
        value: a[metric],
        tss: a.tss,
        intensity_factor: a.intensity_factor,
      }))
    return rollingMean(filtered, "value")
  }, [activities, metric])

  if (!rows.length) {
    return (
      <ChartFrame title="Eficiência aeróbica">
        <p className="muted">Sem atividades com potência e FC.</p>
      </ChartFrame>
    )
  }

  const latestTrend = rows[rows.length - 1]?.trend
  const series = [
    { label: "Por treino", color: colors["--series-1"] },
    { label: "Tendência (10 treinos)", color: colors["--series-2"] },
  ]

  return (
    <ChartFrame
      title="Eficiência aeróbica"
      subtitle={`${config.subtitle} · tendência atual ${num(latestTrend, config.digits)}`}
      series={series}
      action={
        <div className="segmented" role="group" aria-label="Métrica">
          {Object.entries(METRICS).map(([key, cfg]) => (
            <button
              key={key}
              aria-pressed={key === metric}
              onClick={() => setMetric(key)}
            >
              {cfg.label}
            </button>
          ))}
        </div>
      }
    >
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={monthYear}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            minTickGap={72}
          />
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            width={58}
            tickFormatter={(v) => num(v, config.digits)}
          />
          {config.reference !== null && (
            <ReferenceLine
              y={config.reference}
              stroke={colors["--status-warning"]}
              strokeDasharray="4 3"
              label={{
                value: `${config.reference}%`,
                position: "right",
                fill: colors["--text-muted"],
                fontSize: 10,
              }}
            />
          )}
          <Tooltip
            content={
              <VizTooltip
                formatValue={(v) => num(v, config.digits)}
              />
            }
            labelFormatter={fullDate}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
          />
          <Scatter
            dataKey="value"
            name="Por treino"
            fill={colors["--series-1"]}
            fillOpacity={0.55}
            shape="circle"
            legendType="circle"
            /* Marcador com área suficiente para leitura e para o hover. */
            r={4}
          />
          <Line
            type="monotone"
            dataKey="trend"
            name="Tendência (10 treinos)"
            stroke={colors["--series-2"]}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
