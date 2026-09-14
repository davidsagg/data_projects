import { useEffect, useState } from "react"

/**
 * Lê custom properties CSS do documento.
 *
 * O Recharts precisa de cores como string — não aceita `var(--series-1)` em
 * atributos SVG. Ler os tokens aqui mantém uma única fonte da verdade no CSS e
 * ainda acompanha a troca de tema.
 *
 * O valor inicial vem da inicialização preguiçosa do estado, não de um efeito:
 * chamar `setState` no corpo do efeito provocaria uma segunda renderização
 * imediata em todo gráfico da tela. O efeito existe só para assinar mudanças.
 */

/**
 * Lê os tokens informados do elemento raiz.
 *
 * @param {string[]} tokens Nomes das variáveis, com os dois hifens.
 * @returns {Object} Mapa {token: valor}.
 */
function readTokens(tokens) {
  if (typeof document === "undefined") return {}
  const styles = getComputedStyle(document.documentElement)
  return Object.fromEntries(
    tokens.map((token) => [token, styles.getPropertyValue(token).trim()]),
  )
}

/**
 * Assina as duas formas de troca de tema: o atributo no `<html>` (alternador
 * do usuário) e a preferência do sistema.
 *
 * @param {() => void} onChange Chamado a cada mudança.
 * @returns {() => void} Função de cancelamento.
 */
function subscribeToTheme(onChange) {
  const observer = new MutationObserver(onChange)
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  })

  const media = window.matchMedia("(prefers-color-scheme: dark)")
  media.addEventListener("change", onChange)

  return () => {
    observer.disconnect()
    media.removeEventListener("change", onChange)
  }
}

/**
 * Lê vários tokens de uma vez.
 *
 * @param {string[]} tokens Nomes das variáveis.
 * @returns {Object} Mapa {token: valor}.
 */
export function useCssVars(tokens) {
  const key = tokens.join(",")
  const [values, setValues] = useState(() => readTokens(tokens))

  useEffect(() => {
    const update = () => setValues(readTokens(key.split(",")))
    update()
    return subscribeToTheme(update)
  }, [key])

  return values
}

/**
 * Lê uma única custom property.
 *
 * @param {string|null} token Nome da variável, com os dois hifens.
 * @returns {string|null} Valor resolvido, ou null quando não há token.
 */
export function useCssVar(token) {
  const values = useCssVars(token ? [token] : [])
  return token ? values[token] || null : null
}
