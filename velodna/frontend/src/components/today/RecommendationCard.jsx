/*
 * O que os sinais do dia sugerem treinar.
 *
 * Os sinais que produziram a leitura ficam à vista, e não é enfeite:
 * recomendação sem os sinais é palpite com cara de resultado. O atleta precisa
 * poder discordar dela sabendo do quê — se ele sabe que dormiu mal por um motivo
 * pontual, a leitura muda, e só dá para perceber isso com os insumos expostos.
 */
import { num } from "../../lib/format"

const INTENSITY_TOKEN = {
  recuperação: "--status-critical",
  "leve ou descanso": "--status-warning",
  endurance: null,
  "endurance longo": null,
  intervalado: "--status-good",
}

export default function RecommendationCard({ recommendation, week }) {
  if (!recommendation) return null

  const token = INTENSITY_TOKEN[recommendation.intensity]

  return (
    <section
      className="card card--static"
      style={{
        display: "grid",
        gap: "var(--space-2)",
        alignContent: "start",
        borderLeft: `3px solid var(${token || "--accent"})`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "var(--space-4)",
          flexWrap: "wrap",
        }}
      >
        <h2 className="card-title">Hoje sugere</h2>
        <span
          style={{
            fontSize: "var(--fs-small)",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            color: "var(--text-secondary)",
          }}
        >
          <span
            className="viz-swatch"
            style={{
              background: `var(${token || "--text-tertiary"})`,
              borderRadius: "50%",
            }}
          />
          {recommendation.intensity}
        </span>
      </div>

      <strong style={{ fontFamily: "var(--font-display)", fontSize: "1.0625rem" }}>
        {recommendation.headline}
      </strong>

      <p
        style={{
          margin: 0,
          fontSize: "var(--fs-small)",
          lineHeight: 1.5,
          color: "var(--text-secondary)",
        }}
      >
        {recommendation.detail}
      </p>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "var(--space-1) var(--space-2)",
          paddingTop: "var(--space-2)",
          borderTop: "1px solid var(--border-subtle)",
        }}
      >
        {recommendation.signals.map((signal) => (
          <span
            key={signal}
            className="tabular"
            style={{
              fontSize: "var(--fs-micro)",
              color: "var(--text-tertiary)",
              background: "var(--surface-sunken)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-sm)",
              padding: "2px var(--space-3)",
            }}
          >
            {signal}
          </span>
        ))}
        {week?.baseline_tss > 0 && (
          <span
            className="tabular"
            style={{
              fontSize: "var(--fs-micro)",
              color: "var(--text-tertiary)",
              background: "var(--surface-sunken)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-sm)",
              padding: "2px var(--space-3)",
            }}
          >
            {num(week.total_tss, 0)} de {num(week.baseline_tss, 0)} TSS na semana
          </span>
        )}
      </div>
    </section>
  )
}
