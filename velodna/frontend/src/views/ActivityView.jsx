/*
 * Visão Atividade — detalhe de um treino, ou comparação de até três.
 *
 * A mesma tela cobre os dois casos porque a diferença é só quantas atividades
 * estão selecionadas. Separar em duas telas obrigaria o usuário a decidir antes
 * de olhar o que existe.
 */
import { useEffect, useState } from "react"

import ActivityPicker, { MAX_COMPARE } from "../components/activity/ActivityPicker"
import ActivityDetail from "../components/activity/ActivityDetail"
import ActivityCompare from "../components/activity/ActivityCompare"
import DayContext from "../components/activity/DayContext"
import IntervalPanel from "../components/training/IntervalPanel"
import ClimbPanel from "../components/training/ClimbPanel"
import PacingPanel from "../components/training/PacingPanel"
import LoadDensityChart from "../components/training/LoadDensityChart"
import WBalPanel from "../components/training/WBalPanel"
import DurabilityPanel from "../components/training/DurabilityPanel"
import { api } from "../lib/api"

export default function ActivityView({ initialActivity }) {
  const [activities, setActivities] = useState(null)
  const [selected, setSelected] = useState([])
  const [data, setData] = useState({ streams: {}, curves: {}, zones: {} })

  useEffect(() => {
    api.activities
      .list()
      .then((list) => {
        setActivities(list)
        // Quando se chega pelo drawer da semana, a atividade escolhida lá é a
        // que abre aqui — trocar de tela não pode custar a seleção.
        const preferred =
          (initialActivity && list.find((a) => a.id === initialActivity.id)) ||
          [...list].sort((a, b) => (a.started_at < b.started_at ? 1 : -1))[0]
        if (preferred) setSelected([preferred])
      })
      .catch(() => setActivities([]))
  }, [])

  // Busca só o que ainda falta: alternar a seleção não deve refazer o que já
  // está em memória.
  useEffect(() => {
    const missing = selected.filter((a) => !data.streams[a.id])
    if (!missing.length) return

    let cancelled = false

    Promise.all(
      missing.map((activity) =>
        Promise.all([
          api.activities.streams(activity.id, 5),
          api.activities.zoneDistribution(activity.id),
          api.activities.powerCurve(activity.id),
        ]).then(([streams, zones, curve]) => ({
          id: activity.id,
          streams,
          zones,
          curve,
        })),
      ),
    )
      .then((results) => {
        if (cancelled) return
        setData((previous) => {
          const next = {
            streams: { ...previous.streams },
            zones: { ...previous.zones },
            curves: { ...previous.curves },
          }
          results.forEach((r) => {
            next.streams[r.id] = r.streams
            next.zones[r.id] = r.zones
            next.curves[r.id] = r.curve
          })
          return next
        })
      })

    return () => {
      cancelled = true
    }
  }, [selected, data.streams])

  const toggle = (activity) => {
    setSelected((current) => {
      const exists = current.some((a) => a.id === activity.id)
      if (exists) {
        const next = current.filter((a) => a.id !== activity.id)
        return next.length ? next : current // nunca deixa a seleção vazia
      }
      if (current.length >= MAX_COMPARE) return [...current.slice(1), activity]
      return [...current, activity]
    })
  }

  if (activities === null) return <p className="muted">Carregando…</p>
  if (!activities.length) return <p className="muted">Nenhuma atividade no catálogo.</p>

  // Derivado, não guardado em estado: um `setState` no corpo do efeito
  // provocaria uma renderização extra a cada troca de seleção.
  const ready = selected.every((a) => data.streams[a.id] !== undefined)

  return (
    <div
      className="page"
      style={{
        gridTemplateColumns: "minmax(280px, 340px) minmax(0, 1fr)",
        gap: "var(--card-gap)",
        alignItems: "start",
      }}
    >
      <ActivityPicker
        activities={activities}
        selected={selected}
        onToggle={toggle}
      />

      <div style={{ minWidth: 0 }}>
        {!ready && <p className="muted">Carregando atividade…</p>}
        {ready && selected.length === 1 && (
          <div style={{ display: "grid", gap: "var(--space-4)" }}>
            <ActivityDetail
              activity={selected[0]}
              streams={data.streams[selected[0].id]}
              zones={data.zones[selected[0].id]}
              highlight={
                // O W'bal sobre o percurso é a leitura principal do treino:
                // onde o gás acabou. Vem antes do mapa e das curvas.
                <WBalPanel
                  activityId={selected[0].id}
                  elapsedTimeS={selected[0].elapsed_time_s}
                />
              }
            />
            {/* Análises avançadas: cada painel busca o que precisa e se
                esconde quando a atividade não sustenta a métrica. */}
            <DayContext activity={selected[0]} />
            <IntervalPanel activityId={selected[0].id} />
            <PacingPanel activityId={selected[0].id} />
            <ClimbPanel activityId={selected[0].id} />
            <DurabilityPanel activityId={selected[0].id} />
            <LoadDensityChart activityId={selected[0].id} />
          </div>
        )}
        {ready && selected.length > 1 && (
          <ActivityCompare
            activities={selected}
            curves={data.curves}
            zones={data.zones}
          />
        )}
      </div>
    </div>
  )
}
