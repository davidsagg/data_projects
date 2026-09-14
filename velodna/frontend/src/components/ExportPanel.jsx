/*
 * Exportação de dados em CSV (US-05).
 *
 * Links diretos, não requisições via JavaScript: o navegador já sabe baixar um
 * arquivo com `Content-Disposition`, e passar pelo `fetch` obrigaria a montar o
 * blob inteiro em memória — justamente o que o streaming no backend evita.
 */
const EXPORTS = [
  {
    href: "/api/export/activities.csv",
    label: "Atividades",
    note: "Uma linha por treino, com NP, IF, VI, TSS e origem do TSS",
  },
  {
    href: "/api/export/training-load.csv",
    label: "Carga de treino",
    note: "Série diária de CTL, ATL, TSB e TSS",
  },
  {
    href: "/api/export/health.csv",
    label: "Saúde",
    note: "HRV, sono, FC de repouso, body battery e estresse por dia",
  },
  {
    href: "/api/export/power-curve.csv",
    label: "Curva de potência",
    note: "Melhor esforço por duração e a data em que foi alcançado",
  },
]

export default function ExportPanel({ activityId }) {
  const items = activityId
    ? [
        ...EXPORTS,
        {
          href: `/api/export/activities/${activityId}/streams.csv`,
          label: "Streams da atividade selecionada",
          note: "Série temporal segundo a segundo, com GPS",
        },
      ]
    : EXPORTS

  return (
    <section className="card">
      <h2 className="card-title">Exportar dados</h2>
      <p className="card-subtitle">
        Arquivos CSV com nomes de coluna legíveis e unidades convertidas
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        {items.map((item) => (
          <a
            key={item.href}
            href={item.href}
            download
            style={{
              display: "grid",
              gap: 2,
              padding: "var(--space-3)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
              background: "var(--surface-sunken)",
              color: "var(--text-primary)",
              textDecoration: "none",
            }}
          >
            <span style={{ fontWeight: 600, fontSize: "var(--fs-body)" }}>
              ↓ {item.label}
            </span>
            <span
              className="muted"
              style={{ fontSize: "var(--fs-micro)", lineHeight: 1.4 }}
            >
              {item.note}
            </span>
          </a>
        ))}
      </div>
    </section>
  )
}
