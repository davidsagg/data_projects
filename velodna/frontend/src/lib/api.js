/*
 * Cliente da API do VeloDNA.
 *
 * Um único lugar conhece os nomes dos endpoints e dos campos. A versão anterior
 * espalhava chamadas axios pelos componentes, e quando o schema mudou de
 * `activity_id`/`start_time` para `id`/`started_at` todos quebraram de uma vez.
 */
import axios from "axios"

const client = axios.create({ baseURL: "/api", timeout: 30000 })

/**
 * Erro de API já classificado, com mensagem que diz o que fazer.
 *
 * O usuário não deve ler "AxiosError: Request failed with status code 502". Um
 * 502 aqui quase sempre significa uma coisa específica e recuperável: o proxy do
 * Vite está de pé mas a API caiu — tipicamente porque foi parada para liberar o
 * banco para um script de escrita, já que o DuckDB aceita um escritor só.
 */
export class ApiError extends Error {
  constructor(message, { kind, status, hint, cause } = {}) {
    super(message)
    this.name = "ApiError"
    this.kind = kind
    this.status = status
    this.hint = hint
    this.cause = cause
  }
}

const API_DOWN_HINT = "make api"

/** Traduz a falha do axios em algo que o usuário consiga agir. */
function classify(error) {
  const status = error.response?.status

  if (status === 502 || status === 503 || status === 504) {
    return new ApiError("A API não está respondendo.", {
      kind: "api-down",
      status,
      hint: API_DOWN_HINT,
      cause: error,
    })
  }

  if (!error.response) {
    // Sem resposta alguma: ou o dev server caiu, ou a rede sumiu no caminho.
    return new ApiError("Não foi possível falar com o servidor.", {
      kind: "unreachable",
      hint: API_DOWN_HINT,
      cause: error,
    })
  }

  if (status >= 500) {
    return new ApiError("A API encontrou um erro interno.", {
      kind: "server",
      status,
      hint: "Confira o log do uvicorn.",
      cause: error,
    })
  }

  const detail = error.response?.data?.detail
  return new ApiError(detail || `Requisição recusada (HTTP ${status}).`, {
    kind: "request",
    status,
    cause: error,
  })
}

/** Devolve os dados da resposta, ou um valor padrão quando o recurso não existe. */
async function get(path, { params, fallback } = {}) {
  try {
    const response = await client.get(path, { params })
    return response.data
  } catch (error) {
    if (fallback !== undefined && error.response?.status === 404) return fallback
    throw classify(error)
  }
}

/** Mesma classificação para os verbos de escrita. */
async function send(method, path, body) {
  try {
    const response = await client[method](path, body)
    return response.data
  } catch (error) {
    throw classify(error)
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



  training: {
    week: (params) => get("/week", { params, fallback: null }),
    weeks: (params) => get("/weeks", { params, fallback: [] }),
    intervals: (id, params) =>
      get(`/activities/${id}/intervals`, { params, fallback: null }),
    wbal: (id, params) => get(`/activities/${id}/wbal`, { params, fallback: null }),
    durability: (id, params) =>
      get(`/activities/${id}/durability`, { params, fallback: null }),
  },

  today: () => get("/today", { fallback: null }),

  analysis: {
    climbs: (id, params) => get(`/activities/${id}/climbs`, { params, fallback: null }),
    pacing: (id) => get(`/activities/${id}/pacing`, { fallback: null }),
    loadDensity: (id, params) =>
      get(`/activities/${id}/load-density`, { params, fallback: null }),
    capacityProfile: (params) =>
      get("/capacity-profile", { params, fallback: null }),
  },

  feedback: {
    list: (params) => get("/feedback", { params, fallback: [] }),
    forActivity: (id) => get(`/activities/${id}/feedback`, { fallback: null }),
    save: (body) => send("put", "/feedback", body),
    remove: (id) => send("delete", `/feedback/${id}`),
  },


  panorama: (params) => get("/panorama", { params, fallback: null }),

  goals: {
    list: () => get("/goals", { fallback: [] }),
    metrics: () => get("/goals/metrics", { fallback: [] }),
    save: (body) => send("put", "/goals", body),
    remove: (metric) => send("delete", `/goals/${metric}`),
  },

  milestones: {
    list: (params) => get("/milestones", { params, fallback: [] }),
    create: (body) => send("post", "/milestones", body),
    remove: (id) => send("delete", `/milestones/${id}`),
  },
}
