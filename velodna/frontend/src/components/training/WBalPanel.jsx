/*
 * Painel do W'bal — busca o balanço e delega o desenho ao gráfico.
 *
 * Some da tela em silêncio quando não há CP e W' registrados ou quando a
 * atividade não tem potência: nesses casos a API responde 422, e um aviso
 * permanente sobre uma métrica que o atleta talvez nunca vá usar só faria
 * ruído. O caminho para habilitá-la está no CLAUDE.md e no próprio erro da API.
 */
import { useEffect, useState } from "react"

import WBalChart from "./WBalChart"
import { api } from "../../lib/api"

export default function WBalPanel({ activityId, elapsedTimeS }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!activityId) return undefined
    let cancelled = false
    setData(null)

    api.training
      .wbal(activityId)
      .then((result) => !cancelled && setData(result))
      .catch(() => !cancelled && setData(null))

    return () => {
      cancelled = true
    }
  }, [activityId])

  if (!data) return null

  return <WBalChart data={data} elapsedTimeS={elapsedTimeS} />
}
