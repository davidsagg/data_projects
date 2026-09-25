/*
 * Número protagonista — um por tela, nunca dois.
 *
 * Sem card, sem borda, sem fundo: fica solto no espaço da página. É o que
 * estabelece a hierarquia da tela inteira, e cercá-lo de moldura o rebaixaria
 * ao mesmo nível dos cards que vêm depois.
 */
import { num } from "../../lib/format"

export default function HeroNumber({
  value,
  unit,
  label,
  delta,
  deltaLabel,
  statusToken,
  context,
}) {
  const hasDelta = delta !== null && delta !== undefined && Number.isFinite(delta)

  return (
    <div style={{ display: "grid", gap: "var(--space-3)" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-3)" }}>
        <span
          className="figure figure-hero tabular"
          style={statusToken ? { color: `var(${statusToken})` } : undefined}
        >
          {value}
        </span>
        {unit && (
          <span style={{ fontSize: "var(--fs-lead)", color: "var(--text-secondary)" }}>
            {unit}
          </span>
        )}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: "var(--space-5)",
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontSize: "var(--fs-body)", color: "var(--text-secondary)" }}>
          {label}
        </span>
        {hasDelta && (
          <span
            className="tabular"
            style={{ fontSize: "var(--fs-small)", color: "var(--text-secondary)" }}
          >
            {/* A seta é redundante com o sinal — e é o que sobrevive em escala
                de cinza, onde a cor não diferencia nada. */}
            {delta > 0 ? "▲" : delta < 0 ? "▼" : "—"} {num(Math.abs(delta), 1)}%{" "}
            {deltaLabel}
          </span>
        )}
      </div>

      {context && (
        <p
          style={{
            margin: 0,
            fontSize: "var(--fs-body)",
            color: "var(--text-secondary)",
          }}
        >
          {context}
        </p>
      )}
    </div>
  )
}
