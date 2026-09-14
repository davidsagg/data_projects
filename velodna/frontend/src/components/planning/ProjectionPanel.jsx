/*
 * Projeção de carga — "se eu treinar assim, onde chego?" e o inverso.
 *
 * O ritmo de rampa é mostrado junto com o resultado, e não escondido, porque
 * é a informação que impede o uso ingênuo da ferramenta: quase sempre existe
 * uma carga que atinge o CTL desejado no prazo pedido, e frequentemente ela é
 * exatamente a que causa lesão.
 */
import { useState } from "react"
import {
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
import { api } from "../../lib/api"
import { useCssVars } from "../../lib/useCssVar"
import { axisDateFormatter, fullDate, num } from "../../lib/format"

const TOKENS = [
  "--series-1",
  "--series-2",
  "--series-3",
  "--status-warning",
  "--gridline",
  "--axis",
  "--text-muted",
]

const WEEKDAYS = [
  ["seg", 0], ["ter", 1], ["qua", 2], ["qui", 3],
  ["sex", 4], ["sáb", 5], ["dom", 6],
]

export default function ProjectionPanel() {
  const [mode, setMode] = useState("load")
  const [weeks, setWeeks] = useState(6)
  const [weeklyTss, setWeeklyTss] = useState(500)
  const [targetCtl, setTargetCtl] = useState(80)
  const [restDays, setRestDays] = useState([0])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const colors = useCssVars(TOKENS)

  const run = () => {
    setBusy(true)
    setError(null)
    api.planning
      .projection({
        days: weeks * 7,
        rest_days: restDays,
        ...(mode === "load"
          ? { weekly_tss: Number(weeklyTss) }
          : { target_ctl: Number(targetCtl) }),
      })
      .then(setResult)
      .catch((e) =>
        setError(
          e.response?.data?.detail || "Não foi possível calcular a projeção",
        ),
      )
      .finally(() => setBusy(false))
  }

  const summary = result?.summary
  const series = [
    { label: "CTL · fitness", color: colors["--series-1"] },
    { label: "ATL · fadiga", color: colors["--series-2"] },
    { label: "TSB · forma", color: colors["--series-3"] },
  ]

  return (
    <ChartFrame
      title="Projeção de carga"
      subtitle={
        summary
          ? `${num(result.weekly_tss, 0)} TSS/semana · CTL ${result.current_ctl} → ${summary.final_ctl}`
          : "Simule a carga das próximas semanas"
      }
      series={result ? series : null}
    >
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Modo">
          <button aria-pressed={mode === "load"} onClick={() => setMode("load")}>
            Definir carga
          </button>
          <button
            aria-pressed={mode === "target"}
            onClick={() => setMode("target")}
          >
            Definir alvo de CTL
          </button>
        </div>

        <label style={labelStyle}>
          Semanas
          <input
            type="number"
            min="1"
            max="26"
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
            style={inputStyle}
          />
        </label>

        {mode === "load" ? (
          <label style={labelStyle}>
            TSS por semana
            <input
              type="number"
              min="0"
              step="50"
              value={weeklyTss}
              onChange={(e) => setWeeklyTss(e.target.value)}
              style={inputStyle}
            />
          </label>
        ) : (
          <label style={labelStyle}>
            CTL alvo
            <input
              type="number"
              min="0"
              value={targetCtl}
              onChange={(e) => setTargetCtl(e.target.value)}
              style={inputStyle}
            />
          </label>
        )}

        <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
          <legend style={{ ...labelStyle, padding: 0 }}>Descanso</legend>
          <div className="segmented">
            {WEEKDAYS.map(([label, index]) => (
              <button
                key={index}
                aria-pressed={restDays.includes(index)}
                onClick={() =>
                  setRestDays((current) =>
                    current.includes(index)
                      ? current.filter((d) => d !== index)
                      : [...current, index],
                  )
                }
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        <button onClick={run} disabled={busy} style={buttonStyle}>
          {busy ? "Calculando…" : "Projetar"}
        </button>
      </div>

      {error && (
        <p style={{ color: "var(--status-critical)", fontSize: "var(--fs-small)" }}>
          {error}
        </p>
      )}

      {summary && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              gap: "var(--space-3)",
              marginBottom: "var(--space-3)",
            }}
          >
            <Figure label="CTL final" value={num(summary.final_ctl, 1)} />
            <Figure label="TSB final" value={num(summary.final_tsb, 1)} />
            <Figure label="TSB mínimo" value={num(summary.min_tsb, 1)} />
            <Figure
              label="Rampa"
              value={`${num(summary.ramp_rate_per_week, 1)}/sem`}
              warning={summary.ramp_exceeds_safe_limit}
              note={
                summary.ramp_exceeds_safe_limit
                  ? `acima do limite seguro de ${summary.safe_ramp_limit}`
                  : "dentro do limite seguro"
              }
            />
            <Figure label="TSS total" value={num(summary.total_tss, 0)} />
          </div>

          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart
              data={result.days}
              margin={{ top: 4, right: 8, bottom: 0, left: -6 }}
            >
              <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={axisDateFormatter(result.days.length)}
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
                content={<VizTooltip formatValue={(v) => num(v, 1)} />}
                labelFormatter={fullDate}
                cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
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
              <Line
                type="monotone"
                dataKey="tsb"
                name="TSB · forma"
                stroke={colors["--series-3"]}
                strokeWidth={1.5}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}
    </ChartFrame>
  )
}

/** Número com rótulo e aviso opcional de limite excedido. */
function Figure({ label, value, note, warning }) {
  return (
    <div>
      <div className="card-title" style={{ marginBottom: 2 }}>
        {label}
      </div>
      <div
        className="figure tabular"
        style={{
          fontSize: "var(--fs-figure)",
          color: warning ? "var(--status-warning)" : "var(--text-primary)",
        }}
      >
        {value}
      </div>
      {note && (
        <div
          style={{
            fontSize: "var(--fs-micro)",
            color: warning ? "var(--status-warning)" : "var(--text-muted)",
          }}
        >
          {/* Aviso nunca depende só da cor: o texto diz o que houve. */}
          {warning ? "⚠ " : ""}
          {note}
        </div>
      )}
    </div>
  )
}

const labelStyle = {
  display: "grid",
  gap: 2,
  fontSize: "var(--fs-micro)",
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.03em",
}

const inputStyle = {
  font: "inherit",
  fontSize: "var(--fs-small)",
  padding: "4px 6px",
  width: 84,
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "var(--surface-1)",
  color: "var(--text-primary)",
}

const buttonStyle = {
  font: "inherit",
  fontSize: "var(--fs-small)",
  fontWeight: 600,
  padding: "6px 14px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "var(--surface-sunken)",
  color: "var(--text-primary)",
  cursor: "pointer",
  alignSelf: "end",
}
