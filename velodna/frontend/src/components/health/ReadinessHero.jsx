/*
 * Cartão de prontidão do dia.
 *
 * O score é um número só, então é um número — não um medidor circular, que
 * gasta muito espaço para comunicar a mesma coisa com menos precisão.
 *
 * A recomendação vem do backend e é o que realmente se lê: o número sozinho
 * não diz o que fazer, e a cor sozinha não pode carregar o significado.
 */
import { num } from "../../lib/format"
import { useCssVar } from "../../lib/useCssVar"

/** Faixas de prontidão e o token de estado correspondente. */
function readinessBand(score) {
  if (score === null || score === undefined) return { label: "Sem dados", token: null }
  if (score >= 75) return { label: "Pronto", token: "--status-good" }
  if (score >= 55) return { label: "Moderado", token: null }
  if (score >= 40) return { label: "Cansado", token: "--status-warning" }
  return { label: "Muito cansado", token: "--status-critical" }
}

export default function ReadinessHero({ readiness, health }) {
  const band = readinessBand(readiness?.score)
  const color = useCssVar(band.token)

  return (
    <section
      className="card"
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(160px, auto) 1fr",
        gap: "var(--space-5)",
        alignItems: "center",
      }}
    >
      <div>
        <h2 className="card-title">Prontidão de hoje</h2>
        <div
          className="figure figure-hero"
          style={{ fontSize: 56, color: color || "var(--text-primary)" }}
        >
          {num(readiness?.score, 0)}
        </div>
        <span
          style={{
            fontSize: "var(--fs-small)",
            fontWeight: 600,
            color: color || "var(--text-secondary)",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          {color && (
            <span
              className="viz-swatch"
              style={{ background: color, borderRadius: "50%" }}
            />
          )}
          {band.label}
        </span>
      </div>

      <div style={{ display: "grid", gap: "var(--space-3)", minWidth: 0 }}>
        <p
          style={{
            margin: 0,
            fontSize: "var(--fs-lead)",
            lineHeight: 1.45,
            color: "var(--text-primary)",
          }}
        >
          {readiness?.recommendation || "Sem recomendação para hoje."}
        </p>
        {health && (
          <dl
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(96px, 1fr))",
              gap: "var(--space-3)",
              margin: 0,
            }}
          >
            {[
              ["HRV", health.hrv_rmssd_ms, "ms", 0],
              ["FC repouso", health.resting_hr_bpm, "bpm", 0],
              ["Sono", health.sleep_hours, "h", 1],
              ["Body battery", health.body_battery, "", 0],
              ["Estresse", health.stress_level, "", 0],
            ].map(([label, value, unit, digits]) => (
              <div key={label}>
                <dt
                  style={{
                    fontSize: "var(--fs-micro)",
                    color: "var(--text-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "0.03em",
                  }}
                >
                  {label}
                </dt>
                <dd
                  className="tabular"
                  style={{
                    margin: 0,
                    fontSize: "var(--fs-lead)",
                    fontWeight: 600,
                  }}
                >
                  {num(value, digits)}
                  {unit && <span className="unit">{unit}</span>}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  )
}
