/*
 * Ingestão contra gasto, por semana — as duas metades da conta do peso.
 *
 * As barras são a média de calorias dos dias com comida registrada; a linha é
 * o gasto total que o MacroFactor estima. Mesma unidade (kcal por dia), então
 * cabem num eixo só, e a distância entre barra e linha é o balanço.
 *
 * O registro é esparso, e o gráfico não esconde isso: semana com menos dias do
 * que o mínimo sai em tom claro — a média de um ou dois dias não descreve a
 * semana — e semana sem registro fica sem barra, em vez de virar zero. Dia de
 * registro parcial já chega fora das médias (`analytics.nutrition`). O gasto
 * existe todo dia, por isso a linha é contínua.
 */
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import { useCssVars } from "../../lib/useCssVar"
import { dayMonth, num } from "../../lib/format"

const TOKENS = [
  "--series-1",
  "--seq-250",
  "--series-2",
  "--gridline",
  "--axis",
  "--text-muted",
  "--surface-1",
]

const kcal = (value) => (value == null ? "—" : `${num(value, 0)} kcal`)
const signed = (value) =>
  value == null ? "—" : `${value > 0 ? "+" : value < 0 ? "−" : ""}${num(Math.abs(value), 0)} kcal`

function EnergyTooltip({ active, payload, minDays }) {
  if (!active || !payload?.length) return null
  const week = payload[0].payload
  const rowsToShow = [
    ["Ingestão média", kcal(week.avg_calories_kcal)],
    ["Gasto estimado", kcal(week.avg_expenditure_kcal)],
    ["Balanço", signed(week.avg_balance_kcal)],
    [
      "Proteína",
      week.avg_protein_g == null
        ? "—"
        : `${num(week.avg_protein_g, 0)} g${week.target_protein_g ? ` de ${num(week.target_protein_g, 0)} g` : ""}`,
    ],
  ]
  return (
    <div className="viz-tooltip">
      <div className="viz-tooltip-title">
        {dayMonth(week.week_start)} – {dayMonth(week.week_end)}
      </div>
      {rowsToShow.map(([label, value]) => (
        <div className="viz-tooltip-row" key={label}>
          <span className="viz-tooltip-label">{label}</span>
          <span className="viz-tooltip-value">{value}</span>
        </div>
      ))}
      <div className="viz-tooltip-row" style={{ marginTop: 4 }}>
        <span className="viz-tooltip-label">Dias registrados</span>
        <span className="viz-tooltip-value">
          {week.days_logged} de 7{week.days_logged > 0 && week.days_logged < minDays ? " · poucos" : ""}
        </span>
      </div>
    </div>
  )
}

export default function EnergyChart({ nutrition }) {
  const colors = useCssVars(TOKENS)
  const { weeks, summary, min_days_per_week: minDays } = nutrition

  const max = Math.max(
    ...weeks.map((w) => Math.max(w.avg_calories_kcal || 0, w.avg_expenditure_kcal || 0)),
    1,
  )
  const top = Math.ceil((max * 1.08) / 500) * 500

  return (
    <ChartFrame
      title="Ingestão × gasto"
      subtitle={
        summary.avg_balance_kcal == null
          ? "Média diária por semana · sem dias registrados no ciclo"
          : `Média diária por semana · balanço de ${signed(summary.avg_balance_kcal)}/dia nos dias registrados`
      }
      series={[
        { label: `Ingestão (${minDays}+ dias na semana)`, color: colors["--series-1"] },
        { label: "Ingestão (poucos dias)", color: colors["--seq-250"] },
        { label: "Gasto estimado", color: colors["--series-2"] },
      ]}
      table={{
        columns: [
          {
            key: "week_start",
            label: "Semana",
            format: (v, r) => `${dayMonth(v)} – ${dayMonth(r.week_end)}`,
          },
          { key: "days_logged", label: "Dias", num: true },
          { key: "avg_calories_kcal", label: "Ingestão", num: true, format: kcal },
          { key: "avg_expenditure_kcal", label: "Gasto", num: true, format: kcal },
          { key: "avg_balance_kcal", label: "Balanço", num: true, format: signed },
          {
            key: "avg_protein_g",
            label: "Proteína",
            num: true,
            format: (v) => (v == null ? "—" : `${num(v, 0)} g`),
          },
        ],
        rows: weeks,
      }}
    >
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={weeks} margin={{ top: 12, right: 8, bottom: 0, left: -6 }}>
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
            domain={[0, top]}
            ticks={Array.from({ length: top / 500 + 1 }, (_, i) => i * 500)}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            allowDecimals={false}
            tickFormatter={(v) => num(v, 0)}
          />
          <Tooltip
            content={<EnergyTooltip minDays={minDays} />}
            cursor={{ fill: colors["--gridline"], opacity: 0.5 }}
          />
          <Bar
            dataKey="avg_calories_kcal"
            name="Ingestão"
            maxBarSize={36}
            radius={[4, 4, 0, 0]}
            stroke={colors["--surface-1"]}
            strokeWidth={1.5}
            isAnimationActive={false}
          >
            {weeks.map((week) => (
              <Cell
                key={week.week_start}
                fill={week.reliable ? colors["--series-1"] : colors["--seq-250"]}
              />
            ))}
          </Bar>
          <Line
            dataKey="avg_expenditure_kcal"
            name="Gasto estimado"
            stroke={colors["--series-2"]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
