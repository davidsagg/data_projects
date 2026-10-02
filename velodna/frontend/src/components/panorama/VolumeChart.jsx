/*
 * Volume semanal por modalidade — barras empilhadas, com a meta tracejada.
 *
 * Empilhar responde às duas perguntas de uma vez: quanto treinei (altura total,
 * lida contra a linha da meta) e de que jeito (a fatia de rua, rolo e força).
 * O TSS não entra neste gráfico: é outra unidade, e dividir o eixo vertical
 * entre horas e TSS seria o gráfico de dois eixos que o guia proíbe. Ele aparece
 * no tooltip e na tabela.
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import { MODALITY_TOKENS } from "../../lib/goals"
import { useCssVars } from "../../lib/useCssVar"
import { dayMonth, num } from "../../lib/format"


const TOKENS = [
  ...Object.values(MODALITY_TOKENS),
  "--gridline",
  "--axis",
  "--text-muted",
  "--text-tertiary",
  "--surface-1",
]

function hours(value) {
  return `${num(value, 1)} h`
}

function VolumeTooltip({ active, payload, modalities }) {
  if (!active || !payload?.length) return null
  const week = payload[0].payload
  return (
    <div className="viz-tooltip">
      <div className="viz-tooltip-title">
        {dayMonth(week.week_start)} – {dayMonth(week.week_end)}
      </div>
      {modalities
        .filter((m) => week[m.key] > 0)
        .map((m) => (
          <div className="viz-tooltip-row" key={m.key}>
            <span className="viz-tooltip-label">
              <span className="viz-swatch" style={{ background: m.color }} />
              {m.label}
            </span>
            <span className="viz-tooltip-value">{hours(week[m.key])}</span>
          </div>
        ))}
      <div className="viz-tooltip-row" style={{ marginTop: 4 }}>
        <span className="viz-tooltip-label">Total</span>
        <span className="viz-tooltip-value">{hours(week.total_hours)}</span>
      </div>
      <div className="viz-tooltip-row">
        <span className="viz-tooltip-label">TSS</span>
        <span className="viz-tooltip-value">{num(week.tss, 0)}</span>
      </div>
    </div>
  )
}

export default function VolumeChart({ volume, goalHours }) {
  const colors = useCssVars(TOKENS)

  // Só entram na legenda e nas barras as modalidades que aparecem na janela.
  const modalities = volume.modalities
    .filter((m) => volume.weeks.some((w) => w.hours[m.key] > 0))
    .map((m) => ({ ...m, color: colors[MODALITY_TOKENS[m.key]] }))

  const rows = volume.weeks.map((w) => ({ ...w, ...w.hours }))
  const max = Math.max(goalHours || 0, ...rows.map((r) => r.total_hours))
  const top = Math.ceil((max + 1) / 2) * 2

  return (
    <ChartFrame
      title="Volume semanal por modalidade"
      subtitle={
        goalHours
          ? `Horas em movimento · linha tracejada = meta de ${num(goalHours, 0)} h/semana`
          : "Horas em movimento por semana"
      }
      series={modalities.map((m) => ({ label: m.label, color: m.color }))}
      table={{
        columns: [
          {
            key: "week_start",
            label: "Semana",
            format: (v, r) => `${dayMonth(v)} – ${dayMonth(r.week_end)}`,
          },
          ...modalities.map((m) => ({
            key: m.key,
            label: m.label,
            num: true,
            format: hours,
          })),
          { key: "total_hours", label: "Total", num: true, format: hours },
          { key: "tss", label: "TSS", num: true, format: (v) => num(v, 0) },
          { key: "elevation_m", label: "Elevação", num: true, format: (v) => `${num(v)} m` },
        ],
        rows,
      }}
    >
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 12, right: 8, bottom: 0, left: -18 }}>
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
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            allowDecimals={false}
            tickFormatter={(v) => `${v}h`}
          />
          <Tooltip
            content={<VolumeTooltip modalities={modalities} />}
            cursor={{ fill: colors["--gridline"], opacity: 0.5 }}
          />
          {modalities.map((m, i) => (
            <Bar
              key={m.key}
              dataKey={m.key}
              name={m.label}
              stackId="volume"
              fill={m.color}
              stroke={colors["--surface-1"]}
              strokeWidth={1.5}
              maxBarSize={36}
              radius={i === modalities.length - 1 ? [4, 4, 0, 0] : 0}
              isAnimationActive={false}
            />
          ))}
          {goalHours && (
            <ReferenceLine
              y={goalHours}
              stroke={colors["--text-tertiary"]}
              strokeDasharray="4 4"
              label={{
                value: `meta ${num(goalHours, 0)} h`,
                position: "insideTopLeft",
                fill: colors["--text-tertiary"],
                fontSize: 11,
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
