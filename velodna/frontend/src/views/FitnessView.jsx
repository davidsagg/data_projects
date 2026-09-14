/*
 * Visão Fitness — o estado de forma do atleta e como ele chegou aqui.
 *
 * Ordem de leitura: os números do momento no topo, depois o PMC (que explica
 * como se chegou neles), depois as capacidades (curva de potência, FTP) e por
 * fim a eficiência, que é a leitura mais lenta e de longo prazo.
 */
import { useEffect, useState } from "react"

import PMCChart from "../components/fitness/PMCChart"
import PowerCurveChart from "../components/fitness/PowerCurveChart"
import FTPHistoryChart from "../components/fitness/FTPHistoryChart"
import EfficiencyChart from "../components/fitness/EfficiencyChart"
import StatTile from "../components/viz/StatTile"
import ExportPanel from "../components/ExportPanel"
import { api } from "../lib/api"
import { formState, num } from "../lib/format"

export default function FitnessView({ athleteWeightKg }) {
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    let cancelled = false

    Promise.all([
      api.fitness.pmc(),
      api.fitness.powerCurve(),
      api.fitness.criticalPower({ days: 365 }),
      api.fitness.ftpHistory(),
      api.fitness.efficiency(),
      api.fitness.zones(),
    ])
      .then(([pmc, curve, cp, ftpHistory, efficiency, zones]) => {
        if (cancelled) return
        setState({ loading: false, pmc, curve, cp, ftpHistory, efficiency, zones })
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error: String(error) })
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (state.loading) return <p className="muted">Carregando…</p>
  if (state.error)
    return <p style={{ color: "var(--status-critical)" }}>Erro: {state.error}</p>

  const latest = state.pmc?.[state.pmc.length - 1]
  const form = formState(latest?.tsb)
  const ftp = state.zones?.ftp_w

  const rampRate = computeRampRate(state.pmc)

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        <StatTile
          label="Fitness · CTL"
          value={num(latest?.ctl, 1)}
          context={rampRate !== null ? `${rampRate > 0 ? "+" : ""}${num(rampRate, 1)}/semana` : null}
          statusToken={rampRate > 7 ? "--status-warning" : null}
          hero
        />
        <StatTile label="Fadiga · ATL" value={num(latest?.atl, 1)} hero />
        <StatTile
          label="Forma · TSB"
          value={num(latest?.tsb, 1)}
          context={form.label}
          statusToken={form.token}
          hero
        />
        <StatTile label="FTP" value={num(ftp)} unit="W" hero />
        {athleteWeightKg && ftp && (
          <StatTile
            label="Relação peso-potência"
            value={num(ftp / athleteWeightKg, 2)}
            unit="W/kg"
            hero
          />
        )}
      </div>

      <PMCChart data={state.pmc} />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        <PowerCurveChart
          curve={state.curve}
          cp={state.cp}
          weightKg={athleteWeightKg}
        />
        <FTPHistoryChart history={state.ftpHistory} />
      </div>

      <EfficiencyChart activities={state.efficiency} />
      <ExportPanel />
    </div>
  )
}

/** Variação de CTL por semana nas últimas quatro semanas. */
function computeRampRate(pmc) {
  if (!pmc || pmc.length < 29) return null
  const last = pmc[pmc.length - 1]?.ctl
  const previous = pmc[pmc.length - 29]?.ctl
  if (last === null || previous === null) return null
  return (last - previous) / 4
}
