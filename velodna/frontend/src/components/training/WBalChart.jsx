/*
 * W'bal — a reserva anaeróbica ao longo da atividade.
 *
 * Área, não linha: o que se lê aqui é "quanto ainda resta no tanque", uma
 * quantidade que se esgota, e a área preenchida diz isso de imediato. A linha
 * de 50% marca onde cada mergulho passa a custar caro — é dela que sai a
 * contagem de fósforos queimados.
 */
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { useCssVars } from "../../lib/useCssVar"
import { duration, num } from "../../lib/format"

const TOKENS = [
  "--series-1",
  "--status-warning",
  "--gridline",
  "--axis",
  "--text-muted",
]

export default function WBalChart({ data, elapsedTimeS }) {
  const colors = useCssVars(TOKENS)

  if (!data?.balance?.length) return null

  // A série vem decimada pela API; cada ponto representa uma fatia igual do
  // tempo total, então o eixo é reconstruído a partir da duração.
  const step = (elapsedTimeS || data.balance.length) / data.balance.length
  const rows = data.balance.map((joules, index) => ({
    t: Math.round(index * step),
    kj: Number((joules / 1000).toFixed(2)),
  }))

  const halfKj = data.w_prime_j / 2000

  return (
    <ChartFrame
      title="W'bal — reserva anaeróbica"
      subtitle={
        `CP ${num(data.cp_w, 0)} W · W' ${num(data.w_prime_j / 1000, 1)} kJ · ` +
        `τ ${num(data.tau_s, 0)} s`
      }
      action={
        <span className="tabular muted" style={{ fontSize: "var(--fs-small)" }}>
          {num(data.depletion_pct, 1)}% consumido no fundo ·{" "}
          {data.matches_burned} {data.matches_burned === 1 ? "fósforo" : "fósforos"}
        </span>
      }
    >
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: -12 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            domain={[0, "dataMax"]}
            tickFormatter={duration}
            stroke={colors["--axis"]}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            tickLine={false}
          />
          <YAxis
            stroke={colors["--axis"]}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            unit=" kJ"
          />
          <ReferenceLine
            y={halfKj}
            stroke={colors["--status-warning"]}
            strokeDasharray="4 4"
            label={{
              value: "50% da reserva",
              position: "insideTopRight",
              fill: colors["--text-muted"],
              fontSize: 11,
            }}
          />
          <Tooltip
            content={
              <VizTooltip formatValue={(value) => `${num(value, 2)} kJ`} />
            }
            labelFormatter={(value) => duration(value)}
          />
          <Area
            dataKey="kj"
            name="W' restante"
            stroke={colors["--series-1"]}
            fill={colors["--series-1"]}
            fillOpacity={0.18}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
