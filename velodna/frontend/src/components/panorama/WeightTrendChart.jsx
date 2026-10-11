/*
 * Tendência de peso no ciclo, contra a meta.
 *
 * É o peso suavizado do MacroFactor, não a pesagem do dia: a balança oscila um
 * quilo de um dia para o outro por água e intestino, e é a tendência que diz se
 * o balanço das semanas ao lado está fazendo efeito. Um ponto por semana (o do
 * último dia dela). Uma série só: dispensa legenda, o título a nomeia.
 */
import {
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
import { dayMonth, num } from "../../lib/format"

const TOKENS = ["--series-3", "--gridline", "--axis", "--text-muted", "--text-tertiary"]

const kg = (value) => (value == null ? "—" : `${num(value, 1)} kg`)

export default function WeightTrendChart({ nutrition, goalKg }) {
  const colors = useCssVars(TOKENS)
  const { weeks, summary } = nutrition
  const start = summary.trend_weight_start_kg
  const end = summary.trend_weight_end_kg
  const delta = start != null && end != null ? end - start : null

  return (
    <ChartFrame
      title="Tendência de peso"
      subtitle={
        delta == null
          ? "Peso suavizado, por semana"
          : `${delta > 0 ? "+" : delta < 0 ? "−" : ""}${num(Math.abs(delta), 1)} kg no ciclo · de ${num(start, 1)} para ${num(end, 1)} kg`
      }
      table={{
        columns: [
          {
            key: "week_start",
            label: "Semana",
            format: (v, r) => `${dayMonth(v)} – ${dayMonth(r.week_end)}`,
          },
          { key: "trend_weight_kg", label: "Tendência", num: true, format: kg },
        ],
        rows: weeks,
      }}
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={weeks} margin={{ top: 16, right: 8, bottom: 0, left: -14 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="week_start"
            tickFormatter={dayMonth}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            interval="preserveStartEnd"
            minTickGap={8}
          />
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            domain={[
              (min) => Math.floor(Math.min(min, goalKg ?? min) - 0.5),
              (max) => Math.ceil(Math.max(max, goalKg ?? max) + 0.5),
            ]}
            allowDecimals={false}
          />
          <Tooltip
            content={<VizTooltip formatValue={(v) => kg(v)} />}
            labelFormatter={(v) => `semana de ${dayMonth(v)}`}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
          />
          <Line
            dataKey="trend_weight_kg"
            name="Tendência"
            stroke={colors["--series-3"]}
            strokeWidth={2}
            dot={weeks.length <= 26 ? { r: 2.5, fill: colors["--series-3"] } : false}
            activeDot={{ r: 4 }}
            connectNulls
            isAnimationActive={false}
          />
          {goalKg && (
            <ReferenceLine
              y={goalKg}
              stroke={colors["--text-tertiary"]}
              strokeDasharray="4 4"
              label={{
                value: `meta ${num(goalKg, 1)} kg`,
                position: "insideBottomLeft",
                fill: colors["--text-tertiary"],
                fontSize: 11,
              }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
