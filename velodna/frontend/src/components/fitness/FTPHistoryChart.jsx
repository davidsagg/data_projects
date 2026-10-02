/*
 * Evolução do FTP, distinguindo o que foi medido do que foi estimado.
 *
 * A distinção é o ponto do gráfico: uma estimativa derivada da curva só é tão
 * boa quanto o esforço máximo mais recente, enquanto um teste de campo é um
 * dado. Marcar os testes com ponto sólido e rótulo direto — em vez de confiar
 * numa cor diferente — mantém a leitura sem depender de cor.
 */
import { useMemo } from "react"
import {
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Scatter,
  ComposedChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { milestoneLines } from "../viz/milestoneLines"
import { useCssVars } from "../../lib/useCssVar"
import { fullDate, monthYear, num } from "../../lib/format"

const TOKENS = [
  "--series-1",
  "--series-2",
  "--gridline",
  "--axis",
  "--text-muted",
  "--text-tertiary",
  "--surface-1",
]

export default function FTPHistoryChart({ history, milestones }) {
  const colors = useCssVars(TOKENS)

  const { rows, measured } = useMemo(() => {
    if (!history?.length) return { rows: [], measured: [] }
    const sorted = [...history].sort((a, b) =>
      a.effective_from < b.effective_from ? -1 : 1,
    )
    const points = sorted.map((h) => ({
      date: h.effective_from,
      ftp: h.ftp_w,
      source: h.source,
      method: h.method,
      cp_w: h.cp_w,
    }))
    // O eixo X é categórico (uma categoria por ponto do histórico); para o marco
    // ganhar linha, a data dele precisa existir como categoria. Entra com o FTP
    // vigente naquele dia, então a linha em degrau não muda de forma.
    const known = new Set(points.map((p) => p.date))
    for (const m of milestones || []) {
      if (known.has(m.date) || m.date < points[0].date) continue
      const vigente = [...points].reverse().find((p) => p.date <= m.date)
      points.push({ date: m.date, ftp: vigente?.ftp ?? null })
      known.add(m.date)
    }
    points.sort((a, b) => (a.date < b.date ? -1 : 1))
    return {
      rows: points,
      measured: sorted
        .filter((h) => h.source === "test" || h.source === "manual")
        .map((h) => ({
          date: h.effective_from,
          measured_ftp: h.ftp_w,
          ftp: h.ftp_w,
          source: h.source,
          cp_w: h.cp_w,
        })),
    }
  }, [history, milestones])

  if (!rows.length) {
    return (
      <ChartFrame title="Evolução do FTP">
        <p className="muted">Sem histórico de FTP.</p>
      </ChartFrame>
    )
  }

  const series = [
    { label: "Estimado da curva", color: colors["--series-1"] },
    { label: "Medido (teste ou informado)", color: colors["--series-2"] },
  ]

  const latestMeasured = measured[measured.length - 1]

  return (
    <ChartFrame
      title="Evolução do FTP"
      subtitle={
        latestMeasured
          ? `Último medido: ${num(latestMeasured.ftp)} W em ${fullDate(latestMeasured.date)}`
          : "Somente estimativas"
      }
      series={series}
    >
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={monthYear}
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            minTickGap={72}
          />
          {/* O domínio precisa ser numérico: strings como "dataMin - 15" fazem
              o Recharts repetir o mesmo tick ao longo de todo o eixo. */}
          <YAxis
            tick={{ fill: colors["--text-muted"], fontSize: 11 }}
            stroke={colors["--axis"]}
            width={50}
            domain={[
              (min) => Math.floor((min - 15) / 10) * 10,
              (max) => Math.ceil((max + 15) / 10) * 10,
            ]}
            allowDecimals={false}
          />
          <Tooltip
            content={
              <VizTooltip
                formatValue={(v, _key, row) =>
                  `${num(v)} W${row?.method ? ` · ${row.method}` : ""}`
                }
              />
            }
            labelFormatter={fullDate}
            cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
          />
          <Line
            type="stepAfter"
            dataKey="ftp"
            name="FTP vigente"
            stroke={colors["--series-1"]}
            strokeWidth={2}
            dot={false}
          />
          {/* Chave distinta da linha: duas séries com o mesmo dataKey fazem o
              React reclamar de chaves duplicadas e podem omitir marcas. */}
          <Scatter
            data={measured}
            dataKey="measured_ftp"
            name="Medido"
            fill={colors["--series-2"]}
            shape="circle"
            r={5}
          />
          {milestoneLines(milestones, null, colors)}
        </ComposedChart>
      </ResponsiveContainer>

      <div className="scroll-x" style={{ marginTop: "var(--space-3)" }}>
        <table className="data">
          <thead>
            <tr>
              <th>Data</th>
              <th>FTP</th>
              <th>CP</th>
              <th>Origem</th>
            </tr>
          </thead>
          <tbody>
            {measured
              .slice()
              .reverse()
              .map((m) => (
                <tr key={m.date}>
                  <td>{fullDate(m.date)}</td>
                  <td>{num(m.ftp)} W</td>
                  <td>{m.cp_w ? `${num(m.cp_w)} W` : "—"}</td>
                  <td>{m.source === "test" ? "Teste de campo" : "Informado"}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </ChartFrame>
  )
}
