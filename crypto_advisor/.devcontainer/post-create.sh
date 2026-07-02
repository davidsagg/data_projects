#!/usr/bin/env bash
set -e

echo "━━━ Atualizando pip ━━━"
pip install --upgrade pip --quiet

echo "━━━ Instalando dependências do projeto ━━━"
pip install -e ".[dev]" --quiet

echo "━━━ Criando diretório de dados ━━━"
mkdir -p /workspaces/crypto_advisor/data

echo "━━━ Instalando Claude Code ━━━"
npm install -g @anthropic-ai/claude-code

echo "━━━ Verificando instalação ━━━"
python --version
claude --version

echo ""
echo "✓ Setup concluído."
echo ""
echo "Próximos passos:"
echo "  • Copie o arquivo de variáveis:  cp .env.example .env"
echo "  • Adicione suas chaves de API no .env"
echo "  • Autentique o Claude Code:      claude login"
echo "  • Inicie o scheduler:            python -m crypto_advisor"
echo "  • Inicie a UI:                   streamlit run src/crypto_advisor/ui/app.py"
