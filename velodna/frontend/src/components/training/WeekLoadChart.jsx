/*
 * Carga por semana — TSS executado contra o planejado, semana a semana.
 *
 * Barras, porque a pergunta é de magnitude comparada entre períodos discretos:
 * a semana é uma unidade fechada, não um ponto numa série contínua. O planejado
 * entra como uma segunda barra ao lado, e não como segunda escala — duas
 * escalas no mesmo painel fariam comparar alturas incomparáveis.
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { useCssVars } from "../../lib/useCssVar"
import { dayMonth, num } from "../../lib/format"

const TOKENS = ["--series-1", "--series-2", "--gridline", "--axis", "--text-muted"]

export default function WeekLoadChart({ weeks }) {
  const colors = useCssVars(TOKENS)

  if (!weeks?.length) {
    return (
      <ChartFrame title="Carga por semana">
        <p className="muted">Sem semanas para exibir.</p>
      </ChartFrame>
    )
  }

  const rows = weeks.map((w) => ({
    week_start: w.week_start,
    executado: w.total_tss ?? 0,
    planejado: w.planned_tss ?? 0,
  }))

  const hasPlan = rows.some((r) => r.planejado > 0)

  const series = [
    { label: "Executado", color: colors["--series-1"] },
    ...(hasPlan ? [{ label: "Planejado", color: colors["--series-2"] }] : []),
  ]

  return (
    <ChartFrame
      title="Carga por semana"
      subtitle="TSS total de cada semana, de segunda a domingo"
      series={series}
    >
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: -12 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="week_start"
            tickFormatter={dayMonth}
            stroke={colors["--axis"]}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            tickLine={false}
          />
          <YAxis
            stroke={colors["--axis"]}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: colors["--gridline"], opacity: 0.4 }}
            content={
              <VizTooltip formatValue={(value) => `${num(value, 0)} TSS`} />
            }
            labelFormatter={(value) => `Semana de ${dayMonth(value)}`}
          />
          <Bar
            dataKey="executado"
            name="Executado"
            fill={colors["--series-1"]}
            radius={[4, 4, 0, 0]}
          />
          {hasPlan && (
            <Bar
              dataKey="planejado"
              name="Planejado"
              fill={colors["--series-2"]}
              radius={[4, 4, 0, 0]}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
