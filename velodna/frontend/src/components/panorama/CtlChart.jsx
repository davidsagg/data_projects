/*
 * Condicionamento no ciclo — CTL diário, com os marcos por cima.
 *
 * Substitui o "esforço relativo" do painel de referência: o relative effort do
 * Strava é uma métrica fechada, baseada só em FC. O CTL é a média ponderada de
 * 42 dias do TSS que o próprio VeloDNA calcula — de potência quando há medidor,
 * de FC calibrada quando não há. Uma série só: dispensa legenda, o título a nomeia.
 */
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { milestoneLines } from "../viz/milestoneLines"
import { useCssVars } from "../../lib/useCssVar"
import { dayMonth, fullDate, num } from "../../lib/format"

const TOKENS = ["--ctl", "--gridline", "--axis", "--text-muted", "--text-tertiary"]

export default function CtlChart({ series, milestones, goalCtl }) {
  const colors = useCssVars(TOKENS)
  if (!series?.length) return null

  const first = series.find((p) => p.ctl != null)
  const last = [...series].reverse().find((p) => p.ctl != null)
  const delta = first && last ? last.ctl - first.ctl : null
  const dates = new Set(series.map((p) => p.date))

  return (
    <ChartFrame
      title="Condicionamento · CTL"
      subtitle={
        delta == null
          ? "Média de 42 dias do TSS"
          : `${delta >= 0 ? "+" : ""}${num(delta, 1)} no ciclo · de ${num(first.ctl, 0)} para ${num(last.ctl, 0)}`
      }
    >
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={series} margin={{ top: 16, right: 8, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="panoramaCtlFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors["--ctl"]} stopOpacity={0.22} />
              <stop offset="100%" stopColor={colors["--ctl"]} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={dayMonth}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            minTickGap={40}
          />
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            domain={[
              (min) => Math.max(0, Math.floor((Math.min(min, goalCtl ?? min) - 5) / 5) * 5),
              (max) => Math.ceil((Math.max(max, goalCtl ?? max) + 5) / 5) * 5,
            ]}
            allowDecimals={false}
          />
          <Tooltip
            content={<VizTooltip formatValue={(v) => num(v, 1)} />}
            labelFormatter={fullDate}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
          />
          <Area
            dataKey="ctl"
            stroke="none"
            fill="url(#panoramaCtlFill)"
            isAnimationActive={false}
            tooltipType="none"
          />
          <Line
            dataKey="ctl"
            name="CTL"
            stroke={colors["--ctl"]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
          {goalCtl && (
            <ReferenceLine
              y={goalCtl}
              stroke={colors["--text-tertiary"]}
              strokeDasharray="4 4"
              label={{
                value: `meta ${num(goalCtl, 0)}`,
                position: "insideTopLeft",
                fill: colors["--text-tertiary"],
                fontSize: 11,
              }}
            />
          )}
          {milestoneLines(milestones, dates, colors)}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
