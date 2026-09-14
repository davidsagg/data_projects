/*
 * Cliente da API do VeloDNA.
 *
 * Um único lugar conhece os nomes dos endpoints e dos campos. A versão anterior
 * espalhava chamadas axios pelos componentes, e quando o schema mudou de
 * `activity_id`/`start_time` para `id`/`started_at` todos quebraram de uma vez.
 */
import axios from "axios"

const client = axios.create({ baseURL: "/api", timeout: 30000 })

/** Devolve os dados da resposta, ou um valor padrão quando o recurso não existe. */
async function get(path, { params, fallback } = {}) {
  try {
    const response = await client.get(path, { params })
    return response.data
  } catch (error) {
    if (fallback !== undefined && error.response?.status === 404) return fallback
    throw error
  }
}

export const api = {
  activities: {
    list: (params) => get("/activities/", { params, fallback: [] }),
    latest: () => get("/activities/latest", { fallback: null }),
    streams: (id, everyN = 6) =>
      get(`/activities/${id}/streams`, { params: { every_n: everyN }, fallback: [] }),
    zoneDistribution: (id) =>
      get(`/activities/${id}/zone-distribution`, { fallback: null }),
    powerCurve: (id) =>
      get(`/activities/${id}/power-curve`, { fallback: [] }),
  },

  fitness: {
    pmc: () => get("/pmc", { fallback: [] }),
    powerCurve: (params) => get("/power-curve", { params, fallback: [] }),
    criticalPower: (params) => get("/critical-power", { params, fallback: null }),
    ftpHistory: () => get("/ftp-history", { fallback: [] }),
    efficiency: (params) => get("/efficiency", { params, fallback: [] }),
    decoupling: (params) => get("/decoupling", { params, fallback: null }),
    zones: (params) => get("/zones/definitions", { params, fallback: null }),
  },

  health: {
    daily: (days = 30) => get("/health-daily", { params: { days }, fallback: [] }),
    readiness: () => get("/readiness/today", { fallback: null }),
    alerts: () => get("/health/alerts", { fallback: [] }),
    sleepCorrelation: (params) =>
      get("/health/sleep-correlation", { params, fallback: null }),
  },

  segments: {
    list: () => get("/segments", { fallback: [] }),
    efforts: (id) => get(`/segments/${id}/efforts`, { fallback: null }),
    create: (body) => client.post("/segments", body).then((r) => r.data),
    rescan: (id) => client.post(`/segments/${id}/rescan`).then((r) => r.data),
    remove: (id) => client.delete(`/segments/${id}`).then((r) => r.data),
  },

  coach: {
    chat: (body) => client.post("/coach/chat", body).then((r) => r.data),
    history: (sessionId) => get(`/coach/chat/${sessionId}`, { fallback: [] }),
    sessions: () => get("/coach/chat-sessions", { fallback: [] }),
  },

  training: {
    week: (params) => get("/week", { params, fallback: null }),
    weeks: (params) => get("/weeks", { params, fallback: [] }),
    intervals: (id, params) =>
      get(`/activities/${id}/intervals`, { params, fallback: null }),
    wbal: (id, params) => get(`/activities/${id}/wbal`, { params, fallback: null }),
    durability: (id, params) =>
      get(`/activities/${id}/durability`, { params, fallback: null }),
  },

  planning: {
    calendar: (params) => get("/calendar", { params, fallback: null }),
    projection: (body) =>
      client.post("/planning/projection", body).then((r) => r.data),
    addWorkout: (body) =>
      client.post("/planning/workouts", body).then((r) => r.data),
    reconcile: () => client.post("/planning/reconcile").then((r) => r.data),
  },
}
