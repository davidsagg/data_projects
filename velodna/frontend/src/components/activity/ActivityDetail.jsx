/*
 * Detalhe de uma atividade: números, percurso, séries e zonas.
 *
 * O mapa e o gráfico de séries dividem o mesmo eixo de tempo implícito, então
 * ler os dois juntos mostra onde no percurso o esforço aconteceu.
 */
import { useMemo } from "react"
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { MapContainer, Polyline, TileLayer } from "react-leaflet"
import "leaflet/dist/leaflet.css"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import StatTile from "../viz/StatTile"
import { useCssVars } from "../../lib/useCssVar"
import { duration, fullDate, km, num, shortDuration } from "../../lib/format"

const TOKENS = [
  "--series-1",
  "--series-2",
  "--series-3",
  "--gridline",
  "--axis",
  "--text-muted",
]

/**
 * @param highlight conteúdo exibido logo abaixo dos números do treino — o
 *   painel que a tela quer em destaque (hoje, o W'bal sobre o percurso).
 */
export default function ActivityDetail({ activity, streams, zones, highlight }) {
  const colors = useCssVars(TOKENS)

  const track = useMemo(
    () =>
      (streams || [])
        .filter((s) => s.lat !== null && s.lon !== null)
        .map((s) => [s.lat, s.lon]),
    [streams],
  )

  const center = track.length ? track[Math.floor(track.length / 2)] : null

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      <header>
        <h1 style={{ margin: 0, fontSize: "1.375rem", fontWeight: 800 }}>
          {activity.name || "Atividade"}
        </h1>
        <p className="section-lede">{fullDate(activity.started_at)}</p>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        <StatTile
          label="Distância"
          value={activity.distance_m ? num(activity.distance_m / 1000, 1) : "—"}
          unit={activity.distance_m ? "km" : undefined}
        />
        <StatTile label="Duração" value={duration(activity.elapsed_time_s)} />
        <StatTile
          label="NP"
          value={num(activity.normalized_power_w)}
          unit="W"
          context={
            activity.avg_power_w
              ? `média ${num(activity.avg_power_w)} W`
              : null
          }
        />
        <StatTile
          label="TSS"
          value={num(activity.tss, 0)}
          context={activity.tss_source === "hr" ? "estimado por FC" : null}
        />
        <StatTile label="IF" value={num(activity.intensity_factor, 2)} />
        <StatTile
          label="Elevação"
          value={num(activity.elevation_gain_m)}
          unit="m"
        />
      </div>

      {highlight}

      {track.length > 1 && center && (
        <section className="card">
          <h2 className="card-title">Percurso</h2>
          <div style={{ height: 300, borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
            <MapContainer
              center={center}
              zoom={12}
              style={{ height: "100%", width: "100%" }}
              scrollWheelZoom={false}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <Polyline positions={track} color={colors["--series-1"]} weight={3} />
            </MapContainer>
          </div>
        </section>
      )}

      {streams?.length > 1 && (
        <ChartFrame
          title="Potência e frequência cardíaca"
          subtitle="Ao longo do tempo decorrido"
          series={[
            { label: "Potência (W)", color: colors["--series-1"] },
            { label: "FC (bpm)", color: colors["--series-2"] },
          ]}
        >
          {/* Potência e FC têm escalas diferentes, mas a comparação que importa
              é temporal, não de magnitude — painéis empilhados evitam o segundo
              eixo sem perder a leitura de coincidência. */}
          <ResponsiveContainer width="100%" height={150}>
            <ComposedChart data={streams} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
              <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
              <XAxis dataKey="time_s" hide />
              <YAxis
                tick={{ fill: colors["--text-muted"], fontSize: 11 }}
                stroke={colors["--axis"]}
                width={48}
              />
              <Tooltip
                content={<VizTooltip formatValue={(v) => `${num(v)} W`} />}
                labelFormatter={(v) => `aos ${shortDuration(v)}`}
                cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
              />
              <Area
                type="monotone"
                dataKey="power_w"
                name="Potência (W)"
                stroke={colors["--series-1"]}
                fill={colors["--series-1"]}
                fillOpacity={0.2}
                strokeWidth={1.2}
                dot={false}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>

          <ResponsiveContainer width="100%" height={110}>
            <ComposedChart data={streams} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
              <CartesianGrid stroke={colors["--gridline"]} vertical={false} />
              <XAxis
                dataKey="time_s"
                tickFormatter={shortDuration}
                tick={{ fill: colors["--text-muted"], fontSize: 11 }}
                stroke={colors["--axis"]}
                minTickGap={60}
              />
              <YAxis
                tick={{ fill: colors["--text-muted"], fontSize: 11 }}
                stroke={colors["--axis"]}
                width={48}
                domain={[
                  (min) => Math.floor((min - 5) / 10) * 10,
                  (max) => Math.ceil((max + 5) / 10) * 10,
                ]}
              />
              <Tooltip
                content={<VizTooltip formatValue={(v) => `${num(v)} bpm`} />}
                labelFormatter={(v) => `aos ${shortDuration(v)}`}
                cursor={{ stroke: colors["--axis"], strokeWidth: 1 }}
              />
              <Line
                type="monotone"
                dataKey="hr_bpm"
                name="FC (bpm)"
                stroke={colors["--series-2"]}
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartFrame>
      )}

      {zones?.power?.length > 0 && (
        <section className="card">
          <h2 className="card-title">Tempo em zona</h2>
          <p className="card-subtitle">FTP de referência: {num(zones.ftp_w)} W</p>
          <ZoneBars distribution={zones.power} unit="W" />
          {zones.hr?.length > 0 && (
            <>
              <p className="card-subtitle" style={{ marginTop: "var(--space-4)" }}>
                Frequência cardíaca · limiar {num(zones.threshold_hr_bpm)} bpm
              </p>
              <ZoneBars distribution={zones.hr} unit="bpm" />
            </>
          )}
        </section>
      )}
    </div>
  )
}

/**
 * Barras horizontais de tempo em zona.
 *
 * Uma barra por zona, com rótulo direto do percentual — o valor fica visível
 * sem depender de hover, e a zona é identificada pelo texto, não pela cor.
 */
function ZoneBars({ distribution, unit }) {
  const max = Math.max(...distribution.map((z) => z.pct), 1)

  return (
    <div style={{ display: "grid", gap: "var(--space-1)" }}>
      {distribution.map((zone) => (
        <div
          key={zone.zone}
          style={{
            display: "grid",
            gridTemplateColumns: "36px 1fr 116px",
            alignItems: "center",
            gap: "var(--space-2)",
            fontSize: "var(--fs-small)",
          }}
        >
          <span style={{ fontWeight: 600 }}>{zone.zone}</span>
          <div
            style={{
              height: 16,
              background: "var(--surface-sunken)",
              borderRadius: 3,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${(zone.pct / max) * 100}%`,
                height: "100%",
                background: "var(--series-1)",
                opacity: 0.35 + 0.65 * (zone.pct / max),
                borderRadius: 3,
              }}
            />
          </div>
          <span className="tabular muted" style={{ textAlign: "right" }}>
            {num(zone.pct, 1)}% · {Math.round(zone.seconds / 60)} min
          </span>
        </div>
      ))}
      <p className="card-subtitle" style={{ margin: "var(--space-1) 0 0" }}>
        Limites em {unit}
      </p>
    </div>
  )
}
