/*
 * Estado de erro — o que a tela mostra quando a API não responde.
 *
 * A versão anterior despejava `AxiosError: Request failed with status code 502`
 * na cara do usuário. Isso não é mensagem de erro, é vazamento de stack: não diz
 * o que aconteceu nem o que fazer. Aqui cada tipo de falha vira uma frase e,
 * quando existe, o comando que resolve.
 */
export default function ErrorState({ error, onRetry }) {
  const kind = error?.kind
  const message = error?.message || String(error)
  const isDown = kind === "api-down" || kind === "unreachable"

  return (
    <div className="page">
      <section
        className="card card--static"
        style={{ display: "grid", gap: "var(--space-5)", maxWidth: 620 }}
      >
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          <span className="label" style={{ color: "var(--status-warning)" }}>
            {isDown ? "Servidor fora do ar" : "Erro"}
          </span>
          <p style={{ margin: 0, fontSize: "var(--fs-lead)" }}>{message}</p>
        </div>

        {isDown && (
          <p
            style={{
              margin: 0,
              fontSize: "var(--fs-body)",
              color: "var(--text-secondary)",
            }}
          >
            O DuckDB aceita um escritor só, então a API costuma ser parada para
            rodar um script de sincronização. Se foi o caso, é só subi-la de volta
            quando o script terminar.
          </p>
        )}

        {error?.hint && (
          <code
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "var(--fs-small)",
              background: "var(--surface-sunken)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-sm)",
              padding: "var(--space-3) var(--space-4)",
              color: "var(--text-primary)",
            }}
          >
            {error.hint}
          </code>
        )}

        {onRetry && (
          <div>
            <button
              className="segmented"
              onClick={onRetry}
              style={{ padding: "var(--space-2) var(--space-5)", cursor: "pointer" }}
            >
              tentar de novo
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
