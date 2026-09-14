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
import IntervalPanel from "../components/training/IntervalPanel"
import WBalPanel from "../components/training/WBalPanel"
import DurabilityPanel from "../components/training/DurabilityPanel"
import { api } from "../lib/api"

export default function ActivityView() {
  const [activities, setActivities] = useState(null)
  const [selected, setSelected] = useState([])
  const [data, setData] = useState({ streams: {}, curves: {}, zones: {} })

  useEffect(() => {
    api.activities
      .list()
      .then((list) => {
        setActivities(list)
        const latest = [...list].sort((a, b) =>
          a.started_at < b.started_at ? 1 : -1,
        )[0]
        if (latest) setSelected([latest])
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
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(300px, 380px) minmax(0, 1fr)",
        gap: "var(--space-4)",
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
            />
            {/* Análises avançadas: cada painel busca o que precisa e se
                esconde quando a atividade não sustenta a métrica. */}
            <IntervalPanel activityId={selected[0].id} />
            <WBalPanel
              activityId={selected[0].id}
              elapsedTimeS={selected[0].elapsed_time_s}
            />
            <DurabilityPanel activityId={selected[0].id} />
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
