/*
 * Sono e frequência cardíaca de repouso.
 *
 * São duas grandezas de escalas incompatíveis (horas e bpm). Postas no mesmo
 * painel com dois eixos, o leitor compararia alturas que não têm relação — o
 * erro mais comum em dashboards. Aqui elas ficam em painéis empilhados que
 * compartilham o eixo de tempo, o que preserva a leitura de coincidência
 * temporal sem sugerir proporção entre as curvas.
 */
import { useMemo, useState } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { useCssVars } from "../../lib/useCssVar"
import { axisDateFormatter, fullDate, num } from "../../lib/format"

const RANGES = [
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "1a", days: 365 },
]

const TOKENS = [
  "--series-1",
  "--series-2",
  "--gridline",
  "--axis",
  "--text-muted",
]

/** Média simples de uma chave, ignorando valores ausentes. */
function mean(rows, key) {
  const values = rows.map((r) => r[key]).filter((v) => v !== null && v !== undefined)
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
}

export default function WellnessChart({ health }) {
  const [range, setRange] = useState(RANGES[0])
  const colors = useCssVars(TOKENS)

  const rows = useMemo(() => {
    if (!health?.length) return []
    return [...health]
      .sort((a, b) => (a.date < b.date ? -1 : 1))
      .slice(-range.days)
  }, [health, range])

  if (!rows.length) {
    return (
      <ChartFrame title="Sono e recuperação">
        <p className="muted">Sem dados de saúde.</p>
      </ChartFrame>
    )
  }

  const avgSleep = mean(rows, "sleep_hours")
  const avgResting = mean(rows, "resting_hr_bpm")
  const spanDays =
    (new Date(rows[rows.length - 1].date) - new Date(rows[0].date)) / 86400000
  const formatTick = axisDateFormatter(spanDays)

  return (
    <ChartFrame
      title="Sono e frequência cardíaca de repouso"
      subtitle={`Médias no período: ${num(avgSleep, 1)} h de sono · ${num(avgResting, 0)} bpm em repouso`}
      action={
        <div className="segmented" role="group" aria-label="Período">
          {RANGES.map((r) => (
            <button
              key={r.label}
              aria-pressed={r.label === range.label}
              onClick={() => setRange(r)}
            >
              {r.label}
            </button>
          ))}
        </div>
      }
    >
      <p className="card-subtitle" style={{ margin: 0 }}>
        Horas de sono
      </p>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis dataKey="date" hide />
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            width={44}
            domain={[0, (max) => Math.ceil(max + 1)]}
          />
          {avgSleep && (
            <ReferenceLine
              y={avgSleep}
              stroke={colors["--axis"]}
              strokeDasharray="3 3"
            />
          )}
          <Tooltip
            content={<VizTooltip formatValue={(v) => `${num(v, 1)} h`} />}
            labelFormatter={fullDate}
            cursor={{ fill: colors["--gridline"] }}
          />
          <Bar
            dataKey="sleep_hours"
            name="Sono"
            fill={colors["--series-1"]}
            fillOpacity={0.6}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>

      <p className="card-subtitle" style={{ margin: "var(--space-3) 0 0" }}>
        FC de repouso
      </p>
      <ResponsiveContainer width="100%" height={110}>
        <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatTick}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            minTickGap={72}
          />
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            width={44}
            domain={[
              (min) => Math.floor((min - 2) / 2) * 2,
              (max) => Math.ceil((max + 2) / 2) * 2,
            ]}
          />
          {avgResting && (
            <ReferenceLine
              y={avgResting}
              stroke={colors["--axis"]}
              strokeDasharray="3 3"
            />
          )}
          <Tooltip
            content={<VizTooltip formatValue={(v) => `${num(v)} bpm`} />}
            labelFormatter={fullDate}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
          />
          <Line
            type="monotone"
            dataKey="resting_hr_bpm"
            name="FC de repouso"
            stroke={colors["--series-2"]}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
