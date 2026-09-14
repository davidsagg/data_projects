/*
 * Curva de potência (MMP) — melhor esforço por duração.
 *
 * O eixo de duração é logarítmico porque a curva cobre de 1 s a 2 h: numa
 * escala linear, tudo abaixo de 10 minutos colapsa contra o eixo e a parte
 * mais informativa da curva desaparece.
 *
 * A sobreposição do modelo CP/W' mostra onde os esforços reais ficam acima ou
 * abaixo do previsto — o afastamento é a informação, não o ajuste em si.
 */
import { useMemo, useState } from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { useCssVars } from "../../lib/useCssVar"
import { num, shortDuration } from "../../lib/format"

const TICKS = [1, 5, 15, 60, 300, 720, 1200, 3600, 7200]
const TOKENS = [
  "--series-1",
  "--series-4",
  "--gridline",
  "--axis",
  "--text-muted",
]

export default function PowerCurveChart({ curve, cp, weightKg }) {
  const [perKg, setPerKg] = useState(false)
  const colors = useCssVars(TOKENS)

  const rows = useMemo(() => {
    if (!curve?.length) return []
    const divisor = perKg && weightKg ? weightKg : 1
    return curve
      .filter((d) => d.power_w > 0)
      .map((d) => ({
        duration_s: d.duration_s,
        power: d.power_w / divisor,
        // O modelo só descreve a faixa de 2 a 20 min; fora dela não se desenha
        // uma previsão que se sabe inválida.
        model:
          cp && d.duration_s >= 120 && d.duration_s <= 1200
            ? (cp.w_prime_j / d.duration_s + cp.cp_w) / divisor
            : null,
      }))
  }, [curve, cp, perKg, weightKg])

  if (!rows.length) {
    return (
      <ChartFrame title="Curva de potência">
        <p className="muted">Sem esforços registrados.</p>
      </ChartFrame>
    )
  }

  const unit = perKg ? "W/kg" : "W"
  const digits = perKg ? 2 : 0
  const series = [
    { label: "Melhor esforço", color: colors["--series-1"] },
    ...(cp ? [{ label: "Modelo CP/W'", color: colors["--series-4"] }] : []),
  ]

  return (
    <ChartFrame
      title="Curva de potência"
      subtitle={
        cp
          ? `CP ${num(cp.cp_w)} W · W' ${num(cp.w_prime_kj, 1)} kJ · R² ${cp.r_squared ?? "—"}`
          : "Melhor potência média por duração"
      }
      series={series}
      action={
        weightKg ? (
          <div className="segmented" role="group" aria-label="Unidade">
            <button aria-pressed={!perKg} onClick={() => setPerKg(false)}>
              W
            </button>
            <button aria-pressed={perKg} onClick={() => setPerKg(true)}>
              W/kg
            </button>
          </div>
        ) : null
      }
    >
      <ResponsiveContainer width="100%" height={230}>
        <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="duration_s"
            scale="log"
            domain={["dataMin", "dataMax"]}
            type="number"
            ticks={TICKS}
            tickFormatter={shortDuration}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
          />
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            width={54}
            tickFormatter={(v) => num(v, digits)}
          />
          <Tooltip
            content={<VizTooltip formatValue={(v) => `${num(v, digits)} ${unit}`} />}
            labelFormatter={(v) => `Esforço de ${shortDuration(v)}`}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
          />
          <Line
            type="monotone"
            dataKey="power"
            name="Melhor esforço"
            stroke={colors["--series-1"]}
            strokeWidth={2}
            dot={{ r: 2.5, strokeWidth: 0, fill: colors["--series-1"] }}
            activeDot={{ r: 5 }}
          />
          {cp && (
            <Line
              type="monotone"
              dataKey="model"
              name="Modelo CP/W'"
              stroke={colors["--series-4"]}
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              connectNulls
            />
          )}
        </LineChart>
      </ResponsiveContainer>

      {/* Vista de tabela: exigida como alternativa não-visual e útil por si. */}
      <details style={{ marginTop: "var(--space-3)" }}>
        <summary
          style={{
            cursor: "pointer",
            fontSize: "var(--fs-micro)",
            color: "var(--text-muted)",
          }}
        >
          Ver como tabela
        </summary>
        <div className="scroll-x" style={{ marginTop: "var(--space-2)" }}>
          <table className="data">
            <thead>
              <tr>
                <th>Duração</th>
                <th>Potência</th>
                {weightKg && <th>W/kg</th>}
              </tr>
            </thead>
            <tbody>
              {curve
                .filter((d) => d.power_w > 0)
                .map((d) => (
                  <tr key={d.duration_s}>
                    <td>{shortDuration(d.duration_s)}</td>
                    <td>{num(d.power_w)} W</td>
                    {weightKg && <td>{num(d.power_w / weightKg, 2)}</td>}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </details>
    </ChartFrame>
  )
}
