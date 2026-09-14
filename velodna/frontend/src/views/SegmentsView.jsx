/*
 * Visão Segmentos — trechos pessoais e histórico de passagens (US-07/08).
 *
 * O gráfico de evolução é o ponto: um segmento só vale como teste repetido se
 * dá para ver se o tempo caiu ao longo dos meses. A tabela ordenada por tempo
 * responde "qual foi meu melhor"; o gráfico responde "estou melhorando".
 */
import { useCallback, useEffect, useState } from "react"
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

import ChartFrame from "../components/viz/ChartFrame"
import VizTooltip from "../components/viz/Tooltip"
import StatTile from "../components/viz/StatTile"
import { api } from "../lib/api"
import { useCssVars } from "../lib/useCssVar"
import { axisDateFormatter, fullDate, km, num } from "../lib/format"

const TOKENS = [
  "--series-1",
  "--series-2",
  "--status-good",
  "--gridline",
  "--axis",
  "--text-muted",
]

/** Tempo em segundos para `mm:ss`. */
function clock(seconds) {
  if (seconds === null || seconds === undefined) return "—"
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`
}

export default function SegmentsView() {
  const [segments, setSegments] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(false)

  const loadSegments = useCallback(() => {
    api.segments.list().then((list) => {
      setSegments(list)
      setSelectedId((current) => current ?? list[0]?.id ?? null)
    })
  }, [])

  useEffect(() => {
    loadSegments()
  }, [loadSegments])

  useEffect(() => {
    if (!selectedId) return

    let cancelled = false
    api.segments.efforts(selectedId).then((data) => {
      if (!cancelled) setDetail(data)
    })
    return () => {
      cancelled = true
    }
  }, [selectedId])

  // O detalhe só vale para o segmento selecionado. Comparar aqui evita um
  // `setState` no corpo do efeito só para descartar dado obsoleto.
  const current = detail?.segment?.id === selectedId ? detail : null

  const rescan = () => {
    setBusy(true)
    api.segments
      .rescan(selectedId)
      .then(() => api.segments.efforts(selectedId))
      .then(setDetail)
      .finally(() => setBusy(false))
  }

  const remove = () => {
    setBusy(true)
    api.segments
      .remove(selectedId)
      .then(() => {
        setSelectedId(null)
        loadSegments()
      })
      .finally(() => setBusy(false))
  }

  if (segments === null) return <p className="muted">Carregando…</p>

  if (!segments.length) {
    return (
      <section className="card">
        <h2 className="card-title">Segmentos</h2>
        <p className="muted">
          Nenhum segmento criado. Segmentos nascem de um trecho de uma atividade
          sua — o sistema então procura esse mesmo trecho em todo o histórico.
        </p>
      </section>
    )
  }

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      <section className="card">
        <div className="toolbar" style={{ marginBottom: 0 }}>
          <div className="segmented" role="group" aria-label="Segmento">
            {segments.map((s) => (
              <button
                key={s.id}
                aria-pressed={s.id === selectedId}
                onClick={() => setSelectedId(s.id)}
              >
                {s.name}
              </button>
            ))}
          </div>
          <button onClick={rescan} disabled={busy || !selectedId} style={buttonStyle}>
            {busy ? "Processando…" : "Reprocessar histórico"}
          </button>
          <button onClick={remove} disabled={busy || !selectedId} style={buttonStyle}>
            Remover
          </button>
        </div>
      </section>

      {current && <SegmentDetail detail={current} />}
    </div>
  )
}

/** Números, evolução e histórico de um segmento. */
function SegmentDetail({ detail }) {
  const colors = useCssVars(TOKENS)
  const { segment, efforts } = detail

  if (!efforts.length) {
    return (
      <section className="card">
        <h2 className="card-title">{segment.name}</h2>
        <p className="muted">Nenhuma passagem encontrada neste segmento.</p>
      </section>
    )
  }

  const best = efforts[0]
  const chronological = [...efforts]
    .sort((a, b) => (a.started_at < b.started_at ? -1 : 1))
    .map((e) => ({ ...e, date: String(e.started_at).slice(0, 10) }))

  const latest = chronological[chronological.length - 1]
  const spanDays =
    (new Date(latest.date) - new Date(chronological[0].date)) / 86400000

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        <StatTile label="Distância" value={km(segment.distance_m)} />
        <StatTile label="Passagens" value={num(efforts.length, 0)} />
        <StatTile
          label="Melhor tempo"
          value={clock(best.elapsed_time_s)}
          context={fullDate(best.started_at)}
          statusToken="--status-good"
        />
        <StatTile
          label="Velocidade no recorde"
          value={num(best.avg_speed_ms * 3.6, 1)}
          unit="km/h"
        />
        <StatTile
          label="Potência no recorde"
          value={best.avg_power_w ? num(best.avg_power_w) : "—"}
          unit={best.avg_power_w ? "W" : ""}
        />
        <StatTile
          label="Última passagem"
          value={clock(latest.elapsed_time_s)}
          context={fullDate(latest.started_at)}
        />
      </div>

      <ChartFrame
        title="Evolução no segmento"
        subtitle="Tempo de cada passagem — mais baixo é melhor"
        series={[
          { label: "Passagem", color: colors["--series-1"] },
          { label: "Melhor tempo", color: colors["--status-good"] },
        ]}
      >
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart
            data={chronological}
            margin={{ top: 4, right: 8, bottom: 0, left: -6 }}
          >
            <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={axisDateFormatter(spanDays)}
              tick={{ fill: colors["--text-muted"], fontSize: 11 }}
              stroke={colors["--axis"]}
              minTickGap={72}
            />
            {/* Eixo invertido: tempo menor é desempenho melhor, então o melhor
                resultado deve aparecer mais alto no gráfico. */}
            <YAxis
              reversed
              tick={{ fill: colors["--text-muted"], fontSize: 11 }}
              stroke={colors["--axis"]}
              width={54}
              tickFormatter={clock}
              domain={[
                (min) => Math.floor((min - 20) / 30) * 30,
                (max) => Math.ceil((max + 20) / 30) * 30,
              ]}
            />
            <ReferenceLine
              y={best.elapsed_time_s}
              stroke={colors["--status-good"]}
              strokeDasharray="4 3"
              label={{
                value: `recorde ${clock(best.elapsed_time_s)}`,
                position: "insideTopRight",
                fill: colors["--text-muted"],
                fontSize: 10,
              }}
            />
            <Tooltip
              content={<VizTooltip formatValue={clock} />}
              labelFormatter={fullDate}
              cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
            />
            <Line
              type="monotone"
              dataKey="elapsed_time_s"
              name="Passagem"
              stroke={colors["--series-1"]}
              strokeWidth={1.5}
              dot={{ r: 3, strokeWidth: 0, fill: colors["--series-1"] }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartFrame>

      <section className="card">
        <h2 className="card-title">Histórico de passagens</h2>
        <p className="card-subtitle">Ordenado do melhor para o pior tempo</p>
        <div className="scroll-x" style={{ maxHeight: 420, overflowY: "auto" }}>
          <table className="data">
            <thead>
              <tr>
                <th>#</th>
                <th>Data</th>
                <th>Tempo</th>
                <th>Velocidade</th>
                <th>Potência</th>
                <th>FC</th>
                <th>Atraso</th>
              </tr>
            </thead>
            <tbody>
              {efforts.map((e) => (
                <tr key={e.id}>
                  <td>
                    {e.rank}
                    {/* Recorde marcado com texto, não só com cor. */}
                    {e.is_pr && (
                      <span
                        style={{
                          marginLeft: 4,
                          color: "var(--status-good)",
                          fontWeight: 700,
                        }}
                      >
                        PR
                      </span>
                    )}
                  </td>
                  <td>{fullDate(e.started_at)}</td>
                  <td>{clock(e.elapsed_time_s)}</td>
                  <td>{num(e.avg_speed_ms * 3.6, 1)} km/h</td>
                  <td>{e.avg_power_w ? `${num(e.avg_power_w)} W` : "—"}</td>
                  <td>{e.avg_hr_bpm ? `${num(e.avg_hr_bpm)} bpm` : "—"}</td>
                  <td>
                    {e.elapsed_time_s === best.elapsed_time_s
                      ? "—"
                      : `+${clock(e.elapsed_time_s - best.elapsed_time_s)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

const buttonStyle = {
  font: "inherit",
  fontSize: "var(--fs-small)",
  fontWeight: 600,
  padding: "6px 12px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "var(--surface-sunken)",
  color: "var(--text-primary)",
  cursor: "pointer",
}
