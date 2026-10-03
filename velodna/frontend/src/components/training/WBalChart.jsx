/*
 * W'bal sobre o terreno — onde, no percurso, o tanque esvaziou.
 *
 * Dois painéis empilhados com o mesmo eixo X (distância, ou tempo quando não há
 * GPS): o perfil de elevação em cima, a reserva anaeróbica embaixo. Não é um
 * gráfico só com dois eixos verticais — metros e quilojoules não se comparam
 * por altura, e o cruzamento de duas escalas arbitrárias vira coincidência
 * visual. O que liga os dois é o alinhamento horizontal, o cursor sincronizado
 * e as faixas: cada trecho com o W' abaixo de 25% aparece marcado nos dois
 * painéis, numerado, e listado na tabela com a rampa que levou até ele.
 */
import { useState } from "react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import { useCssVars } from "../../lib/useCssVar"
import { duration, num } from "../../lib/format"

const TOKENS = [
  "--series-1",
  "--status-serious",
  "--status-warning",
  "--text-tertiary",
  "--gridline",
  "--axis",
  "--text-muted",
  "--surface-1",
]

const SYNC_ID = "wbal-terrain"

const TERRAIN_LABEL = {
  subida: "subida",
  descida: "descida",
  plano: "plano",
  "sem altitude": "—",
}

/** Pontos antigos (só `balance`) viram pontos com tempo reconstruído. */
function legacyPoints(data, elapsedTimeS) {
  const step = (elapsedTimeS || data.balance.length) / data.balance.length
  return data.balance.map((joules, index) => ({
    t: Math.round(index * step),
    km: null,
    alt: null,
    kj: Number((joules / 1000).toFixed(2)),
    w: null,
  }))
}

function TerrainTooltip({ active, payload, wPrimeKj }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="viz-tooltip">
      <div className="viz-tooltip-title">
        {p.km != null ? `km ${num(p.km, 1)} · ` : ""}
        {duration(p.t)}
      </div>
      {p.alt != null && (
        <div className="viz-tooltip-row">
          <span className="viz-tooltip-label">Altitude</span>
          <span className="viz-tooltip-value">{num(p.alt, 0)} m</span>
        </div>
      )}
      <div className="viz-tooltip-row">
        <span className="viz-tooltip-label">W' restante</span>
        <span className="viz-tooltip-value">
          {num(p.kj, 1)} kJ · {num((p.kj / wPrimeKj) * 100, 0)}%
        </span>
      </div>
      {p.w != null && (
        <div className="viz-tooltip-row">
          <span className="viz-tooltip-label">Potência</span>
          <span className="viz-tooltip-value">{num(p.w, 0)} W</span>
        </div>
      )}
    </div>
  )
}

