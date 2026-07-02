#!/bin/bash

# Script de Setup - OKR Portfolio Dashboard
# Execute este script para configurar o projeto pela primeira vez

echo "🚀 Iniciando setup do OKR Portfolio Dashboard..."
echo ""

# Verificar se Node.js está instalado
if ! command -v node &> /dev/null
then
    echo "❌ Node.js não encontrado!"
    echo "📥 Por favor, instale Node.js 18+ de: https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js $(node -v) encontrado"
echo "✅ npm $(npm -v) encontrado"
echo ""

# Verificar se está na pasta correta
if [ ! -f "package.json" ]; then
    echo "❌ Erro: package.json não encontrado!"
    echo "Execute este script dentro da pasta okr-portfolio-dashboard"
    exit 1
fi

echo "📦 Instalando dependências..."
npm install

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Setup concluído com sucesso!"
    echo ""
    echo "📝 Próximos passos:"
    echo "   1. Execute: npm run dev"
    echo "   2. Abra: http://localhost:5173"
    echo ""
    echo "📚 Outros comandos úteis:"
    echo "   npm run build   - Gerar build de produção"
    echo "   npm run preview - Visualizar build localmente"
    echo ""
else
    echo "❌ Erro ao instalar dependências"
    exit 1
fi
