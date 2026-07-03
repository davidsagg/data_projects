#!/usr/bin/env bash
#
# setup_local.sh — prepara os projetos para desenvolvimento LOCAL (sem DevContainer)
#
# O que faz, por projeto:
#   1. cria um virtualenv isolado com a versão de Python correta (via uv)
#   2. instala as dependências (requirements.txt ou pyproject.toml)
#   3. cria .env a partir de .env.example (se ainda não existir) e aponta o Ollama p/ localhost
#   4. (opcional) roda `npm install` nos frontends
#
# Uso:
#   ./setup_local.sh                 # todos os projetos
#   ./setup_local.sh bandkit velodna # apenas alguns
#
# Requisitos: uv (https://astral.sh/uv). Node/npm apenas para os frontends. Ollama nativo p/ IA local.
# sem 'set -e': a falha de um projeto NÃO deve abortar os demais (rastreamos em FAILED)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "❌ 'uv' não encontrado. Instale com:"
  echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

echo "▶ Instalando as versões de Python usadas pelos projetos (3.11 e 3.12)…"
uv python install 3.11 3.12

# Formato: nome|pyver|tipo(req|pyproject)|caminho_deps|venvdir|extras
PROJECTS=(
  "bandkit|3.11|req|backend/requirements.txt|backend/.venv|-"
  "crypto_advisor|3.12|pyproject|-|.venv|[dev]"
  "ficadica|3.12|req|requirements.txt|.venv|-"
  "job_scout|3.11|req|requirements.txt|.venv|-"
  "musicdna-ai|3.11|req|requirements.txt|.venv|-"
  "saggirag|3.11|req|requirements.txt|.venv|-"
  "special_gear|3.11|req|requirements.txt|.venv|-"
  "trend-radar|3.11|req|requirements.txt|.venv|-"
  "velodna|3.11|pyproject|-|.venv|-"
)

SELECTED=("$@")   # projetos escolhidos na linha de comando (vazio = todos)
FAILED=()         # projetos cuja instalação de deps falhou

for entry in "${PROJECTS[@]}"; do
  IFS='|' read -r name pyver deptype deppath venvdir extras <<< "$entry"
  if [ "${#SELECTED[@]}" -gt 0 ]; then
    skip=1; for s in "${SELECTED[@]}"; do [ "$s" = "$name" ] && skip=0; done
    [ "$skip" -eq 1 ] && continue
  fi

  proj="$ROOT/$name"
  echo ""
  echo "──────── $name (Python $pyver) ────────"
  [ -d "$proj" ] || { echo "  ⚠ pasta não existe, pulando"; continue; }

  venvpy="$proj/$venvdir/bin/python"
  echo "  • criando venv em $venvdir"
  uv venv --python "$pyver" "$proj/$venvdir" >/dev/null

  if [ "$deptype" = "pyproject" ]; then
    ext=""; [ "$extras" != "-" ] && ext="$extras"
    echo "  • instalando deps (pyproject${ext})"
    if ( cd "$proj" && uv pip install --python "$venvpy" -e ".${ext}" >/dev/null ); then
      :
    else
      echo "  ⚠ FALHA ao instalar deps de $name"; FAILED+=("$name"); continue
    fi
  else
    if [ -f "$proj/$deppath" ]; then
      echo "  • instalando deps ($deppath)"
      if uv pip install --python "$venvpy" -r "$proj/$deppath" >/dev/null; then
        :
      else
        echo "  ⚠ FALHA ao instalar deps de $name"; FAILED+=("$name"); continue
      fi
    else
      echo "  ⚠ deps não encontradas em $deppath"
    fi
  fi

  if [ -f "$proj/.env.example" ] && [ ! -f "$proj/.env" ]; then
    cp "$proj/.env.example" "$proj/.env"
    # aponta o Ollama para localhost (fora do container não existe host.docker.internal)
    sed -i.bak 's/host\.docker\.internal/localhost/g' "$proj/.env" 2>/dev/null && rm -f "$proj/.env.bak"
    echo "  • .env criado a partir do exemplo → PREENCHA os segredos reais"
  fi
  echo "  ✓ pronto"
done

# ── Frontends (Node) ────────────────────────────────────────────────
if command -v npm >/dev/null 2>&1; then
  for fe in bandkit/frontend saggirag/frontend velodna/frontend; do
    if [ -d "$ROOT/$fe" ] && { [ "${#SELECTED[@]}" -eq 0 ] || printf '%s\n' "${SELECTED[@]}" | grep -q "^${fe%%/*}$"; }; then
      echo ""
      echo "──────── $fe (npm install) ────────"
      ( cd "$ROOT/$fe" && npm install --silent ) && echo "  ✓ pronto"
    fi
  done
else
  echo ""
  echo "ℹ Node/npm não encontrado — pule se não for mexer nos frontends (bandkit, saggirag, velodna)."
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo ""
  echo "⚠ Projetos com falha na instalação de deps: ${FAILED[*]}"
  echo "  (o venv foi criado, mas as dependências não instalaram — verifique o requirements/pyproject)"
fi

cat <<'EON'

════════════════════════════════════════════════════════════════════
✅ Setup local concluído.

Próximos passos:
  • IA local (musicdna-ai, trend-radar, velodna, saggirag):
        brew install ollama && ollama serve
        ollama pull llama3 && ollama pull mistral
  • Infra pesada (Airflow/MLflow) continua via Docker, sob demanda:
        docker compose -f <projeto>/docker-compose.yml up
  • Ativar um projeto:
        source <projeto>/.venv/bin/activate      # (bandkit usa backend/.venv)
  • Portas: ver o mapa em CLAUDE.md (seção "Desenvolvimento local").
════════════════════════════════════════════════════════════════════
EON