export default function WBalChart({ data, elapsedTimeS }) {
  const colors = useCssVars(TOKENS)
  const points = data?.points?.length ? data.points : data?.balance?.length ? legacyPoints(data, elapsedTimeS) : []

  const hasDistance = points.some((p) => p.km != null)
  const hasAltitude = points.some((p) => p.alt != null)
  const [axisMode, setAxisMode] = useState("km")
  const byDistance = hasDistance && axisMode === "km"
  const xKey = byDistance ? "km" : "t"

  if (!points.length) return null

  const wPrimeKj = data.w_prime_j / 1000
  const halfKj = wPrimeKj / 2
  const reserveKj = (wPrimeKj * (data.depleted_threshold_pct ?? 25)) / 100
  const episodes = (data.episodes || []).map((e, i) => ({ ...e, n: i + 1 }))
  const rows = byDistance ? points.filter((p) => p.km != null) : points

  const xStart = (e) => (byDistance ? e.start_km : e.start_s)
  const xEnd = (e) => (byDistance ? e.end_km : e.end_s)
  const formatX = byDistance ? (v) => `${num(v, 0)} km` : duration

  const xAxis = {
    dataKey: xKey,
    type: "number",
    domain: ["dataMin", "dataMax"],
    tickFormatter: formatX,
    stroke: colors["--axis"],
    tick: { fill: colors["--text-muted"], fontSize: 11 },
    tickLine: false,
    minTickGap: 40,
  }
  const yAxis = {
    stroke: colors["--axis"],
    tick: { fill: colors["--text-muted"], fontSize: 11 },
    tickLine: false,
    axisLine: false,
    width: 56,
  }

  const bands = (withLabel) =>
    episodes
      .filter((e) => xStart(e) != null && xEnd(e) != null)
      .map((e) => (
        <ReferenceArea
          key={e.n}
          x1={xStart(e)}
          x2={xEnd(e)}
          fill={colors["--status-serious"]}
          fillOpacity={0.14}
          stroke="none"
          ifOverflow="hidden"
          label={
            withLabel
              ? {
                  value: e.n,
                  position: "top",
                  fill: colors["--status-serious"],
                  fontSize: 11,
                  fontWeight: 700,
                }
              : undefined
          }
        />
      ))

  const subtitle =
    `CP ${num(data.cp_w, 0)} W · W' ${num(wPrimeKj, 1)} kJ · ` +
    `${num(data.depletion_pct, 0)}% consumido no fundo · ` +
    `${data.matches_burned} ${data.matches_burned === 1 ? "fósforo" : "fósforos"}`

  return (
    <ChartFrame
      title="W'bal sobre o percurso"
      subtitle={subtitle}
      series={
        hasAltitude
          ? [
              { label: "Elevação", color: colors["--text-tertiary"] },
              { label: "W' restante", color: colors["--series-1"] },
              { label: `Tanque na reserva (< ${num(data.depleted_threshold_pct ?? 25, 0)}%)`, color: colors["--status-serious"] },
            ]
          : null
      }
      action={
        hasDistance && (
          <nav className="segmented" role="group" aria-label="Eixo horizontal">
            <button aria-pressed={axisMode === "km"} onClick={() => setAxisMode("km")}>
              distância
            </button>
            <button aria-pressed={axisMode === "t"} onClick={() => setAxisMode("t")}>
              tempo
            </button>
          </nav>
        )
      }
      table={
        episodes.length
          ? {
              columns: [
                { key: "n", label: "#", format: (v) => <strong>{v}</strong> },
                {
                  key: "start_km",
                  label: "Onde",
                  format: (v, e) =>
                    v != null
                      ? `km ${num(v, 1)}–${num(e.end_km, 1)}`
                      : `${duration(e.start_s)}–${duration(e.end_s)}`,
                },
                { key: "min_s", label: "Fundo em", num: true, format: (v) => duration(v) },
                { key: "duration_s", label: "Na reserva", num: true, format: (v) => duration(v) },
                { key: "min_pct", label: "W' mínimo", num: true, format: (v) => `${num(v, 0)}%` },
                { key: "avg_power_w", label: "Pot. média", num: true, format: (v) => (v ? `${num(v)} W` : "—") },
                { key: "terrain", label: "Terreno antes", format: (v) => TERRAIN_LABEL[v] ?? v },
                {
                  key: "lead_gain_m",
                  label: "Subiu até o fundo",
                  num: true,
                  format: (v, e) =>
                    v != null && v >= 10
                      ? `${num(v)} m${e.lead_grade_pct != null ? ` a ${num(e.lead_grade_pct, 1)}%` : ""}`
                      : "—",
                },
              ],
              rows: episodes,
            }
          : null
      }
    >
      {hasAltitude && (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={rows} syncId={SYNC_ID} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
            <XAxis {...xAxis} hide />
            <YAxis
              {...yAxis}
              domain={[(min) => Math.floor(min / 100) * 100, (max) => Math.ceil(max / 100) * 100]}
              tickCount={4}
              allowDecimals={false}
              tickFormatter={(v) => `${num(v)} m`}
            />
            {bands(true)}
            <Tooltip
              content={<TerrainTooltip wPrimeKj={wPrimeKj} />}
              cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
            />
            <Area
              dataKey="alt"
              name="Elevação"
              stroke={colors["--text-tertiary"]}
              fill={colors["--text-tertiary"]}
              fillOpacity={0.18}
              strokeWidth={1.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}

      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={rows} syncId={SYNC_ID} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis {...xAxis} />
          <YAxis {...yAxis} domain={[0, Math.ceil(wPrimeKj)]} tickFormatter={(v) => `${num(v)} kJ`} />
          {bands(!hasAltitude)}
          <ReferenceLine
            y={halfKj}
            stroke={colors["--status-warning"]}
            strokeDasharray="4 4"
            label={{
              value: "50%",
              position: "insideTopRight",
              fill: colors["--text-muted"],
              fontSize: 11,
            }}
          />
          <ReferenceLine y={reserveKj} stroke={colors["--status-serious"]} strokeDasharray="2 4" />
          <Tooltip
            content={hasAltitude ? () => null : <TerrainTooltip wPrimeKj={wPrimeKj} />}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
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

      {episodes.length === 0 ? (
        <p className="muted" style={{ margin: "var(--space-2) 0 0", fontSize: "var(--fs-small)" }}>
          O W' não desceu abaixo de {num(data.depleted_threshold_pct ?? 25, 0)}% da reserva em nenhum momento.
        </p>
      ) : (
        <p style={{ margin: "var(--space-2) 0 0", fontSize: "var(--fs-small)", color: "var(--text-secondary)" }}>
          {episodes.length} {episodes.length === 1 ? "trecho" : "trechos"} com o tanque na reserva
          {(() => {
            const climbs = episodes.filter((e) => e.terrain === "subida").length
            return climbs ? ` — ${climbs} ao fim de uma subida` : ""
          })()}
          . Abra a tabela para ver onde e quanto se subiu até cada um.
        </p>
      )}
    </ChartFrame>
  )
}
