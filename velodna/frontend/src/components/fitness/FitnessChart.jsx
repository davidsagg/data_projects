/*
 * Performance Management Chart, com a camada de saúde.
 *
 * CTL, ATL e TSB dividem a unidade (TSS), então dividem o eixo. O HRV **não**
 * divide: sobrepô-lo ao mesmo painel exigiria um segundo eixo Y, que é o erro
 * mais comum em gráficos — o leitor compara alturas que não são comparáveis e o
 * cruzamento vira coincidência visual arbitrária.
 *
 * A spec pedia a sobreposição; a entrega é um painel empilhado com o mesmo eixo
 * X. O cruzamento saúde × treino que ela quer continua lá — é o alinhamento
 * temporal que produz a leitura, não a partilha do eixo vertical —, e é a mesma
 * solução da timeline da semana, o que mantém o vocabulário visual consistente.
 */
import { useMemo, useState } from "react"
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceArea,
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
import { axisDateFormatter, fullDate, num } from "../../lib/format"

const RANGES = [
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "180d", days: 180 },
  { label: "1a", days: 365 },
]

/* Faixas de TSB (Coggan/Friel). O rótulo acompanha a faixa na legenda de texto,
   então a informação não depende só da cor de fundo. */
const TSB_BANDS = [
  { from: 25, to: 60, token: "--text-tertiary", label: "destreinando" },
  { from: 5, to: 25, token: "--tsb-positive", label: "forma de prova" },
  { from: -10, to: 5, token: null, label: "equilíbrio" },
  { from: -30, to: -10, token: "--tsb-negative", label: "produtivo" },
  { from: -60, to: -30, token: "--atl", label: "risco" },
]

const TOKENS = [
  "--ctl",
  "--atl",
  "--tsb-positive",
  "--tsb-negative",
  "--hrv",
  "--gridline",
  "--axis",
  "--text-tertiary",
  "--surface-1",
]

export default function FitnessChart({ pmc, health, milestones }) {
  const [range, setRange] = useState(RANGES[1])
  const [showHealth, setShowHealth] = useState(true)
  const colors = useCssVars(TOKENS)

  const rows = useMemo(() => {
    if (!pmc?.length) return []
    const sliced = pmc.slice(-range.days)
    const hrvByDate = new Map(
      (health || []).filter((h) => h.hrv_rmssd_ms != null).map((h) => [h.date, h.hrv_rmssd_ms]),
    )
    return sliced.map((d) => ({
      date: d.date,
      ctl: d.ctl ?? 0,
      atl: d.atl ?? 0,
      tsb: d.tsb ?? 0,
      hrv: hrvByDate.get(d.date) ?? null,
    }))
  }, [pmc, health, range])

  if (!rows.length) {
    return (
      <ChartFrame title="Carga de treino">
        <p className="muted">Sem série de carga.</p>
      </ChartFrame>
    )
  }

  const hasHrv = rows.some((r) => r.hrv != null)
  const spanDays = rows.length
  const formatTick = axisDateFormatter(spanDays)

  const axis = {
    stroke: colors["--axis"],
    tick: { fill: colors["--text-tertiary"], fontSize: 11 },
    tickLine: false,
    axisLine: false,
  }

  return (
    <ChartFrame
      title="Carga de treino"
      subtitle="CTL é a forma acumulada, ATL a fadiga recente, TSB a diferença entre as duas"
      series={[
        { label: "CTL · forma", color: colors["--ctl"] },
        { label: "ATL · fadiga", color: colors["--atl"] },
        { label: "TSB · frescor", color: colors["--tsb-positive"] },
      ]}
      action={
        <div className="toolbar">
          {hasHrv && (
            <button
              className="segmented"
              aria-pressed={showHealth}
              onClick={() => setShowHealth((v) => !v)}
              style={{
                padding: "var(--space-2) var(--space-4)",
                fontSize: "var(--fs-small)",
                cursor: "pointer",
                color: showHealth ? "var(--text-primary)" : "var(--text-secondary)",
              }}
            >
              camada de HRV
            </button>
          )}
          <nav className="segmented" role="group" aria-label="Período">
            {RANGES.map((r) => (
              <button
                key={r.label}
                aria-pressed={range.label === r.label}
                onClick={() => setRange(r)}
              >
                {r.label}
              </button>
            ))}
          </nav>
        </div>
      }
    >
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
          <defs>
            <linearGradient id="ctlFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors["--ctl"]} stopOpacity={0.18} />
              <stop offset="100%" stopColor={colors["--ctl"]} stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid
            stroke={colors["--gridline"]}
            vertical={false}
            opacity={0.35}
          />
          <XAxis dataKey="date" tickFormatter={formatTick} {...axis} />
          <YAxis {...axis} />
          <Tooltip
            content={<VizTooltip formatValue={(v) => num(v, 1)} />}
            labelFormatter={fullDate}
          />

          <Area
            dataKey="ctl"
            name="CTL · forma"
            stroke={colors["--ctl"]}
            strokeWidth={2}
            fill="url(#ctlFill)"
            dot={false}
            isAnimationActive={false}
          />
          <Line
            dataKey="atl"
            name="ATL · fadiga"
            stroke={colors["--atl"]}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          {milestoneLines(milestones, new Set(rows.map((r) => r.date)), colors)}
        </ComposedChart>
      </ResponsiveContainer>

      {/* TSB em painel próprio: compartilha a unidade, mas a leitura é de sinal
          (acima ou abaixo de zero), que barras comunicam e linha não. */}
      <div style={{ marginTop: "var(--space-5)" }}>
        <span className="label">TSB · frescor</span>
        <ResponsiveContainer width="100%" height={120}>
          <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
            {TSB_BANDS.filter((b) => b.token).map((band) => (
              <ReferenceArea
                key={band.label}
                y1={band.from}
                y2={band.to}
                fill={colors[band.token]}
                fillOpacity={0.06}
                strokeOpacity={0}
              />
            ))}
            <CartesianGrid stroke={colors["--gridline"]} vertical={false} opacity={0.35} />
            <XAxis dataKey="date" tickFormatter={formatTick} {...axis} />
            <YAxis {...axis} />
            <ReferenceLine y={0} stroke={colors["--axis"]} />
            <Tooltip
              content={<VizTooltip formatValue={(v) => num(v, 1)} />}
              labelFormatter={fullDate}
            />
            <Bar dataKey="tsb" name="TSB" isAnimationActive={false}>
              {rows.map((row) => (
                <Cell
                  key={row.date}
                  fill={row.tsb >= 0 ? colors["--tsb-positive"] : colors["--tsb-negative"]}
                />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
        <p className="card-subtitle" style={{ marginTop: 0 }}>
          Acima de +5 é forma de prova; entre −10 e −30, treino produtivo; abaixo
          de −30, risco de overtraining.
        </p>
      </div>

      {showHealth && hasHrv && (
        <div style={{ marginTop: "var(--space-5)" }}>
          <span className="label">HRV · resposta do corpo</span>
          <ResponsiveContainer width="100%" height={110}>
            <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
              <CartesianGrid stroke={colors["--gridline"]} vertical={false} opacity={0.35} />
              <XAxis dataKey="date" tickFormatter={formatTick} {...axis} />
              <YAxis {...axis} domain={["dataMin - 4", "dataMax + 4"]} unit=" ms" />
              <Tooltip
                content={<VizTooltip formatValue={(v) => `${num(v, 0)} ms`} />}
                labelFormatter={fullDate}
              />
              <Line
                dataKey="hrv"
                name="HRV"
                stroke={colors["--hrv"]}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </ChartFrame>
  )
}
