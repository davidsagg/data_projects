/*
 * Performance Management Chart — CTL, ATL e TSB ao longo do tempo.
 *
 * As três séries compartilham a mesma unidade (TSS), então cabem num só eixo.
 * A tentação de pôr o TSS diário como barras num segundo eixo é justamente o
 * erro mais comum em gráficos: duas escalas no mesmo painel fazem o leitor
 * comparar alturas que não são comparáveis. O TSS diário vive no próprio
 * gráfico, abaixo, compartilhando o eixo de tempo.
 */
import { useMemo, useState } from "react"
import {
  Area,
  Bar,
  BarChart,
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
import { useCssVars } from "../../lib/useCssVar"
import { axisDateFormatter, fullDate, num } from "../../lib/format"

const RANGES = [
  { label: "3m", days: 90 },
  { label: "6m", days: 180 },
  { label: "1a", days: 365 },
  { label: "Tudo", days: null },
]

const TOKENS = [
  "--series-1",
  "--series-2",
  "--series-3",
  "--gridline",
  "--axis",
  "--text-muted",
  "--surface-1",
]

export default function PMCChart({ data }) {
  const [range, setRange] = useState(RANGES[1])
  const colors = useCssVars(TOKENS)

  const rows = useMemo(() => {
    if (!data?.length) return []
    const sliced = range.days ? data.slice(-range.days) : data
    return sliced.map((d) => ({
      ...d,
      ctl: d.ctl ?? 0,
      atl: d.atl ?? 0,
      tsb: d.tsb ?? 0,
      daily_tss: d.daily_tss ?? 0,
    }))
  }, [data, range])

  if (!rows.length) {
    return (
      <ChartFrame title="Performance Management Chart">
        <p className="muted">Sem série de carga.</p>
      </ChartFrame>
    )
  }

  const series = [
    { label: "CTL · fitness", color: colors["--series-1"] },
    { label: "ATL · fadiga", color: colors["--series-2"] },
    { label: "TSB · forma", color: colors["--series-3"] },
  ]

  const last = rows[rows.length - 1]
  const spanDays = (new Date(last.date) - new Date(rows[0].date)) / 86400000
  const formatTick = axisDateFormatter(spanDays)

  return (
    <ChartFrame
      title="Performance Management Chart"
      subtitle={`CTL ${num(last.ctl, 1)} · ATL ${num(last.atl, 1)} · TSB ${num(last.tsb, 1)}`}
      series={series}
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
      <ResponsiveContainer width="100%" height={230}>
        <ComposedChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: -6 }}>
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
            width={50}
          />
          <ReferenceLine y={0} stroke={colors["--axis"]} />
          <Tooltip
            content={
              <VizTooltip formatValue={(v) => num(v, 1)} />
            }
            labelFormatter={fullDate}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
          />
          {/* TSB como área ajuda a ler o sinal (acima/abaixo de zero). */}
          <Area
            type="monotone"
            dataKey="tsb"
            name="TSB · forma"
            stroke={colors["--series-3"]}
            fill={colors["--series-3"]}
            fillOpacity={0.14}
            strokeWidth={1.5}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="ctl"
            name="CTL · fitness"
            stroke={colors["--series-1"]}
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="atl"
            name="ATL · fadiga"
            stroke={colors["--series-2"]}
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* TSS diário: mesma escala de tempo, painel próprio — nunca segundo eixo. */}
      <ResponsiveContainer width="100%" height={64}>
        <BarChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: -6 }}>
          <XAxis dataKey="date" hide />
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 10 }}
            stroke={colors["--axis"]}
            width={50}
          />
          <Tooltip
            content={<VizTooltip formatValue={(v) => num(v, 0)} />}
            labelFormatter={fullDate}
            cursor={{ fill: colors["--gridline"] }}
          />
          <Bar
            dataKey="daily_tss"
            name="TSS do dia"
            fill={colors["--series-1"]}
            fillOpacity={0.45}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
      <p className="card-subtitle" style={{ margin: "var(--space-1) 0 0" }}>
        TSS por dia
      </p>
    </ChartFrame>
  )
}
