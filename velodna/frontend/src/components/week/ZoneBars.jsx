/*
 * Distribuição de tempo por zona — barras horizontais.
 *
 * Nunca pizza: comparar ângulos é pior que comparar comprimentos, e sete fatias
 * de pizza são ilegíveis. A rampa é sequencial de um hue porque zonas são
 * ordinais — mais escuro é mais intenso, e o olho lê a ordem sem legenda.
 */
import { num } from "../../lib/format"

const ZONE_LABELS = {
  Z1: "Recuperação",
  Z2: "Endurance",
  Z3: "Tempo",
  Z4: "Limiar",
  Z5: "VO2máx",
  Z6: "Anaeróbico",
  Z7: "Neuromuscular",
}

/* Rampa sequencial: Z1 claro, Z7 escuro. */
const ZONE_TOKEN = {
  Z1: "--seq-100",
  Z2: "--seq-250",
  Z3: "--seq-400",
  Z4: "--seq-550",
  Z5: "--seq-700",
  Z6: "--seq-700",
  Z7: "--seq-700",
}

export default function ZoneBars({ zoneSeconds }) {
  const entries = Object.entries(zoneSeconds || {})
  const total = entries.reduce((sum, [, seconds]) => sum + seconds, 0)

  if (total === 0) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        Sem dados de potência nesta semana.
      </p>
    )
  }

  // Zonas altas quase sempre têm fração pequena; a escala é relativa ao maior
  // valor, senão Z5–Z7 viram traços indistinguíveis.
  const max = Math.max(...entries.map(([, s]) => s))

  return (
    <div style={{ display: "grid", gap: "var(--space-3)" }}>
      {entries.map(([zone, seconds]) => {
        const pct = (seconds / total) * 100
        return (
          <div
            key={zone}
            style={{
              display: "grid",
              gridTemplateColumns: "92px 1fr 96px",
              alignItems: "center",
              gap: "var(--space-4)",
              fontSize: "var(--fs-small)",
            }}
          >
            <span style={{ color: "var(--text-secondary)" }}>
              <strong style={{ color: "var(--text-primary)" }}>{zone}</strong>{" "}
              {ZONE_LABELS[zone]}
            </span>

            <div
              style={{
                height: 10,
                background: "var(--surface-sunken)",
                borderRadius: "var(--radius-sm)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${(seconds / max) * 100}%`,
                  height: "100%",
                  background: `var(${ZONE_TOKEN[zone]})`,
                  borderRadius: "var(--radius-sm)",
                }}
              />
            </div>

            <span
              className="tabular"
              style={{ textAlign: "right", color: "var(--text-secondary)" }}
            >
              {num(pct, 1)}% · {Math.round(seconds / 60)} min
            </span>
          </div>
        )
      })}
    </div>
  )
}
