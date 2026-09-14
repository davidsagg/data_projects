/*
 * Tendência de HRV com faixa de referência pessoal.
 *
 * O valor absoluto de HRV não significa quase nada entre pessoas — 30 ms pode
 * ser excelente para um e ruim para outro. O que informa é o desvio em relação
 * à **própria** linha de base. Por isso a faixa sombreada (média de 60 dias ±
 * um desvio-padrão) é o elemento principal, e o ponto diário só importa por
 * onde cai dentro dela.
 *
 * A média de 7 dias existe porque o HRV diário é ruidoso: uma noite ruim
 * derruba o valor sem que nada tenha mudado na adaptação ao treino.
 */
import { useMemo, useState } from "react"
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
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

const BASELINE_WINDOW = 60
const SMOOTHING_WINDOW = 7

const TOKENS = [
  "--series-1",
  "--series-2",
  "--gridline",
  "--axis",
  "--text-muted",
]

/** Média e desvio-padrão de uma janela retrospectiva, por ponto da série. */
function withBaseline(rows, key) {
  return rows.map((row, index) => {
    const window = rows
      .slice(Math.max(0, index - BASELINE_WINDOW + 1), index + 1)
      .map((r) => r[key])
      .filter((v) => v !== null && v !== undefined)

    const smooth = rows
      .slice(Math.max(0, index - SMOOTHING_WINDOW + 1), index + 1)
      .map((r) => r[key])
      .filter((v) => v !== null && v !== undefined)

    if (!window.length) return { ...row, baseline: null, band: null, smoothed: null }

    const mean = window.reduce((a, b) => a + b, 0) / window.length
    const variance =
      window.reduce((acc, v) => acc + (v - mean) ** 2, 0) / window.length
    const sd = Math.sqrt(variance)

    return {
      ...row,
      baseline: mean,
      // Recharts desenha a faixa como área empilhada: base e altura.
      bandLow: mean - sd,
      bandHeight: 2 * sd,
      smoothed: smooth.length
        ? smooth.reduce((a, b) => a + b, 0) / smooth.length
        : null,
    }
  })
}

export default function HRVChart({ health }) {
  const [range, setRange] = useState(RANGES[1])
  const colors = useCssVars(TOKENS)

  const rows = useMemo(() => {
    if (!health?.length) return []
    // A API devolve do mais recente para o mais antigo.
    const chronological = [...health]
      .filter((h) => h.hrv_rmssd_ms !== null && h.hrv_rmssd_ms !== undefined)
      .sort((a, b) => (a.date < b.date ? -1 : 1))
    return withBaseline(chronological, "hrv_rmssd_ms").slice(-range.days)
  }, [health, range])

  if (!rows.length) {
    return (
      <ChartFrame title="HRV">
        <p className="muted">Sem dados de HRV.</p>
      </ChartFrame>
    )
  }

  const latest = rows[rows.length - 1]
  const deviation =
    latest.baseline && latest.hrv_rmssd_ms
      ? latest.hrv_rmssd_ms - latest.baseline
      : null

  const series = [
    { label: "HRV diário", color: colors["--series-1"] },
    { label: "Média de 7 dias", color: colors["--series-2"] },
  ]

  const spanDays =
    (new Date(latest.date) - new Date(rows[0].date)) / 86400000

  const visible = rows.flatMap((r) =>
    [r.hrv_rmssd_ms, r.bandLow, r.bandLow + r.bandHeight].filter(
      (v) => v !== null && v !== undefined,
    ),
  )
  const domain = [
    Math.max(0, Math.floor((Math.min(...visible) - 5) / 5) * 5),
    Math.ceil((Math.max(...visible) + 5) / 5) * 5,
  ]

  return (
    <ChartFrame
      title="Variabilidade da frequência cardíaca"
      subtitle={
        deviation !== null
          ? `Hoje ${num(latest.hrv_rmssd_ms)} ms · linha de base ${num(latest.baseline)} ms · ${deviation >= 0 ? "+" : ""}${num(deviation, 1)} ms`
          : "Desvio em relação à linha de base pessoal"
      }
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
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={axisDateFormatter(spanDays)}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            minTickGap={72}
          />
          {/* Domínio explícito: as chaves auxiliares da faixa (`bandLow` e
              `bandHeight`) entrariam no cálculo automático e puxariam o eixo
              para valores de HRV que não existem, inclusive negativos. */}
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            width={44}
            domain={domain}
            allowDataOverflow
          />
          <Tooltip
            content={
              <VizTooltip
                formatValue={(v) => `${num(v, 1)} ms`}
              />
            }
            labelFormatter={fullDate}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
          />
          {/* Faixa de normalidade: base invisível + altura sombreada. */}
          <Area
            dataKey="bandLow"
            stackId="band"
            stroke="none"
            fill="none"
            legendType="none"
            tooltipType="none"
            isAnimationActive={false}
          />
          <Area
            dataKey="bandHeight"
            stackId="band"
            name="Faixa habitual"
            stroke="none"
            fill={colors["--series-1"]}
            fillOpacity={0.12}
            isAnimationActive={false}
          />
          <Scatter
            dataKey="hrv_rmssd_ms"
            name="HRV diário"
            fill={colors["--series-1"]}
            fillOpacity={0.6}
            shape="circle"
            legendType="circle"
            /* Marcador com área suficiente para leitura e para o hover. */
            r={4}
          />
          <Line
            type="monotone"
            dataKey="smoothed"
            name="Média de 7 dias"
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
